"""Hjælperens læse-værktøjer (v4.1.0, PLAN.md fase 1): samler de data, et spørgsmål handler om — med brugerens rettigheder.

Bevidst deterministisk: værktøjerne vælges ud fra siden (konteksten) og ordene i spørgsmålet, ikke af modellen. Det
koster ét LLM-kald pr. spørgsmål i stedet for op til fire (målt på demo-VM'en: 2–4 tokens/s), og tekst fra anlægget
(alarmtekster, elementnavne) kan aldrig få modellen til at kalde noget. Alt her er rene læsninger af eksisterende
services; intet skriver til en PLC eller ændrer opsætning.

Sendes aldrig med: PLC-adresser og tag-kilder, adgangskoder, tokens, API-nøgler. Tags sendes med navn, beskrivelse og enhed.
"""

from __future__ import annotations

import logging
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any

from .assist_knowledge import ManualIndex, excerpt
from .auth import CurrentUser, role_at_least
from .symbols import config_tags

log = logging.getLogger("scada.assist")

MAX_TAGS = 6
MAX_ALARMS = 8
MAX_SYMBOLS = 30
MANUAL_HITS = 2
MANUAL_CHARS = 500
DATA_BUDGET = 2000        # tegn i alt til data — målt på demo-VM: ca. 6–8 tokens/s til at læse prompten
PERIODS = (("uge", 7 * 86400, "den seneste uge"), ("døgn", 86400, "det seneste døgn"), ("24 t", 86400, "det seneste døgn"),
           ("i dag", 86400, "det seneste døgn"), ("time", 3600, "den seneste time"))
# Søgeord til manualen pr. alarmtype (alarmteksten alene rammer ofte forkert afsnit)
ALARM_HINTS = {"comm": "fejlfinding kommunikation forbindelse PLC netværk", "tag": "alarmgrænse tag alarm prioritet",
               "symbol": "afvigelsesalarm symbol stilling tilbagemelding", "sys": "SYS alarm server"}
STATE_TXT = {"active_unack": "aktiv, ikke kvitteret", "active_ack": "aktiv, kvitteret", "rtn_unack": "ophørt, ikke kvitteret"}
PAGES = {"overview": "Drift (Overview)", "alarms": "Alarmer", "trends": "Trends", "draw": "Tegn", "editor": "Bindinger",
         "tags": "Tags", "plcs": "PLC'er", "drawings": "Tegninger", "symbols": "Symboler", "schedules": "Ugeprogrammer",
         "energy": "Energi", "status": "Status", "manual": "Manual"}
_SAFE = re.compile(r"[\x00-\x08\x0b-\x1f<>]")
# Adresser i fx kommunikationsalarmer ("Kan ikke forbinde til PLC (http://10.1.1.34:8080)") sendes ikke med
_ADDR = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s)]+|\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b|\[[0-9a-f:]+\](?::\d+)?", re.I)


def clean(text: Any, limit: int = 160) -> str:
    """Tekst fra anlægget ind i prompten: ingen styretegn eller vinkelparenteser (kan ikke lukke <data>), ingen
    netværksadresser, kort."""
    s = _ADDR.sub("(adresse)", _SAFE.sub(" ", str(text if text is not None else ""))).strip()
    return s[:limit] + ("…" if len(s) > limit else "")


def ago(ts: float | None, now: float) -> str:
    if not ts:
        return "ukendt tid"
    s = max(0, int(now - ts))
    if s < 90:
        return f"{s} s siden"
    if s < 5400:
        return f"{s // 60} min siden"
    if s < 172800:
        return f"{s // 3600} t siden"
    return f"{s // 86400} døgn siden"


def fmt_value(value: Any, unit: str = "", decimals: Any = None) -> str:
    if value is None:
        return "ingen værdi"
    if isinstance(value, bool):
        return "sand (1)" if value else "falsk (0)"
    if isinstance(value, (int, float)) and not (isinstance(value, float) and math.isnan(value)):
        d = decimals if isinstance(decimals, int) and 0 <= decimals <= 6 else (0 if float(value).is_integer() else 2)
        txt = f"{value:.{d}f}"
    else:
        txt = clean(value, 60)
    return f"{txt} {clean(unit, 12)}".strip()


