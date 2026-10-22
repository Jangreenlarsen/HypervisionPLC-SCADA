"""Netværksopsætning (System › Konfiguration) — validering og anmodning til den privilegerede hjælper.

Arbejdsdeling (som OTA-opdateringen, se deploy/apply-config.sh):
  * SCADA-tjenesten kører som almindelig bruger og kan ikke ændre netværket. Den VALIDERER opsætningen og lægger
    `network.request` i `<data>/config/`. En root-tjeneste (systemd .path) anvender den med NetworkManager (`nmcli`).
  * Efter anvendelsen har brugeren CONFIRM_S sekunder til at BEKRÆFTE fra den nye adresse (`network.confirm`);
    sker det ikke, gendanner hjælperen den gamle opsætning automatisk (ingen lockout).
  * Tjenesten ejer `<data>/config` — derfor skriver root ALDRIG dér. Status og log ligger i en root-ejet mappe
    (`state_dir`, standard /var/lib/hypervisionplc-scada-net) som tjenesten kun læser.
  * Intet fra browseren når et shell: alle værdier valideres her (og igen i hjælperen) og skrives som `NØGLE=værdi`.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from .errors import ServiceError

log = logging.getLogger(__name__)

CONFIRM_S = 90   # tid til at bekræfte den nye opsætning, før den gamle gendannes
MODES = ("dhcp", "static", "dhcp_static", "dhcp_fallback")
MODE_TEXT = {"dhcp": "DHCP", "static": "Fast IP", "dhcp_static": "DHCP + fast IP som sekundær",
             "dhcp_fallback": "DHCP, fast IP efter N fejl"}
FALLBACK_DEFAULT = 5   # kontroller (à 30 s) uden DHCP-svar, før reserve-IP'en tages i brug
FALLBACK_MAX = 20
_IFACE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,14}$")
_HOST = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
_SAFE = re.compile(r"[^A-Za-z0-9_.@-]")
STALE_S = 600   # en anmodning/status der ikke er ændret så længe, regnes for hængt


def _addr(value: Any, label: str, *, what: str = "adresse") -> ipaddress.IPv4Address:
    if not isinstance(value, str):
        raise ServiceError(400, f"{label}: skriv en IPv4-{what}")
    text = value.strip()
    if not re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", text):
        raise ServiceError(400, f"{label}: '{value}' er ikke en gyldig IPv4-{what} (fx 192.168.1.50)")
    try:
        ip = ipaddress.IPv4Address(text)
    except ValueError:
        raise ServiceError(400, f"{label}: '{value}' er ikke en gyldig IPv4-{what}") from None
    if ip.is_unspecified or ip.is_loopback or ip.is_multicast or ip.is_reserved or ip.is_link_local:
        raise ServiceError(400, f"{label}: {ip} kan ikke bruges som {what}")
    return ip


def validate_network(values: dict[str, Any], interfaces: list[str] | None = None) -> dict[str, Any]:
    """Kontrollér hele opsætningen og returnér den i fast form. Afviser med en specifik besked (400)."""
    iface = values.get("interface")
    if not isinstance(iface, str) or not _IFACE.fullmatch(iface):
        raise ServiceError(400, "Netkort: vælg et netkort")
    if interfaces is not None and iface not in interfaces:
        raise ServiceError(400, f"Netkort: '{iface}' findes ikke på maskinen")
    mode = values.get("mode")
    if mode not in MODES:
        raise ServiceError(400, "Tilstand: vælg DHCP, Fast IP, DHCP + fast IP eller DHCP med reserve-IP")
    out: dict[str, Any] = {"interface": iface, "mode": mode, "ip": "", "prefix": 0, "gateway": "", "dns": [], "hostname": "",
                      "fallback_after": FALLBACK_DEFAULT}

    dns_in = values.get("dns") or []
    if not isinstance(dns_in, list) or len(dns_in) > 3:
        raise ServiceError(400, "DNS: højst 3 adresser")
    out["dns"] = [str(_addr(d, "DNS", what="serveradresse")) for d in dns_in if str(d).strip()]

    host = values.get("hostname")
    if host not in (None, ""):
        if not isinstance(host, str) or not _HOST.fullmatch(host.strip().lower()):
            raise ServiceError(400, "Værtsnavn: 1–63 tegn, kun bogstaver (a–z), tal og bindestreg, ikke først/sidst")
        out["hostname"] = host.strip().lower()

    if mode == "dhcp":
        return out

    ip = _addr(values.get("ip"), "IP-adresse")
    prefix = values.get("prefix")
    if isinstance(prefix, bool) or not isinstance(prefix, int) or not 8 <= prefix <= 30:
        raise ServiceError(400, "Subnet: præfikset skal være et helt tal mellem 8 og 30 (fx 24 = 255.255.255.0)")
    net = ipaddress.IPv4Network(f"{ip}/{prefix}", strict=False)
    if ip == net.network_address or ip == net.broadcast_address:
        raise ServiceError(400, f"IP-adresse: {ip} er netværks- eller broadcast-adressen i {net}")
    out["ip"], out["prefix"] = str(ip), prefix

    gw_in = values.get("gateway")
    if gw_in not in (None, ""):
        gw = _addr(gw_in, "Gateway")
        if gw == ip:
            raise ServiceError(400, "Gateway: må ikke være den samme adresse som IP-adressen")
        if gw not in net:
            raise ServiceError(400, f"Gateway: {gw} ligger ikke i subnettet {net} — maskinen kunne ikke nå den")
        out["gateway"] = str(gw)
    if mode == "dhcp_static":
        out["gateway"] = ""   # DHCP leverer gatewayen; en angivet gateway ignoreres (UI'et viser ikke feltet)
    if mode == "dhcp_fallback":
        n_in = values.get("fallback_after", FALLBACK_DEFAULT)
        if isinstance(n_in, bool) or not isinstance(n_in, int) or not 1 <= n_in <= FALLBACK_MAX:
            raise ServiceError(400, f"Reserve-IP efter: et helt tal mellem 1 og {FALLBACK_MAX} (kontroller à 30 sekunder uden DHCP-svar)")
        out["fallback_after"] = n_in
    return out


def _clean(value: Any) -> str:
    return _SAFE.sub("", str(value))


def build_request(cfg: dict[str, Any], actor: str, req_id: str) -> str:
    """`NØGLE=værdi`-linjer til hjælperen. Alle værdier er allerede valideret; tegn uden for en sikker mængde fjernes dog også her."""
    lines = {
        "ID": _clean(req_id), "BY": _clean(actor)[:64] or "ukendt", "CONFIRM_S": str(CONFIRM_S),
        "IFACE": _clean(cfg["interface"]), "MODE": cfg["mode"], "IP": _clean(cfg["ip"]), "PREFIX": str(int(cfg["prefix"])),
        "GATEWAY": _clean(cfg["gateway"]), "FALLBACK_AFTER": str(int(cfg.get("fallback_after", FALLBACK_DEFAULT))), "DNS": ",".join(_clean(d) for d in cfg["dns"]), "HOSTNAME": _clean(cfg["hostname"]),
    }
    return "".join(f"{k}={v}\n" for k, v in lines.items())


class NetworkService:
    def __init__(self, data_dir: Path, state_dir: Path | None = None):
        self.dir = data_dir / "config"                                 # ejes af tjenesten: request/confirm/revert, gemte valg
        self.state = state_dir or Path("/var/lib/hypervisionplc-scada-net")   # ejes af root: status, log
        self.enabled_file = self.state / "enabled"

    # ------------------------------------------------------------- læsning
    @property
    def enabled(self) -> bool:
        """Hjælperen er installeret (deploy/install.sh opretter filen)."""
        return self.enabled_file.exists()

    def disabled_reason(self) -> str:
        """'' = aktiveret. 'no_backend' = hverken NetworkManager eller ifupdown. 'not_installed' = install.sh er ikke kørt."""
        if self.enabled:
            return ""
        if (self.state / "no-backend").exists() or (self.state / "no-nmcli").exists():
            return "no_backend"
        return "not_installed"

    def capabilities(self) -> dict[str, Any]:
        """Hvilket netværkssystem maskinen bruger ('nm' | 'ifupdown') og om der findes en DHCP-klient (skrevet af install.sh)."""
        backend, dhcp = "nm", True        # ældre installationer: kun NetworkManager
        try:
            for line in (self.state / "capabilities").read_text(encoding="utf-8").splitlines():
                key, _, value = line.partition("=")
                if key == "backend" and value in ("nm", "ifupdown", "none"):
                    backend = value
                elif key == "dhcp":
                    dhcp = value == "1"
        except OSError:
            pass
        return {"backend": backend, "dhcp_available": dhcp}

    def _read(self, name: str, base: Path | None = None) -> dict[str, Any] | None:
        try:
            data = json.loads(((base or self.dir) / name).read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (OSError, ValueError):
            return None

    def saved(self) -> dict[str, Any] | None:
        """Den sidst BEKRÆFTEDE opsætning (til formularen)."""
        return self._read("network.saved.json")

    def status(self) -> dict[str, Any]:
        last = self._read("status.json", self.state)
        pending = (self.dir / "network.request").exists()
        state = (last or {}).get("state", "idle")
        if pending and state not in ("applying", "waiting_confirm"):
            state = "queued"
            try:
                age = time.time() - (self.dir / "network.request").stat().st_mtime
            except OSError:
                age = 0.0
            if age > STALE_S:
                state = "stalled"
        if state == "applying" and last and time.time() - float(last.get("ts", 0)) > STALE_S:
            state = "stalled"
        if state == "confirmed":
            self._persist_saved()
        deadline = float((last or {}).get("deadline", 0) or 0)
        if state == "waiting_confirm" and deadline and time.time() > deadline + 15:
            state = "stalled"
        return {"enabled": self.enabled, "disabled_reason": self.disabled_reason(), **self.capabilities(), "state": state, "message": (last or {}).get("message", ""),
                "deadline": deadline or None, "confirm_s": CONFIRM_S, "target": self._read("network.pending.json"),
                "busy": state in ("queued", "applying", "waiting_confirm"), "saved": self.saved(),
                "watchdog": self.watchdog()}

    def watchdog(self) -> dict[str, Any] | None:
        """DHCP-vagtens seneste tilstand (skrives af deploy/net-watchdog.sh); forældet efter 3 minutter → None."""
        w = self._read("watchdog.json", self.state)
        if not w:
            return None
        if time.time() - float(w.get("ts", 0) or 0) > 180:
            w["stale"] = True
        return w

    # ------------------------------------------------------------- handlinger
    def request_apply(self, cfg: dict[str, Any], actor: str) -> dict[str, Any]:
        if not self.enabled:
            raise ServiceError(409, "Netværksændring via web er ikke aktiveret på denne server — kør 'sh deploy/install.sh' som root én gang")
        caps = self.capabilities()
        if cfg["mode"] != "static" and not caps["dhcp_available"]:
            raise ServiceError(400, "Maskinen har ingen (understøttet) DHCP-klient — på ifupdown kræves dhcpcd (apt install dhcpcd-base). Vælg Fast IP, eller installér klienten og kør install.sh --update")
        if self.status()["busy"]:
            raise ServiceError(409, "En netværksændring er allerede i gang")
        req_id = str(int(time.time()))
        self.dir.mkdir(parents=True, exist_ok=True)
        for stale in ("network.confirm", "network.revert"):
            (self.dir / stale).unlink(missing_ok=True)
        target = {k: cfg[k] for k in ("interface", "mode", "ip", "prefix", "gateway", "dns", "hostname", "fallback_after")}
        (self.dir / "network.pending.json").write_text(json.dumps(target), encoding="utf-8")
        tmp = self.dir / "network.request.tmp"
        tmp.write_text(build_request(cfg, actor, req_id), encoding="utf-8")
        tmp.replace(self.dir / "network.request")   # først nu ser hjælperen den
        log.warning("Netværksændring anmodet af %s: %s %s/%s", actor, cfg["mode"], cfg["ip"], cfg["prefix"])
        return self.status()

    def confirm(self) -> dict[str, Any]:
        st = self.status()
        if st["state"] != "waiting_confirm":
            raise ServiceError(409, "Der er ingen netværksændring, der venter på bekræftelse (tiden kan være gået — så er den gamle opsætning gendannet)")
        self._atomic("network.confirm", "ok\n")
        log.warning("Netværksændring bekræftet")
        return self.status()

    def revert(self) -> dict[str, Any]:
        if self.status()["state"] != "waiting_confirm":
            raise ServiceError(409, "Der er ingen netværksændring at fortryde")
        self._atomic("network.revert", "ok\n")
        return self.status()

    # ------------------------------------------------------------- hjælp
    def _atomic(self, name: str, text: str) -> None:
        tmp = self.dir / (name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(self.dir / name)

    def _persist_saved(self) -> None:
        """Den bekræftede opsætning huskes til formularen — først når hjælperen selv har meldt `confirmed`."""
        pending = self._read("network.pending.json")
        if pending and self._read("network.saved.json") != pending:
            try:
                self._atomic("network.saved.json", json.dumps(pending))
            except OSError as exc:
                log.warning("Kunne ikke gemme den bekræftede netværksopsætning: %s", exc)
