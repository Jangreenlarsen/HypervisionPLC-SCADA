"""Alarmnotifikation (lag 3): webhook og e-mail når en alarm rejses eller ophører.

Kilde: `AlarmService._event` kalder `on_alarm_event` (kun `raise` og `clear`; kvittering og selve notifikationsfejlen `sys:notify` giver
aldrig besked). Hændelser filtreres på prioritet, samles i ét parti pr. `batch_s` (stormbeskyttelse) og sendes af en arbejdsopgave med
forsøg igen. Webhook-adressen og -tokenet og SMTP-adgangskoden er hemmeligheder: de gemmes i `secrets.json`, sættes skriv-kun og
vises, logges eller returneres aldrig (API'et ser kun *om* de er sat, og webhook-adressens vært).

Må ikke tale med PLC'er — kun udgående til en ekstern adresse (webhook) og en SMTP-server, som en admin har sat op.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import smtplib
import socket
import ssl
import time
from collections import deque
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urlsplit

import httpx

from ..config import read_version
from ..storage.secrets import SecretStore
from . import sysconfig
from .errors import ServiceError

log = logging.getLogger(__name__)

# httpx logger hele adressen ved INFO ("HTTP Request: POST <url>") — en webhook-adresse er en hemmelighed (fx et Home Assistant-id eller
# en Slack-nøgle) og må aldrig i loggen. Derfor kun advarsler/fejl fra httpx og httpcore, uanset LOG_LEVEL.
for _name in ("httpx", "httpcore"):
    logging.getLogger(_name).setLevel(logging.WARNING)

SECTION = "notifications"
EMAIL_PROVIDERS = ("smtp", "resend")
RESEND_URL = "https://api.resend.com/emails"   # fast adresse (ikke konfigurerbar: ingen SSRF via e-mail-kanalen)
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
PRIORITY_TEXT = {"high": "HØJ", "medium": "MEDIUM", "low": "LAV"}
MAX_PER_MESSAGE = 20          # flere alarmer i ét parti: de første vises, resten som "+N flere"
MAX_PENDING = 500
MAX_INFLIGHT = 10                    # partier der samtidig venter på forsøg igen
RETRY_DELAYS = (5.0, 30.0, 120.0)   # forsøg igen efter 5 s, 30 s og 120 s (i alt 4 forsøg)
FAIL_STREAK_PROBLEM = 3             # så mange mislykkede afsendelser i træk giver en problemmelding (Status + SYS-alarm)
NEVER_NOTIFY = ("sys:notify",)      # notifikationsfejl må ikke selv give en notifikation (løkke)

DEFAULTS: dict[str, Any] = {
    "enabled": False, "min_priority": "high", "on_clear": True, "batch_s": 20,
    "webhook": {"enabled": False},
    "email": {"enabled": False, "provider": "smtp", "host": "", "port": 587, "security": "starttls", "username": "", "sender": "", "recipients": []},
}
_EMAIL = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")
_HOST = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$")
_TOKEN = re.compile(r"^[\x21-\x7e]{8,300}$")      # printbare tegn uden mellemrum
_RESEND_KEY = re.compile(r"^re_[A-Za-z0-9_-]{16,300}$")


def _bad(message: str) -> ServiceError:
    return ServiceError(400, message)


def _flag(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise _bad(f"'{name}' skal være sand eller falsk")
    return value


class NotificationService:
    def __init__(self, data_dir: Path, secrets: SecretStore, *, instance: str | None = None,
                 client_factory: Callable[[], httpx.AsyncClient] | None = None,
                 smtp_send: Callable[[dict[str, Any], str, EmailMessage], None] | None = None) -> None:
        self.data_dir = data_dir
        self.secrets = secrets
        self.instance = instance or socket.gethostname()
        self._client_factory = client_factory or (lambda: httpx.AsyncClient(timeout=10.0, follow_redirects=False, trust_env=False))
        self._smtp_send = smtp_send or self._real_smtp_send
        self.retry_delays: tuple[float, ...] = RETRY_DELAYS
        self.pending: list[dict[str, Any]] = []
        self._wake = asyncio.Event()
        self.deliveries: deque[dict[str, Any]] = deque(maxlen=50)
        self.sent: dict[str, int] = {"webhook": 0, "email": 0}
        self.failed: dict[str, int] = {"webhook": 0, "email": 0}
        self.dropped = 0
        self.fail_streak: dict[str, int] = {"webhook": 0, "email": 0}
        self.last_error: dict[str, str] = {}
        self._cache: dict[str, Any] | None = None
        self._inflight: set[asyncio.Task] = set()

    # ------------------------------------------------------------- konfiguration

    def config(self) -> dict[str, Any]:
        """Gemt konfiguration oven på standardværdierne — aldrig hemmeligheder."""
        import copy
        if self._cache is not None:
            return copy.deepcopy(self._cache)
        cfg = copy.deepcopy(DEFAULTS)
        try:
            raw = json.loads(sysconfig._settings_path(self.data_dir).read_text(encoding="utf-8")).get(SECTION)
        except FileNotFoundError:
            raw = None
        except (OSError, ValueError, AttributeError) as exc:
            log.warning("Notifikationsopsætningen kunne ikke læses (standardværdier bruges, notifikationer er slået fra): %s", exc)
            raw = None
        if isinstance(raw, dict):
            for k in ("enabled", "on_clear"):
                if isinstance(raw.get(k), bool):
                    cfg[k] = raw[k]
            if raw.get("min_priority") in PRIORITY_RANK:
                cfg["min_priority"] = raw["min_priority"]
            if isinstance(raw.get("batch_s"), (int, float)) and not isinstance(raw["batch_s"], bool) and 5 <= raw["batch_s"] <= 300:
                cfg["batch_s"] = raw["batch_s"]
            for ch in ("webhook", "email"):
                if isinstance(raw.get(ch), dict):
                    cfg[ch].update({k: v for k, v in raw[ch].items() if k in cfg[ch]})
        self._cache = copy.deepcopy(cfg)
        return cfg

    def public(self) -> dict[str, Any]:
        """Til siden: konfiguration + *om* hemmeligheder er sat (og webhook-adressens vært) + status. Aldrig værdierne."""
        cfg = self.config()
        url = self.secrets.get_secret(SECTION, "webhook_url")
        cfg["webhook"]["has_url"] = url is not None
        cfg["webhook"]["host"] = (urlsplit(url).netloc.split("@")[-1] if url else "")
        cfg["webhook"]["has_token"] = self.secrets.has_secret(SECTION, "webhook_token")
        cfg["email"]["has_password"] = self.secrets.has_secret(SECTION, "smtp_password")
        cfg["email"]["has_resend_key"] = self.secrets.has_secret(SECTION, "resend_key")
        return {"config": cfg, "deliveries": list(self.deliveries)[::-1], "queued": len(self.pending),
                "sent": dict(self.sent), "failed": dict(self.failed), "dropped": self.dropped,
                "failing": self.failing()}

    def update(self, body: dict[str, Any]) -> dict[str, Any]:
        """Valider og gem. Kun felter i `body` ændres; hemmeligheder sættes kun når de er udfyldt (eller eksplicit fjernes)."""
        cfg = self.config()
        changed_secrets: list[str] = []
        for k in ("enabled", "on_clear"):
            if k in body:
                cfg[k] = _flag(body[k], k)
        if "min_priority" in body:
            if body["min_priority"] not in PRIORITY_RANK:
                raise _bad("min_priority skal være high, medium eller low")
            cfg["min_priority"] = body["min_priority"]
        if "batch_s" in body:
            v = body["batch_s"]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not 5 <= v <= 300:
                raise _bad("Samletid (batch_s) skal være 5-300 sekunder")
            cfg["batch_s"] = v
        wh = body.get("webhook") or {}
        if wh:
            if "enabled" in wh:
                cfg["webhook"]["enabled"] = _flag(wh["enabled"], "webhook.enabled")
            if (wh.get("url") and wh.get("clear_url")) or (wh.get("token") and wh.get("clear_token")):
                raise _bad("Kan ikke både sætte og fjerne adresse/token i samme gemning")
            if wh.get("url"):
                self._check_url(wh["url"])
                changed_secrets.append("webhook_url")
            if wh.get("token"):
                if not isinstance(wh["token"], str) or not _TOKEN.match(wh["token"]):
                    raise _bad("Token skal være 8-300 tegn uden mellemrum")
                changed_secrets.append("webhook_token")
        em = body.get("email") or {}
        if em:
            for k in ("enabled",):
                if k in em:
                    cfg["email"][k] = _flag(em[k], f"email.{k}")
            if "provider" in em:
                if em["provider"] not in EMAIL_PROVIDERS:
                    raise _bad("E-mail-udbyder skal være smtp eller resend")
                cfg["email"]["provider"] = em["provider"]
            if "host" in em:
                if not isinstance(em["host"], str) or (em["host"] and not _HOST.match(em["host"])):
                    raise _bad("Ugyldig SMTP-server (værtsnavn eller IP)")
                cfg["email"]["host"] = em["host"]
            if "port" in em:
                if isinstance(em["port"], bool) or not isinstance(em["port"], int) or not 1 <= em["port"] <= 65535:
                    raise _bad("SMTP-port skal være 1-65535")
                cfg["email"]["port"] = em["port"]
            if "security" in em:
                if em["security"] not in ("starttls", "ssl", "none"):
                    raise _bad("Sikkerhed skal være starttls, ssl eller none")
                cfg["email"]["security"] = em["security"]
            if "username" in em:
                if not isinstance(em["username"], str) or len(em["username"]) > 200 or "\n" in em["username"]:
                    raise _bad("Ugyldigt SMTP-brugernavn")
                cfg["email"]["username"] = em["username"]
            if "sender" in em:
                if not isinstance(em["sender"], str) or (em["sender"] and not _EMAIL.match(em["sender"])):
                    raise _bad("Ugyldig afsenderadresse")
                cfg["email"]["sender"] = em["sender"]
            if "recipients" in em:
                r = em["recipients"]
                if not isinstance(r, list) or len(r) > 10 or not all(isinstance(x, str) and _EMAIL.match(x) for x in r):
                    raise _bad("Modtagere skal være op til 10 gyldige e-mailadresser")
                cfg["email"]["recipients"] = r
            if em.get("resend_key") and em.get("clear_resend_key"):
                raise _bad("Kan ikke både sætte og fjerne Resend-nøglen i samme gemning")
            if em.get("resend_key"):
                if not isinstance(em["resend_key"], str) or not _RESEND_KEY.match(em["resend_key"]):
                    raise _bad("Resend API-nøglen skal starte med re_ (kopiér den fra Resend)")
                changed_secrets.append("resend_key")
            if em.get("password") and em.get("clear_password"):
                raise _bad("Kan ikke både sætte og fjerne adgangskoden i samme gemning")
            if em.get("password"):
                if not isinstance(em["password"], str) or len(em["password"]) > 300 or "\n" in em["password"]:
                    raise _bad("Ugyldig SMTP-adgangskode")
                changed_secrets.append("smtp_password")
        # fuldstændighed: en slået-til kanal skal kunne bruges
        has_url = self.secrets.has_secret(SECTION, "webhook_url") or wh.get("url")
        if cfg["webhook"]["enabled"] and not has_url and not wh.get("clear_url"):
            raise _bad("Webhook kan ikke slås til uden en adresse")
        if cfg["webhook"]["enabled"] and wh.get("clear_url"):
            raise _bad("Webhook kan ikke slås til uden en adresse — slå den fra, når adressen fjernes")
        e = cfg["email"]
        has_resend = (self.secrets.has_secret(SECTION, "resend_key") and not em.get("clear_resend_key")) or em.get("resend_key")
        if e["enabled"] and e["provider"] == "resend":
            if not (e["sender"] and e["recipients"]):
                raise _bad("Resend kræver afsender (en adresse på et domæne, du har verificeret hos Resend) og mindst én modtager")
            if not has_resend:
                raise _bad("Resend kræver en API-nøgle")
        elif e["enabled"] and not (e["host"] and e["sender"] and e["recipients"]):
            raise _bad("E-mail kræver SMTP-server, afsender og mindst én modtager")
        has_pw = (self.secrets.has_secret(SECTION, "smtp_password") and not em.get("clear_password")) or em.get("password")
        if e["provider"] == "smtp" and e["security"] == "none" and (e["username"] or has_pw):
            raise _bad("Login kræver STARTTLS eller SSL — med sikkerhed 'Ingen' ville adgangskoden blive sendt i klartekst")
        # alt er gyldigt — først nu skrives der
        if wh.get("url"):
            self.secrets.set_secret(SECTION, "webhook_url", wh["url"])
        if wh.get("token"):
            self.secrets.set_secret(SECTION, "webhook_token", wh["token"])
        if em.get("password"):
            self.secrets.set_secret(SECTION, "smtp_password", em["password"])
        if em.get("resend_key"):
            self.secrets.set_secret(SECTION, "resend_key", em["resend_key"])
        if wh.get("clear_url"):
            self.secrets.delete_secret(SECTION, "webhook_url"); changed_secrets.append("webhook_url (fjernet)")
        if wh.get("clear_token"):
            self.secrets.delete_secret(SECTION, "webhook_token"); changed_secrets.append("webhook_token (fjernet)")
        if em.get("clear_password"):
            self.secrets.delete_secret(SECTION, "smtp_password"); changed_secrets.append("smtp_password (fjernet)")
        if em.get("clear_resend_key"):
            self.secrets.delete_secret(SECTION, "resend_key"); changed_secrets.append("resend_key (fjernet)")
        sysconfig.save_section(self.data_dir, SECTION, cfg)
        self._cache = None                  # ny konfiguration læses ved næste brug
        for ch in ("webhook", "email"):     # en kanal der er slået fra (eller alt slået fra) har ingen fejl at melde
            if not (cfg["enabled"] and cfg[ch]["enabled"]):
                self.fail_streak[ch] = 0
                self.last_error.pop(ch, None)
        self._wake.set()
        return {"public": self.public(), "secrets_changed": changed_secrets}

    @staticmethod
    def _check_url(url: Any) -> None:
        if not isinstance(url, str) or len(url) > 500 or any(c.isspace() or ord(c) < 32 for c in url):
            raise _bad("Ugyldig webhook-adresse")
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise _bad("Webhook-adressen skal starte med http:// eller https:// og have et værtsnavn")

    # ------------------------------------------------------------- hændelser

    def on_alarm_event(self, row: dict[str, Any], event: str, now: float) -> None:
        """Kaldt af alarmmotoren for hver hændelse. Kun nye (`raise`, også eskalering) og ophørte (`clear`) alarmer."""
        if event not in ("raise", "clear") or any(row["key"].startswith(p) for p in NEVER_NOTIFY):
            return
        cfg = self.config()
        if not cfg["enabled"] or (event == "clear" and not cfg["on_clear"]):
            return
        if PRIORITY_RANK.get(row["priority"], 9) > PRIORITY_RANK[cfg["min_priority"]]:
            return
        if len(self.pending) >= MAX_PENDING:
            self.pending.pop(0)
            self.dropped += 1
        self.pending.append({"event": event, "time": now, "key": row["key"], "tag": row["tag"], "plc": row["plc"],
                             "kind": row.get("kind", ""), "level": row["level"], "priority": row["priority"],
                             "message": row["message"]})
        self._wake.set()

    # ------------------------------------------------------------- afsendelse

    async def run(self) -> None:
        while True:
            await self._wake.wait()
            self._wake.clear()
            if not self.pending:
                continue
            await asyncio.sleep(self.config()["batch_s"])      # saml en alarmstorm i ét parti
            batch, self.pending = self.pending, []
            if len(self._inflight) >= MAX_INFLIGHT:      # en død kanal ophober ikke ubegrænset mange partier
                self.dropped += len(batch)
                log.warning("Notifikationer kasseret: %d afsendelser er allerede undervejs", len(self._inflight))
                continue
            task = asyncio.create_task(self._deliver_safe(batch))
            self._inflight.add(task)
            task.add_done_callback(self._inflight.discard)

    async def _deliver_safe(self, batch: list[dict[str, Any]]) -> None:
        try:
            await self.deliver(batch)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Afsendelse af notifikation fejlede uventet")

    def failing(self) -> dict[str, str]:
        """Kanaler med gentagne mislykkede afsendelser — kun hvis notifikationer og kanalen stadig er slået til."""
        cfg = self.config()
        if not cfg["enabled"]:
            return {}
        return {ch: self.last_error.get(ch, "") for ch, n in self.fail_streak.items() if n >= FAIL_STREAK_PROBLEM and cfg[ch]["enabled"]}

    async def deliver(self, batch: list[dict[str, Any]], *, test: bool = False) -> dict[str, dict[str, Any]]:
        """Send til de slåede-til kanaler (parallelt, så en død kanal ikke forsinker den anden). → {kanal: {ok, attempts, error}}.
        Med `test` forsøges kun én gang. Er notifikationer slået fra, sendes intet (heller ikke hændelser, der allerede lå i køen)."""
        cfg = self.config()
        if not test and not cfg["enabled"]:
            return {}
        channels = [ch for ch in ("webhook", "email") if cfg[ch]["enabled"]]
        outcomes = await asyncio.gather(*(self._deliver_channel(ch, batch, cfg, test) for ch in channels))
        results: dict[str, dict[str, Any]] = {}
        for channel, (ok, attempts, error) in zip(channels, outcomes):
            results[channel] = {"ok": ok, "attempts": attempts, "error": error}
            self.deliveries.append({"ts": time.time(), "channel": channel, "ok": ok, "attempts": attempts, "alarms": len(batch),
                                    "error": error, "test": test})
            if not test:
                (self.sent if ok else self.failed)[channel] += 1
                self.fail_streak[channel] = 0 if ok else self.fail_streak[channel] + 1
                if ok:
                    self.last_error.pop(channel, None)
                else:
                    self.last_error[channel] = error
            log_fn = log.info if ok else log.warning
            log_fn("Notifikation %s %s (%d alarm(er), %d forsøg)%s", channel, "sendt" if ok else "FEJLEDE", len(batch), attempts,
                   f": {error}" if error else "")
        return results

    async def _deliver_channel(self, channel: str, batch: list[dict[str, Any]], cfg: dict[str, Any], test: bool) -> tuple[bool, int, str]:
        attempts, error = 0, ""
        for delay in (0.0,) if test else (0.0, *self.retry_delays):
            if delay:
                await asyncio.sleep(delay)
            attempts += 1
            try:
                await (self._send_webhook(batch, cfg) if channel == "webhook" else self._send_email(batch, cfg))
                return True, attempts, ""
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                error = self._safe_error(exc)
        return False, attempts, error

    async def send_test(self) -> dict[str, dict[str, Any]]:
        sample = [{"event": "raise", "time": time.time(), "key": "test:notifikation", "tag": "", "plc": "", "kind": "test", "level": "SYS",
                   "priority": "high", "message": "Prøvebesked fra HypervisionPLC SCADA — notifikationer virker"}]
        results = await self.deliver(sample, test=True)
        if not results:
            raise ServiceError(409, "Ingen kanal er slået til — slå webhook eller e-mail til og gem først")
        return results

    def _secret_fragments(self) -> list[str]:
        """Alt der ikke må stå i en fejltekst: hele værdierne og dele af webhook-adressen (sti, forespørgsel, brugerinfo, stisegmenter og
        værdier ≥ 6 tegn, også URL-kodede), så en delvis gengivelse i en httpx-fejl heller ikke afslører noget."""
        out: set[str] = set()
        url = self.secrets.get_secret(SECTION, "webhook_url")
        if url:
            parts = urlsplit(url)
            out |= {url, quote(url, safe=""), quote(url, safe=":/")}
            for piece in (parts.path, parts.query, parts.fragment, parts.netloc.rpartition("@")[0], parts.username or "", parts.password or ""):
                if len(piece) >= 4:
                    out |= {piece, quote(piece, safe="")}
            for seg in [*parts.path.split("/"), *(kv.partition("=")[2] for kv in parts.query.split("&"))]:
                if len(seg) >= 6:
                    out |= {seg, quote(seg, safe="")}
        for name in ("webhook_token", "smtp_password", "resend_key"):
            v = self.secrets.get_secret(SECTION, name)
            if v:
                out |= {v, quote(v, safe="")}
        return sorted(out, key=len, reverse=True)       # længste først, så en lang værdi erstattes som helhed

    def _safe_error(self, exc: Exception) -> str:
        """Fejltekst uden hemmeligheder. Erstatningen sker FØR afkortningen (ellers kunne en hemmelighed over grænsen slippe ud)."""
        text = f"{type(exc).__name__}: {exc}"
        for fragment in self._secret_fragments():
            text = text.replace(fragment, "<skjult>")
        return text[:300]

    # -- besked

    def _payload(self, batch: list[dict[str, Any]]) -> dict[str, Any]:
        iso = lambda t: datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="seconds")  # noqa: E731
        return {"type": "alarm", "instance": self.instance, "version": read_version().get("version", ""),
                "time": iso(time.time()), "events": [{**e, "time": iso(e["time"])} for e in batch[:MAX_PER_MESSAGE]],
                "more": max(0, len(batch) - MAX_PER_MESSAGE)}

    def subject_and_text(self, batch: list[dict[str, Any]]) -> tuple[str, str]:
        raised = [e for e in batch if e["event"] == "raise"]
        cleared = [e for e in batch if e["event"] == "clear"]
        parts = []
        if raised:
            parts.append(f"{len(raised)} {'alarm' if len(raised) == 1 else 'alarmer'}")
        if cleared:
            parts.append(f"{len(cleared)} ophørt")
        subject = f"[SCADA {self.instance}] " + ", ".join(parts)
        lines = []
        for title, items in (("Nye alarmer", raised), ("Ophørt", cleared)):
            if items:
                lines.append(f"{title}:")
                for e in items[:MAX_PER_MESSAGE]:
                    where = f" ({e['tag'] or e['plc']})" if (e["tag"] or e["plc"]) else ""
                    lines.append(f"  • [{PRIORITY_TEXT.get(e['priority'], e['priority'])}] {e['message']}{where}")
                if len(items) > MAX_PER_MESSAGE:
                    lines.append(f"  … og {len(items) - MAX_PER_MESSAGE} flere")
                lines.append("")
        lines.append(f"Sendt af HypervisionPLC SCADA {read_version().get('version', '')} på {self.instance}.")
        return subject, "\n".join(lines)

    # -- kanaler

    async def _send_webhook(self, batch: list[dict[str, Any]], cfg: dict[str, Any]) -> None:
        url = self.secrets.get_secret(SECTION, "webhook_url")
        if not url:
            raise RuntimeError("Webhook-adressen er ikke sat")
        headers = {"User-Agent": "HypervisionPLC-SCADA"}
        token = self.secrets.get_secret(SECTION, "webhook_token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with self._client_factory() as client:
            r = await client.post(url, json=self._payload(batch), headers=headers)
        if not 200 <= r.status_code < 300:
            raise RuntimeError(f"Modtageren svarede HTTP {r.status_code}")

    async def _send_email(self, batch: list[dict[str, Any]], cfg: dict[str, Any]) -> None:
        e = cfg["email"]
        subject, text = self.subject_and_text(batch)
        if e["provider"] == "resend":
            await self._send_resend(e, subject, text)
            return
        msg = EmailMessage()
        msg["Subject"], msg["From"], msg["To"] = subject, e["sender"], ", ".join(e["recipients"])
        msg.set_content(text)
        await asyncio.to_thread(self._smtp_send, {**e, "password": self.secrets.get_secret(SECTION, "smtp_password")}, "", msg)

    async def _send_resend(self, e: dict[str, Any], subject: str, text: str) -> None:
        """Resends HTTPS-API (POST /emails, Bearer-nøgle). Afsenderen skal være på et domæne, der er verificeret hos Resend."""
        key = self.secrets.get_secret(SECTION, "resend_key")
        if not key:
            raise RuntimeError("Resend API-nøglen er ikke sat")
        headers = {"Authorization": f"Bearer {key}", "User-Agent": "HypervisionPLC-SCADA"}
        payload = {"from": e["sender"], "to": e["recipients"], "subject": subject, "text": text}
        async with self._client_factory() as client:
            r = await client.post(RESEND_URL, json=payload, headers=headers)
        if not 200 <= r.status_code < 300:
            detail = ""
            try:
                body = r.json()
                detail = str(body.get("message") or body.get("error") or "")[:200] if isinstance(body, dict) else ""
            except ValueError:
                pass
            raise RuntimeError(f"Resend svarede HTTP {r.status_code}" + (f": {detail}" if detail else ""))

    @staticmethod
    def _real_smtp_send(e: dict[str, Any], _unused: str, msg: EmailMessage) -> None:
        ctx = ssl.create_default_context()
        smtp = smtplib.SMTP_SSL(e["host"], e["port"], timeout=15, context=ctx) if e["security"] == "ssl" \
            else smtplib.SMTP(e["host"], e["port"], timeout=15)
        with smtp:
            smtp.ehlo()
            if e["security"] == "starttls":
                smtp.starttls(context=ctx)
                smtp.ehlo()
            if e["username"]:
                smtp.login(e["username"], e["password"] or "")
            smtp.send_message(msg)