def period_of(question: str) -> tuple[float, str]:
    q = question.lower()
    for word, span, txt in PERIODS:
        if word in q:
            return span, txt
    return 3600, "den seneste time"


@dataclass
class Context:
    page: str = ""
    drawing: str | None = None
    alarm: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class Gathered:
    blocks: list[tuple[str, str]] = field(default_factory=list)        # (overskrift, tekst)
    sources: list[dict[str, str]] = field(default_factory=list)        # {label, href}
    tools: list[str] = field(default_factory=list)                     # brugte værktøjer (til audit/metrics)

    def add(self, title: str, text: str, tool: str, source: dict[str, str] | None = None) -> None:
        if text:
            self.blocks.append((title, text))
            if tool not in self.tools:
                self.tools.append(tool)
            if source and source not in self.sources:
                self.sources.append(source)

    def render(self, budget: int = DATA_BUDGET) -> str:
        out, used = [], 0
        for title, text in self.blocks:
            part = f"[{title}]\n{text}"
            if used + len(part) > budget:
                room = budget - used - len(title) - 4
                if room < 120:
                    break
                part = f"[{title}]\n{text[:room]} …"
            out.append(part)
            used += len(part)
        return "\n\n".join(out)


class AssistTools:
    def __init__(self, *, alarms: Any, tags: Any, cache: Any, trend_db: Any, scope: Any, symbols: Any, drawings: Any,
                 manual: ManualIndex):
        self.alarms, self.tags, self.cache, self.trend_db = alarms, tags, cache, trend_db
        self.scope, self.symbols, self.drawings, self.manual = scope, symbols, drawings, manual

    # ------------------------------------------------------------------ adgang (som api/alarms.py og api/trends.py)
    def _visible(self, user: CurrentUser) -> set[str] | None:
        return self.scope.visible_tags(user)

    def _trendable(self, user: CurrentUser, visible: set[str] | None) -> set[str] | None:
        """Som api/trends.py::_allowed: under tekniker kun tags i de trends, der er sat op i brugerens tegninger."""
        if role_at_least(user.role, "engineer"):
            return visible
        configured = {t for s in self.symbols.trend_symbols(self.scope.drawing_ids(user)) for t in s["tags"]}
        return configured if visible is None else configured & visible

    # ------------------------------------------------------------------ værktøjerne
    def active_alarms(self, user: CurrentUser, now: float) -> str:
        rows = self.alarms.active(self._visible(user))
        if not rows:
            return "Ingen aktive alarmer."
        lines = [f"- {clean(a['message'])} (prioritet {a['priority']}, {STATE_TXT.get(a['state'], a['state'])}, "
                 f"opstod {ago(a.get('raised_at'), now)})" for a in rows[:MAX_ALARMS]]
        if len(rows) > MAX_ALARMS:
            lines.append(f"- … og {len(rows) - MAX_ALARMS} mere")
        return f"{len(rows)} aktive alarmer:\n" + "\n".join(lines)

    def alarm(self, user: CurrentUser, key: str, now: float) -> tuple[str, str | None, str]:
        """Én alarm (som brugeren må se) → (tekst, tag, søgeord til manualen)."""
        keys = self.alarms.visible_keys(self._visible(user))
        if keys is not None and key not in keys:
            return "", None, ""
        a = self.alarms.state.get(key)
        if not a:
            return "Alarmen er ikke længere aktiv.", None, ""
        kind = {"tag": "grænsealarm på et tag", "comm": "kommunikationsalarm for en PLC", "symbol": "afvigelse i et symbol",
                "sys": "alarm om SCADA-serveren selv"}.get(a.get("kind", ""), a.get("kind", ""))
        lines = [f"Tekst: {clean(a['message'])}", f"Type: {kind}", f"Niveau: {a['level']}, prioritet {a['priority']}",
                 f"Tilstand: {STATE_TXT.get(a['state'], a['state'])}", f"Opstod: {ago(a.get('raised_at'), now)}"]
        if a.get("value") is not None:
            lines.append(f"Værdi da den opstod: {clean(a['value'], 40)}")
        if a.get("acked_by"):
            lines.append(f"Kvitteret af {clean(a['acked_by'], 40)} {ago(a.get('acked_at'), now)}")
        return "\n".join(lines), a.get("tag") or None, f"{ALARM_HINTS.get(a.get('kind', ''), '')} {clean(a['message'], 120)}"

    def tag_values(self, names: list[str], now: float) -> str:
        lines = []
        for n in names:
            try:
                t = self.tags.get(n)
            except Exception:   # noqa: BLE001 — et ukendt tag springes over
                continue
            live = self.cache.get(n)
            q = "" if live.quality == "good" else f", kvalitet {live.quality}"
            desc = f" — {clean(t['description'], 80)}" if t.get("description") else ""
            limits = [f"{k.replace('alarm_', '').upper()} {t[k]}" for k in ("alarm_hh", "alarm_h", "alarm_l", "alarm_ll")
                      if t.get(k) is not None]
            lim = f" (alarmgrænser: {', '.join(limits)})" if limits else ""
            lines.append(f"- {clean(n, 60)}{desc}: {fmt_value(live.value, t.get('unit') or '', t.get('decimals'))}{q}, "
                         f"målt {ago(live.ts, now)}{lim}")
        return "\n".join(lines)

    def trend_summary(self, names: list[str], span: float, label: str, now: float) -> str:
        lines = []
        for n in names:
            try:
                rows = self.trend_db.series(n, now - span, now, max(60.0, span / 60))
            except Exception:   # noqa: BLE001 — ingen historik for tagget
                rows = []
            vals = [r for r in rows if r[1] is not None]
            if not vals:
                lines.append(f"- {clean(n, 60)}: ingen historik {label}")
                continue
            unit = ""
            try:
                unit = self.tags.get(n).get("unit") or ""
            except Exception:   # noqa: BLE001
                pass
            mn = min((r[2] if r[2] is not None else r[1] for r in vals), default=vals[0][1])
            mx = max((r[3] if r[3] is not None else r[1] for r in vals), default=vals[0][1])
            mean = sum(r[1] for r in vals) / len(vals)
            first, last = vals[0][1], vals[-1][1]
            trend = "stigende" if last - first > (mx - mn) * 0.2 else "faldende" if first - last > (mx - mn) * 0.2 else "nogenlunde stabil"
            gaps = sum(1 for r in rows if r[1] is None)
            gap = f", {gaps} huller i data" if gaps else ""
            lines.append(f"- {clean(n, 60)} {label}: min {fmt_value(mn, unit)}, max {fmt_value(mx, unit)}, "
                         f"middel {fmt_value(mean, unit)}, fra {fmt_value(first, unit)} til {fmt_value(last, unit)} ({trend}{gap})")
        return "\n".join(lines)

    def drawing_overview(self, user: CurrentUser, drawing_id: str) -> tuple[str, str]:
        if not self.scope.can_see_drawing(user, drawing_id):
            return "", ""
        try:
            d = self.drawings.get(drawing_id)
            syms = self.symbols.list_symbols(drawing_id)
            bindings = self.drawings.effective_bindings(drawing_id)
        except Exception:   # noqa: BLE001 — ukendt eller ulæselig tegning
            return "", ""
        bound: dict[str, set[str]] = {}
        for b in bindings:
            for t in ((b.get("tag"),) if b.get("tag") and not str(b["tag"]).startswith("@") else ()):
                bound.setdefault(b.get("element", ""), set()).add(t)
        cfg_tags = {e: config_tags(c) for e, c in self.symbols.configs(drawing_id).items()}
        known = {s["element"] for s in syms}
        # Elementer med bindinger, men uden navn/symboltype, er også en del af anlægget
        syms = syms + [{"element": e, "name": "", "type": "", "configured": True} for e in sorted(bound) if e and e not in known]
        lines = []
        for s in syms[:MAX_SYMBOLS]:
            tags = sorted(bound.get(s["element"], set()) | set(cfg_tags.get(s["element"], [])))
            kind = f" ({clean(s['type'], 30)})" if s.get("type") else ""
            tg = f": {', '.join(clean(t, 40) for t in tags[:4])}" if tags else (": ikke sat op" if not s["configured"] else "")
            lines.append(f"- {clean(s['name'] or s['element'], 50)}{kind}{tg}")
        if len(syms) > MAX_SYMBOLS:
            lines.append(f"- … og {len(syms) - MAX_SYMBOLS} symboler mere")
        head = f"Tegningen '{clean(d['name'], 60)}' har {len(syms)} symboler/elementer"
        return head + (":\n" + "\n".join(lines) if lines else "."), d["name"]

    def manual_hits(self, query: str) -> list[tuple[str, str, dict[str, str]]]:
        return [(s.source, excerpt(s.text, query, MANUAL_CHARS), {"label": s.source, "href": s.href})
                for s, _ in self.manual.search(query, MANUAL_HITS)]

    # ------------------------------------------------------------------ udvælgelse
    def mentioned_tags(self, user: CurrentUser, question: str) -> list[str]:
        """Tag-navne, der står i spørgsmålet (hele ord, uden hensyn til store/små bogstaver) — kun synlige tags."""
        visible = self._visible(user)
        q = question.lower()
        found = []
        for t in self.tags.list():
            name = t["name"]
            if visible is not None and name not in visible:
                continue
            if len(name) >= 2 and re.search(rf"(?<![\w.]){re.escape(name.lower())}(?![\w])", q):
                found.append(name)
        return found[:MAX_TAGS]

    def gather(self, user: CurrentUser, question: str, ctx: Context, now: float | None = None) -> Gathered:
        now = time.time() if now is None else now
        g = Gathered()
        q = question.lower()
        visible = self._visible(user)
        page = PAGES.get(ctx.page, "")
        if page:
            g.add("Side", f"Brugeren står på siden {page}.", "side")
        alarm_tag = None
        alarm_query = ""
        if ctx.alarm:
            text, alarm_tag, alarm_query = self.alarm(user, ctx.alarm, now)
            g.add("Alarmen", text, "alarm", {"label": "Alarmer", "href": "#alarms"})
        elif ctx.page == "alarms" or "alarm" in q:
            g.add("Aktive alarmer", self.active_alarms(user, now), "aktive_alarmer", {"label": "Alarmer", "href": "#alarms"})
        names = [t for t in ctx.tags if visible is None or t in visible][:MAX_TAGS]
        if alarm_tag and (visible is None or alarm_tag in visible) and alarm_tag not in names:
            names.insert(0, alarm_tag)
        for t in self.mentioned_tags(user, question):
            if t not in names:
                names.append(t)
        names = names[:MAX_TAGS]
        if names:
            g.add("Tags lige nu", self.tag_values(names, now), "tag_vaerdi")
            wants_trend = ctx.page == "trends" or alarm_tag is not None or any(
                w in q for w in ("trend", "forløb", "historik", "udvikling", "steget", "faldet", "seneste", "døgn", "uge", "time"))
            trendable = self._trendable(user, visible)
            tnames = [n for n in names if trendable is None or n in trendable]
            if wants_trend and tnames:
                span, label = period_of(question)
                g.add("Trend", self.trend_summary(tnames, span, label, now), "trend_resume", {"label": "Trends", "href": "#trends"})
        if ctx.drawing and (ctx.page in ("overview", "draw", "editor") or any(w in q for w in ("tegning", "symbol", "anlæg"))):
            text, name = self.drawing_overview(user, ctx.drawing)
            g.add("Tegningen", text, "tegning_oversigt")
        # Ved "Forklar" er spørgsmålet altid det samme — alarmens type og tekst siger, hvad der skal slås op
        query = alarm_query or question
        for title, text, src in self.manual_hits(query):
            g.add(title, text, "soeg_manual", src)
        return g
