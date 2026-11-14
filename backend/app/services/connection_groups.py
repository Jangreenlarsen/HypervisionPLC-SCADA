"""Forbindelsesgrupper (v6.1.0, PLAN.md › Flow-model): hvordan tegningens forbindelser (rør, bøjninger, T-stykker …) viser det
beregnede flow (flow_calc.py).

- Alle forbindelser hører fra start til **standardgruppen** *Alle forbindelser*, som viser **løbelys** efter flowet (retning fra
  fortegnet, hastighed fra mængden).
- I Tegn kan man vælge forbindelser og lægge dem i en **egen gruppe** med andre animationer: løbelys, farve efter flow, blink ved et
  flow over/under en grænse, en fast farve — eller ingen. En forbindelse hører til én gruppe ad gangen.
- Animationerne bliver almindelige bindinger (kilden `flow:<tegning>:<element>`), så Overview tegner dem med den eksisterende
  motor. Standardgruppen bruges kun på tegninger med mindst én pumpe, og aldrig på en forbindelse, der allerede har en animation
  af samme slags fra en binding, et symbol eller en symbolgruppe.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ..storage.db import Database
from .bindings import _color
from .errors import ServiceError
from .flow_calc import flow_tag, ports_tag
from .flow_defs import PIPE_SYMBOL_TYPES, merged, piece_types

log = logging.getLogger("scada.connection_groups")

MAX_GROUPS = 50
MAX_MEMBERS = 2000
MAX_ANIMS = 4
DEFAULT_ANIMS: list[dict[str, Any]] = [{"type": "flow"}]
_NAME = re.compile(r"^[^\x00-\x1f]{1,60}\Z")


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Limit(_M):
    value: float = Field(ge=0, le=1_000_000)
    color: str          # "" = som tegnet (v6.12.0: Til "som tegnet" med en Fra-farve)

    _c = field_validator("color")(lambda cls, v: v if v == "" else _color(v))


class ConnAnim(_M):
    """Én animation på gruppens forbindelser, styret af flowet (l/min)."""
    type: Literal["flow", "color", "blink", "fixed"]
    # løbelys: fart (tegningens enheder/s) ved fuldt flow; `full` = l/min ved fuld fart (0 = tegningens største pumpe)
    light: str = "#8fc8ea"
    base: str = "#555555"
    speed: float = Field(default=60, ge=5, le=500)
    dash: float = Field(default=12, ge=2, le=200)
    full: float = Field(default=0, ge=0, le=65535)
    # (v6.12.0) løbelys: forbindelsens farve, når der intet flow er ("" = som tegnet)
    stopped: str = ""
    # farve efter flow: under den første grænse `off` ("" = som tegnet, v6.12.0); ellers grænsens farve (stigende)
    off: str = "#9e9e9e"
    limits: list[Limit] = Field(default_factory=list, max_length=8)
    # blink: når flowet er mindst `at_least` — eller højst `at_most` (fx 0 = intet flow)
    at_least: float | None = Field(default=None, ge=0, le=1_000_000)
    at_most: float | None = Field(default=None, ge=0, le=1_000_000)
    rate: Literal["slow", "normal", "fast"] = "normal"
    # fast farve
    color: str = "#1e88e5"

    _c = field_validator("light", "base", "color")(lambda cls, v: _color(v))
    _c_opt = field_validator("off", "stopped")(lambda cls, v: v if v == "" else _color(v))

    @field_validator("limits")
    @classmethod
    def _sorted(cls, v: list[Limit]) -> list[Limit]:
        if [x.value for x in v] != sorted(x.value for x in v):
            raise ValueError("grænserne skal være sorteret stigende")
        return v


def clean_anims(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or len(raw) > MAX_ANIMS:
        raise ServiceError(400, f"Animationerne skal være en liste med højst {MAX_ANIMS}")
    out = []
    for i, a in enumerate(raw, 1):
        try:
            m = ConnAnim.model_validate(a)
        except ValidationError as exc:
            e = exc.errors()[0]
            raise ServiceError(400, f"Animation {i}: {'.'.join(str(p) for p in e['loc'])}: {e['msg']}") from None
        if m.type == "blink" and (m.at_least is None) == (m.at_most is None):
            raise ServiceError(400, f"Animation {i}: blink kræver én grænse (mindst eller højst)")
        out.append(m.model_dump())
    return out


def connections_in(svg: str, pieces: frozenset[str] | None = None) -> dict[str, str]:
    """Forbindelserne i tegningen: {id: navn} — rør (`data-hv-pipe`) og rørstykker (bøjning, T-stykke …)."""
    return {k: v[0] for k, v in connection_kinds(svg, pieces).items()}


def connection_kinds(svg: str, pieces: frozenset[str] | None = None) -> dict[str, tuple[str, bool]]:
    """{id: (navn, er et rør)} — et rørstykke (symbol) får flowet uden fortegn; retningen pr. delstreg kommer fra dets flow pr.
    punkt (`flowp:…`, v6.3.0). `pieces`: rørstykke-typerne (de indbyggede + typer med rollen rørstykke)."""
    from defusedxml.ElementTree import fromstring
    pieces = PIPE_SYMBOL_TYPES if pieces is None else pieces
    out: dict[str, tuple[str, bool]] = {}
    for el in fromstring(svg).iter():
        eid = el.get("id") if isinstance(el.tag, str) else None
        pipe = eid is not None and el.get("data-hv-pipe") is not None
        if eid and (pipe or (el.get("data-hv-type") or "") in pieces):
            out[eid] = (el.get("data-hv-name") or "", pipe)
    return out


def clean_name(raw: Any) -> str:
    """En egen gruppes navn: højst 60 tegn uden kontroltegn, ikke standardgruppens."""
    name = " ".join(str(raw or "").split())
    if not _NAME.match(name) or name.casefold() == "alle forbindelser":
        raise ServiceError(400, "Giv gruppen et navn (højst 60 tegn, ikke 'Alle forbindelser')")
    return name


def group_bindings(drawing_id: str, conns: dict[str, tuple[str, bool]], rows: list[dict[str, Any]], full_default: float,
                   taken: set[tuple[str, str]], has_pump: bool) -> list[dict[str, Any]]:
    """Gruppernes animationer som bindinger. `taken`: (element, anim), der allerede er animeret af noget andet."""
    default = next((r for r in rows if r["is_default"]), None)
    owner: dict[str, dict[str, Any]] = {}
    for r in rows:
        if not r["is_default"]:
            for m in r["members"]:
                if m in conns:
                    owner.setdefault(m, r)
    out: list[dict[str, Any]] = []
    for el, (_, is_pipe) in sorted(conns.items()):
        g = owner.get(el)
        if g is None and not has_pump:
            continue          # standardgruppen kun på tegninger med en pumpe
        anims = (g or default or {"anims": DEFAULT_ANIMS})["anims"]
        gid, gname = (g["id"], g["name"]) if g else ((default or {}).get("id"), "Alle forbindelser")
        for i, a in enumerate(anims):
            a = {**ConnAnim.model_validate(a).model_dump()}
            tag = flow_tag(drawing_id, el)
            if a["type"] == "flow":
                # et rør har flowet med fortegn (retning); et rørstykke mængden + retningen pr. punkt (port_tag, v6.3.0)
                anim, params = "flow", {"mode": "signed" if is_pipe else "onoff", "base": a["base"], "light": a["light"], "speed": a["speed"],
                                        "dash": a["dash"], "flow_max": a["full"] or full_default}
                if a["stopped"]:
                    params["stopped"] = a["stopped"]
                # v6.13.0 (Jan: synkroniseringsfejl i overgangen mellem rør, T-stykker og bøjninger): alle forbindelsers løbelys er
                # ét sammenhængende forløb på tværs af elementerne (hver har sit eget flow-tag); retningen kommer fra flowet
                params["chain"] = "conn"
                if not is_pipe:
                    params["port_tag"] = ports_tag(drawing_id, el)
            elif a["type"] == "color":
                anim, params = "stroke", {"abs": True, "off": a["off"], "on": a["off"],
                                          "thresholds": [{"value": x["value"], "color": x["color"]} for x in a["limits"]]}
            elif a["type"] == "blink":
                anim, params = "blink", {"abs": True, "speed": a["rate"],
                                         **({"at_least": a["at_least"]} if a["at_least"] is not None else {"at_most": a["at_most"]})}
            else:
                anim, params, tag = "stroke", {"on": a["color"], "off": a["color"]}, "@on"
            if (el, anim) in taken:
                continue
            out.append({"element": el, "position": 3000 + i, "tag": tag, "anim": anim, "params": params, "source": "conn-group",
                        "conn_group": gid, "conn_group_name": gname})
    return out


class ConnectionGroupService:
    def __init__(self, db: Database, drawings: Any):
        self.db = db
        self.drawings = drawings

    def _conns(self, drawing_id: str) -> dict[str, str]:
        self.drawings._require(drawing_id)
        return connections_in(self.drawings.svg(drawing_id), piece_types(merged(self.db.list_symbol_flow())))

    def list(self, drawing_id: str) -> dict[str, Any]:
        conns = self._conns(drawing_id)
        rows = self.db.list_connection_groups(drawing_id)
        default = next((r for r in rows if r["is_default"]), None)
        groups = [{"id": r["id"], "name": r["name"], "members": [m for m in r["members"] if m in conns],
                   "missing": [m for m in r["members"] if m not in conns], "anims": r["anims"]} for r in rows if not r["is_default"]]
        grouped = {m for g in groups for m in g["members"]}
        return {"default": {"anims": default["anims"] if default else DEFAULT_ANIMS,
                            "members": sorted(c for c in conns if c not in grouped)},
                "groups": groups, "connections": [{"id": k, "name": v} for k, v in sorted(conns.items())]}

    def _members(self, drawing_id: str, raw: Any) -> list[str]:
        if not isinstance(raw, list) or len(raw) > MAX_MEMBERS or not all(isinstance(m, str) and 0 < len(m) <= 120 for m in raw):
            raise ServiceError(400, "Medlemmerne skal være en liste af element-id'er")
        conns = self._conns(drawing_id)
        if bad := [m for m in raw if m not in conns]:
            raise ServiceError(400, f"'{bad[0]}' er ikke en forbindelse i tegningen (kun rør og rørstykker kan være med)")
        return list(dict.fromkeys(raw))

    def _name(self, raw: Any) -> str:
        return clean_name(raw)

    def create(self, actor: Any, drawing_id: str, body: dict[str, Any]) -> dict[str, Any]:
        members = self._members(drawing_id, body.get("members", []))
        name = self._name(body.get("name"))
        anims = clean_anims(body.get("anims", DEFAULT_ANIMS))
        if sum(1 for r in self.db.list_connection_groups(drawing_id) if not r["is_default"]) >= MAX_GROUPS:
            raise ServiceError(400, f"Højst {MAX_GROUPS} forbindelsesgrupper pr. tegning")
        gid = self.db.write_connection_group(drawing_id, None, name, members, anims, actor.username)
        if gid is None:
            raise ServiceError(409, f"Gruppen '{name}' findes allerede")
        log.info("Forbindelsesgruppe '%s' oprettet på %s af %s (%d forbindelser)", name, drawing_id, actor.username, len(members))
        return self.get(drawing_id, gid)

    def update(self, actor: Any, drawing_id: str, gid: int, body: dict[str, Any]) -> dict[str, Any]:
        cur = self.get(drawing_id, gid)
        members = self._members(drawing_id, body["members"]) if "members" in body else cur["members"]
        name = self._name(body["name"]) if "name" in body else cur["name"]
        anims = clean_anims(body["anims"]) if "anims" in body else cur["anims"]
        if self.db.write_connection_group(drawing_id, gid, name, members, anims, actor.username) is None:
            raise ServiceError(409, f"Gruppen '{name}' findes allerede")
        return self.get(drawing_id, gid)

    def set_default(self, actor: Any, drawing_id: str, body: dict[str, Any]) -> dict[str, Any]:
        self.drawings._require(drawing_id)
        anims = clean_anims(body.get("anims"))
        self.db.set_default_connection_group(drawing_id, anims, actor.username)
        return {"anims": anims}

    def get(self, drawing_id: str, gid: int) -> dict[str, Any]:
        r = next((r for r in self.db.list_connection_groups(drawing_id) if r["id"] == gid and not r["is_default"]), None)
        if r is None:
            raise ServiceError(404, "Forbindelsesgruppen findes ikke")
        return {"id": r["id"], "name": r["name"], "members": r["members"], "anims": r["anims"]}

    def delete(self, drawing_id: str, gid: int) -> None:
        self.get(drawing_id, gid)
        self.db.delete_connection_group(drawing_id, gid)
