# SPDX-License-Identifier: AGPL-3.0-or-later
"""Sæt demo-varmeanlægget op i en HypervisionPLC SCADA via dens REST API.

Brug:
  SCADA_USER=... SCADA_PASS=... PLC_USER=... PLC_PASS=... \\
    python demo/varme-plc/scada_setup.py https://scada.example [--cafile=server.pem] [--plc=http://10.1.1.34] [--drawing=varme]

  --cafile: serverens eget (selvsignerede) certifikat som eneste CA — forbindelsen tjekkes stadig, også værtsnavnet.
  --dry-run=fil.svg: skriv kun den nye SVG, gem intet. --skip-plc: spring PLC og tags over. --only-configs: lad tegningen være og sæt kun tags og symboler op.

Trin (alle kan køres igen, intet dobbelt):
  1. PLC'en `demo` oprettes eller opdateres.
  2. Tags oprettes eller opdateres ud fra TAGS herunder: enheder, skrivbare setpunkter og kommandoer, historik, energi, alarmer.
  3. Tegningen får en ny version: højere lærred, et infofelt og et betjeningspanel med omskiftere, trykknapper,
     setpunkter og vippekontakter. Symbolerne genereres af frontendens symbolbibliotek (`syms.json`, se `--symbols`).
  4. Alle symboler bindes til demo-PLC'ens tags (symbolkonfiguration som i Tegn › Opsæt symbol).

Adgangskoder læses fra miljøet og skrives aldrig ud.
"""
from __future__ import annotations

import http.cookiejar
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import Any

HERE = Path(__file__).resolve().parent
PLC_KEY = "demo"

# ------------------------------------------------------------------ tags
# (navn, program, variabel, enhed, decimaler, ekstra felter)
T = "°C"
TAGS: list[tuple[str, int, str, str, int | None, dict[str, Any]]] = [
    # Logic1 — styring
    ("SMS_TXT", 1, "SMS_TXT", "", None, {"description": "Driftstilstand (tekst)"}),
    ("SMS", 1, "SMS", "", 0, {"description": "Driftstilstand (kode)"}),
    ("cmd_mode", 1, "cmd_mode", "", 0, {"description": "Driftsform: 0 Fra, 1 Auto, 2 Sommer, 3 Kun pille, 4 Manuel",
                                        "writable": True, "min": 0, "max": 4, "confirm_write": True}),
    ("cmd_kvitter", 1, "cmd_kvitter", "", None, {"description": "Kvittér alarmer i PLC'en", "writable": True, "confirm_write": False}),
    *[(f"man_{n}", 1, f"man_{n}", "", None, {"description": f"Manuel: {d}", "writable": True, "confirm_write": False})
      for n, d in (("P1", "pumpe 1"), ("P2", "pumpe 2"), ("P3", "pumpe 3"), ("P4", "pumpe 4"),
                   ("MVS", "motorventiler AB-B"), ("pille", "pillefyr"), ("VP", "varmepumpe"))],
    ("sp_rum", 1, "sp_rum", T, 1, {"description": "Setpunkt rumtemperatur", "writable": True, "min": 15, "max": 25, "confirm_write": True}),
    ("sp_kurve", 1, "sp_kurve", "", 1, {"description": "Vejrkurvens hældning", "writable": True, "min": 0.2, "max": 3, "confirm_write": True}),
    ("sp_tank_min", 1, "sp_tank_min", T, 0, {"description": "Tankens minimumtemperatur (start af varmekilde)", "writable": True,
                                            "min": 30, "max": 70, "confirm_write": True}),
    ("STF_SP", 1, "STF_SP", T, 1, {"description": "Beregnet fremløbssetpunkt", "trend": True}),
    *[(f"PS{i}", 1, f"PS{i}", "", None, {"description": f"Pumpe {i} kører"}) for i in range(1, 5)],
    ("AL_P1", 1, "AL_P1", "", None, {"description": "Pumpefejl P1 (husets kreds)", "alarm_on": "true"}),
    ("AL_P2", 1, "AL_P2", "", None, {"description": "Pumpefejl P2 (pillefyr)", "alarm_on": "true"}),
    ("AL_P3", 1, "AL_P3", "", None, {"description": "Pumpefejl P3 (varmepumpe)", "alarm_on": "true"}),
    ("AL_P4", 1, "AL_P4", "", None, {"description": "Pumpefejl P4 (Laddomat)", "alarm_on": "true"}),
    ("AL_VP", 1, "AL_VP", "", None, {"description": "Varmepumpefejl", "alarm_on": "true"}),
    ("AL_PILLE", 1, "AL_PILLE", "", None, {"description": "Pillefyr tænder ikke", "alarm_on": "true"}),
    ("AL_TRYK_LAV", 1, "AL_TRYK_LAV", "", None, {"description": "Lavt systemtryk (< 1,0 bar)", "alarm_on": "true"}),
    ("AL_TRYK_HOEJ", 1, "AL_TRYK_HOEJ", "", None, {"description": "Højt systemtryk (> 2,4 bar)", "alarm_on": "true"}),
    ("AL_FF_TEMP", 1, "AL_FF_TEMP", "", None, {"description": "Overtemperatur i brændefyret (> 95 °C)", "alarm_on": "true"}),
    ("AL_TANK_KOLD", 1, "AL_TANK_KOLD", "", None, {"description": "Akkumuleringstanken er kold (< 35 °C)", "alarm_on": "true"}),
    ("ALARMER", 1, "ALARMER", "", 0, {"description": "Antal aktive alarmer i PLC'en"}),
    # Logic2 — brændefyr og pillefyr
    ("cmd_fyr_op", 2, "cmd_fyr_op", "", None, {"description": "Læg 15 kg brænde i brændefyret", "writable": True, "confirm_write": False}),
    ("FFTF", 2, "FFTF", T, 1, {"description": "Brændefyr fremløb", "trend": True}),
    ("FFTR", 2, "FFTR", T, 1, {"description": "Brændefyr retur", "trend": True}),
    ("FF_KW", 2, "FF_KW", "kW", 1, {"description": "Brændefyrets ydelse", "trend": True}),
    ("FF_KG", 2, "FF_KG", "kg", 1, {"description": "Brænde tilbage i fyret"}),
    ("LADDOMAT", 2, "LADDOMAT", "", None, {"description": "Laddomat åben mod tanken"}),
    ("PFTF", 2, "PFTF", T, 1, {"description": "Pillefyr fremløb", "trend": True}),
    ("PFTR", 2, "PFTR", T, 1, {"description": "Pillefyr retur", "trend": True}),
    ("PILLE_TXT", 2, "PILLE_TXT", "", None, {"description": "Pillefyrets status"}),
    ("PILLE_KW", 2, "PILLE_KW", "kW", 1, {"description": "Pillefyrets ydelse", "trend": True}),
    ("PILLE_KG", 2, "PILLE_KG", "kg", 1, {"description": "Piller brugt"}),
    ("PILLE_STARTS", 2, "PILLE_STARTS", "", 0, {"description": "Antal starter, pillefyr"}),
    ("E_FF", 2, "E_FF", "kWh", 1, {"description": "Energi fra brændefyret", "trend": True, "energy": "counter"}),
    ("E_PILLE", 2, "E_PILLE", "kWh", 1, {"description": "Energi fra pillefyret", "trend": True, "energy": "counter"}),
    # Logic3 — tank og hus
    *[(f"ATT{i}", 3, f"ATT{i}", T, 1, {"description": f"Akkumuleringstank lag {i} ({'top' if i == 1 else 'bund' if i == 6 else 'midt'})",
                                       "trend": True}) for i in range(1, 7)],
    ("ATF", 3, "ATF", T, 1, {"description": "Fremløb fra tankens top"}),
    ("TS", 3, "TS", "%", 0, {"description": "Tankens ladning", "trend": True}),
    ("STF", 3, "STF", T, 1, {"description": "Husets fremløb", "trend": True}),
    ("STR", 3, "STR", T, 1, {"description": "Husets retur", "trend": True}),
    ("MVT2", 3, "MVT2", T, 1, {"description": "Temperatur ved motorventilerne"}),
    ("FMTR", 3, "FMTR", "L/min", 1, {"description": "Flow i husets kreds", "trend": True}),
    ("T_RUM", 3, "T_RUM", T, 1, {"description": "Rumtemperatur", "trend": True, "alarm_l": 18}),
    ("Q_HUS", 3, "Q_HUS", "kW", 1, {"description": "Husets varmeforbrug", "trend": True}),
    ("E_HUS", 3, "E_HUS", "kWh", 1, {"description": "Energi til huset", "trend": True, "energy": "counter"}),
    ("MVS1_TXT", 3, "MVS1_TXT", "", None, {"description": "Motorventil MVS1"}),
    ("MVS2_TXT", 3, "MVS2_TXT", "", None, {"description": "Motorventil MVS2"}),
    ("MVS1_POS", 3, "MVS1_POS", "%", 0, {"description": "Motorventil MVS1 position (0 = AB-A, 100 = AB-B)"}),
    ("MVS2_POS", 3, "MVS2_POS", "%", 0, {"description": "Motorventil MVS2 position (0 = AB-A, 100 = AB-B)"}),
    ("cmd_mvs1", 3, "cmd_mvs1", "", 0, {"description": "Håndbetjening MVS1: 0 Auto, 1 AB-A, 2 AB-B", "writable": True,
                                         "min": 0, "max": 2, "confirm_write": True}),
    ("cmd_mvs2", 3, "cmd_mvs2", "", 0, {"description": "Håndbetjening MVS2: 0 Auto, 1 AB-A, 2 AB-B", "writable": True,
                                         "min": 0, "max": 2, "confirm_write": True}),
    # Logic4 — system, demo, varmepumpe
    ("FFS_TXT", 4, "FFS_TXT", "", None, {"description": "Brændefyrets status"}),
    ("sp_speed", 4, "sp_speed", "×", 0, {"description": "Tidsfaktor (1 = realtid, 60 = en time pr. minut)", "writable": True,
                                         "min": 1, "max": 120, "confirm_write": False}),
    ("cmd_scenarie", 4, "cmd_scenarie", "", 0, {"description": "Scenarie: 0 Normal, 1 Vinternat, 2 Sommer, 3 Lækage, 4 Pumpefejl P1",
                                                "writable": True, "min": 0, "max": 4, "confirm_write": True}),
    ("cmd_efterfyld", 4, "cmd_efterfyld", "", None, {"description": "Efterfyld anlægget til 1,2 bar", "writable": True, "confirm_write": True}),
    *[(f"f_{n}", 4, f"f_{n}", "", None, {"description": f"Demo-fejl: {d}", "writable": True, "confirm_write": False})
      for n, d in (("P1", "pumpe 1"), ("P2", "pumpe 2"), ("P3", "pumpe 3"), ("P4", "pumpe 4 (overophedning)"),
                   ("pille", "pillefyr tænder ikke"), ("vp", "varmepumpe"), ("laek", "lækage"))],
    ("ST", 4, "ST", "bar", 2, {"description": "Systemtryk", "trend": True}),
    ("SV_AABEN", 4, "SV_AABEN", "", None, {"description": "Sikkerhedsventil åben", "alarm_on": "true"}),
    ("T_UDE", 4, "T_UDE", T, 1, {"description": "Udetemperatur", "trend": True}),
    ("KLOKKE", 4, "KLOKKE", "h", 1, {"description": "Simuleret klokkeslæt"}),
    ("DAG", 4, "DAG", "", 0, {"description": "Simuleret dag"}),
    ("VP_RUN", 4, "VP_RUN", "", None, {"description": "Varmepumpen kører"}),
    ("VPTF", 4, "VPTF", T, 1, {"description": "Varmepumpe fremløb", "trend": True}),
    ("VPTR", 4, "VPTR", T, 1, {"description": "Varmepumpe retur", "trend": True}),
    ("VP_KW", 4, "VP_KW", "kW", 1, {"description": "Varmepumpens varmeydelse", "trend": True}),
    ("VP_EL", 4, "VP_EL", "kW", 2, {"description": "Varmepumpens elforbrug", "trend": True}),
    ("VP_COP", 4, "VP_COP", "", 1, {"description": "Varmepumpens COP"}),
    ("E_VP", 4, "E_VP", "kWh", 1, {"description": "Energi fra varmepumpen", "trend": True, "energy": "counter"}),
    ("E_VP_EL", 4, "E_VP_EL", "kWh", 1, {"description": "Varmepumpens elforbrug", "trend": True, "energy": "counter"}),
]


# ------------------------------------------------------------------ HTTP
class Api:
    def __init__(self, base: str, cafile: str | None) -> None:
        self.base = base.rstrip("/")
        ctx = ssl.create_default_context(cafile=cafile) if cafile else ssl.create_default_context()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
                                                  urllib.request.HTTPSHandler(context=ctx))

    def req(self, method: str, path: str, data: Any = None, ok404: bool = False) -> Any:
        raw = json.dumps(data).encode() if data is not None else None
        r = urllib.request.Request(self.base + path, data=raw, method=method,
                                   headers={"Content-Type": "application/json", "Accept": "application/json"})
        try:
            with self.opener.open(r, timeout=60) as resp:
                body = resp.read()
                ctype = resp.headers.get("Content-Type", "")
                if not body:
                    return None
                return json.loads(body) if "json" in ctype else body.decode()
        except urllib.error.HTTPError as e:
            if ok404 and e.code == 404:
                return None
            raise SystemExit(f"{method} {path} → HTTP {e.code}: {e.read().decode(errors='replace')[:500]}")


# ------------------------------------------------------------------ 1-2: PLC og tags
def setup_plc(api: Api, plc_url: str) -> None:
    user, pw = os.environ.get("PLC_USER", ""), os.environ.get("PLC_PASS", "")
    if not user or not pw:
        raise SystemExit("Sæt PLC_USER og PLC_PASS (demo-PLC'ens API-bruger)")
    body = {"name": "Demo-PLC varmeanlæg", "base_url": plc_url, "username": user, "password": pw,
            "enabled": True, "sse_enabled": True}
    if api.req("GET", f"/api/plcs/{PLC_KEY}", ok404=True) is None:
        api.req("POST", "/api/plcs", {"key": PLC_KEY, **body})
        print(f"PLC '{PLC_KEY}' oprettet ({plc_url})")
    else:
        api.req("PATCH", f"/api/plcs/{PLC_KEY}", body)
        print(f"PLC '{PLC_KEY}' opdateret ({plc_url})")


def setup_tags(api: Api) -> None:
    existing = {t["name"]: t for t in api.req("GET", "/api/tags")}
    made = changed = 0
    for name, prog, var, unit, dec, extra in TAGS:
        data = {"source": f"{PLC_KEY}:logic:{prog}:{var}", "unit": unit, "decimals": dec,
                "writable": False, "confirm_write": True, "trend": False, "energy": None, "alarm_on": None,
                "description": "", **extra}
        if name not in existing:
            api.req("POST", "/api/tags", {"name": name, **data})
            made += 1
        else:
            if not existing[name]["source"].startswith(f"{PLC_KEY}:"):
                raise SystemExit(f"Tagget '{name}' findes allerede og hører til en anden PLC — omdøb det først")
            api.req("PATCH", f"/api/tags/{name}", data)
            changed += 1
    print(f"Tags: {made} oprettet, {changed} opdateret")


# ------------------------------------------------------------------ 3: tegningen
H_OLD, H_NEW = 850, 1110
PANEL_Y = 862


class Svg:
    """Byg nye symboler som editoren gør det (scada-core.js buildSymbolNode): id, data-hv-type/-name, dele → data-hv-pid."""

    def __init__(self, syms: dict[str, str]) -> None:
        self.syms = syms
        self.parts: list[str] = []

    def symbol(self, lib: str, elem_id: str, name: str, x: float, y: float, scale: float = 1.0,
               text: str | None = None, typ: str | None = None) -> str:
        frag = self.syms[lib]
        if lib.startswith("omskifter_"):
            frag = selector_labels_out(frag)
        if text is not None:   # skiltets tekst (trykknappen)
            frag = re.sub(r'(id="tekst"[^>]*>)[^<]*<', lambda m: m.group(1) + esc(text) + "<", frag, count=1)
        frag = re.sub(r' id="([A-Za-z0-9_]+)"', lambda m: f' data-hv-pid="{m.group(1)}" id="{elem_id}_{m.group(1)}"', frag)
        tr = f"translate({x} {y})" + (f" scale({scale})" if scale != 1 else "")
        frag = re.sub(r"^<g", f'<g data-hv-name="{esc(name)}" data-hv-type="{typ or lib}" id="{elem_id}" transform="{tr}"', frag, count=1)
        self.parts.append(frag)
        return elem_id

    def label(self, elem_id: str, x: float, y: float, txt: str, size: int = 13, weight: int = 600, anchor: str = "start") -> None:
        self.parts.append(f'<text id="{elem_id}" x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="#333" '
                          f'font-family="Segoe UI, Arial" text-anchor="{anchor}">{esc(txt)}</text>')

    def frame(self, elem_id: str, x: float, y: float, w: float, h: float, title: str) -> None:
        self.parts.append(f'<rect id="{elem_id}" x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="#f4f4f4" stroke="#999" stroke-width="1.5"/>')
        self.label(f"{elem_id}_t", x + 10, y + 20, title, 15, 700)


def selector_labels_out(frag: str) -> str:
    """Omskifterens positionsnavne flyttes ud til siden (højre-/venstrestillet), så lange navne ikke dækker grebet."""
    import math

    def move(m: re.Match[str]) -> str:
        x, y = float(m.group(1)), float(m.group(2)) - 5
        a = math.atan2(x - 70, 70 - y)
        side = math.sin(a)
        r = 50 if abs(side) < 0.2 else 42
        nx, ny = 70 + r * side, 70 - r * math.cos(a) + 5
        anchor = "middle" if abs(side) < 0.2 else ("end" if side < 0 else "start")
        return f'<text x="{nx:.0f}" y="{ny:.0f}" font-size="13" font-weight="600" text-anchor="{anchor}"'
    return re.sub(r'<text x="([\d.]+)" y="([\d.]+)" font-size="13" font-weight="600" text-anchor="middle"', move, frag)


def esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# element-id → (tag, bibliotek) for panelets betjeningssymboler; udfyldes af build_panel
PANEL: dict[str, tuple[str, str]] = {}


def build_panel(svg: Svg) -> None:
    def sym(lib: str, eid: str, name: str, tag: str, x: float, y: float, **kw: Any) -> None:
        svg.symbol(lib, eid, name, x, y, **kw)
        PANEL[eid] = (tag, lib)

    svg.parts.append(f'<rect id="dp_bg" x="0" y="{PANEL_Y - 6}" width="1840" height="{H_NEW - PANEL_Y + 6}" fill="#e6e9ec"/>')
    y0 = PANEL_Y + 4
    # Driftsform og scenarie (omskiftere, 140 × 140)
    svg.frame("dp_f_mode", 10, y0, 180, 232, "Driftsform")
    sym("omskifter_mode", "dp_mode", "Driftsform", "cmd_mode", 30, y0 + 50, typ="omskifter")
    svg.frame("dp_f_scen", 200, y0, 180, 232, "Scenarie")
    sym("omskifter_scen", "dp_scen", "Scenarie", "cmd_scenarie", 220, y0 + 50, typ="omskifter")
    # Trykknapper (76 × 106)
    svg.frame("dp_f_btn", 390, y0, 290, 232, "Betjening")
    for i, (eid, txt, tag) in enumerate((("dp_fyrop", "Fyr op", "cmd_fyr_op"), ("dp_kvit", "Kvittér", "cmd_kvitter"),
                                         ("dp_fyld", "Efterfyld", "cmd_efterfyld"))):
        sym("trykknap_puls", eid, txt, tag, 402 + i * 92, y0 + 50, text=txt)
    svg.label("dp_btn_hint", 400, y0 + 200, "Fyr op: +15 kg brænde · Efterfyld: 1,2 bar", 11, 400)
    # Setpunkter (150 × 40)
    svg.frame("dp_f_sp", 690, y0, 360, 232, "Setpunkter")
    for i, (eid, txt, tag) in enumerate((("dp_sp_rum", "Rumtemperatur", "sp_rum"), ("dp_sp_kurve", "Vejrkurve", "sp_kurve"),
                                         ("dp_sp_tank", "Tank minimum", "sp_tank_min"), ("dp_sp_speed", "Tidsfaktor", "sp_speed"))):
        x, y = 705 + (i % 2) * 175, y0 + 60 + (i // 2) * 85
        svg.label(f"{eid}_l", x, y - 8, txt)
        sym("setpunkt", eid, txt, tag, x, y)
    # Fejl (vippekontakt 64 × 50)
    svg.frame("dp_f_fejl", 1060, y0, 380, 232, "Fejl (demo)")
    fejl = (("P1", "Pumpe 1"), ("P2", "Pumpe 2"), ("P3", "Pumpe 3"), ("P4", "Pumpe 4"), ("pille", "Pillefyr"), ("vp", "Varmepumpe"), ("laek", "Lækage"))
    for i, (n, txt) in enumerate(fejl):
        x, y = 1075 + (i % 4) * 92, y0 + 60 + (i // 4) * 85
        svg.label(f"dp_fejl_{n}_l", x + 32, y - 8, txt, 12, 600, "middle")
        sym("vippekontakt", f"dp_fejl_{n}", f"Fejl {txt}", f"f_{n}", x, y)
    # Manuel drift
    svg.frame("dp_f_man", 1450, y0, 380, 232, "Manuel drift (driftsform Manuel)")
    man = (("P1", "Pumpe 1"), ("P2", "Pumpe 2"), ("P3", "Pumpe 3"), ("P4", "Pumpe 4"), ("MVS", "MVS1+2"), ("pille", "Pillefyr"), ("VP", "Varmepumpe"))
    for i, (n, txt) in enumerate(man):
        x, y = 1465 + (i % 4) * 92, y0 + 60 + (i // 4) * 85
        svg.label(f"dp_man_{n}_l", x + 32, y - 8, txt, 12, 600, "middle")
        sym("vippekontakt", f"dp_man_{n}", f"Manuel {txt}", f"man_{n}", x, y)
    # Infofelt øverst til venstre (statusfelter, 80 × 30)
    for i, (eid, txt, tag) in enumerate((("dp_i_ude", "Ude", "T_UDE"), ("dp_i_rum", "Rum", "T_RUM"),
                                         ("dp_i_klokke", "Klokke", "KLOKKE"), ("dp_i_alarm", "Alarmer", "ALARMER"))):
        x, y = 22 + (i % 2) * 160, 98 + (i // 2) * 44
        svg.label(f"{eid}_l", x, y + 20, txt, 13, 600)
        svg.symbol("statusfelt", eid, f"Statusfelt {txt}", x + 58, y, scale=1.1)
        PANEL[eid] = (tag, "statusfelt")


def _drop_old_panels(old: str, size: int) -> str:
    """Fjern tidligere paneler (kan køres igen). Serveren fjerner kommentarer ved gem, så panelet kendes på sin
    baggrund (rect 1840 bred, #e6e9ec) efterfulgt af `size` elementer — også kopier, hvor Tegn har givet nye id'er."""
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    ET.register_namespace("inkscape", "http://www.inkscape.org/namespaces/inkscape")
    root = ET.fromstring(old)
    for layer in root.iter():
        kids = list(layer)
        starts = [i for i, c in enumerate(kids) if c.tag.endswith("rect") and c.get("width") == "1840" and c.get("fill") == "#e6e9ec"]
        for i in reversed(starts):
            for c in kids[i:i + size]:
                layer.remove(c)
    return ET.tostring(root, encoding="unicode")


def new_svg(old: str, syms: dict[str, str]) -> str:
    svg = Svg(syms)
    build_panel(svg)
    s = _drop_old_panels(old, len(svg.parts))
    s = re.sub(r'(<svg[^>]*?)height="\d+"', rf'\1height="{H_NEW}"', s, count=1)
    s = re.sub(r'viewBox="0 0 1840 \d+"', f'viewBox="0 0 1840 {H_NEW}"', s, count=1)
    block = "\n  " + "\n  ".join(svg.parts) + "\n"
    i = s.rindex("</g>")   # sidste </g> lukker laget
    return s[:i] + block + s[i:]


# ------------------------------------------------------------------ 4: bindinger
BLUE, GREY, WARM, ON = "#0080c0", "#9e9e9e", "#ff8040", "#2e7d32"


def anim(part: str, typ: str, src: str, **params: Any) -> dict[str, Any]:
    return {"part": part, "type": typ, "when": False, "src": src, "params": params}


def flow(part: str, src: str, light: str = BLUE, reverse: bool = False) -> dict[str, Any]:
    return anim(part, "flow", src, mode="onoff", reverse=reverse, invert=False, base="#555555", light=light, speed=40, dash=12)


def pid(index: dict[str, dict[str, Any]], el: str, name: str) -> str:
    """Den faktiske id for symbolets del `name` (data-hv-pid) — kopierede symboler har andre id'er end `<el>_<del>`."""
    found = index.get(el, {}).get("pids", {}).get(name)
    if not found:
        raise SystemExit(f"Symbolet '{el}' har ingen del '{name}'")
    return found


def view(typ: str, anims: list[dict[str, Any]], chart: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"type": typ, "op": "view", "anims": anims, "chart": chart}


# Statusfelter: element → tag
FIELDS = {
    "svg_302": "SMS_TXT", "svg_276": "ST", "svg_305": "STF", "svg_242": "STR", "svg_247": "PFTF", "svg_262": "PFTR",
    "svg_197": "PILLE_TXT", "svg_257": "ATF", "svg_220": "ATT1", "svg_294": "ATT2", "svg_295": "ATT3", "svg_296": "ATT4",
    "svg_297": "ATT5", "svg_298": "ATT6", "svg_300": "TS", "VPTF": "VPTF", "svg_206": "VPTR", "svg_239": "FFTF",
    "svg_288": "FFTR", "svg_195": "FFS_TXT", "svg_130": "PS1", "svg_128": "PS2", "svg_143": "PS3", "svg_178": "PS4",
    "svg_252": "MVT2", "svg_260": "MVS1_TXT", "svg_267": "MVS2_TXT", "statusfelt": "FMTR",
}
# Rør og fittings pr. kreds (efter geometrien på tegningen), farvet som varmt/koldt vand
PIPES = {
    "PS1": ["svg_28", "t_stykke_11", "roer_v_4", "svg_16", "t_stykke_10", "boejning90_17", "svg_29", "svg_30", "boejning90_15",
            "svg_31", "roer_l_2", "boejning90_16", "svg_25", "boejning90_18", "svg_26", "svg_77", "svg_17", "t_stykke_2", "svg_5",
            "svg_84", "svg_85", "boejning90", "t_stykke", "roer_v", "roer_v_2", "boejning90_12", "svg_19", "t_stykke_3",
            "svg_21", "boejning90_2", "svg_32"],
    "PS2": ["svg_12", "t_stykke_9", "svg_63", "boejning90_13", "svg_62"],
    "PS3": ["boejning90_10", "t_stykke_7", "boejning90_11", "t_stykke_6", "svg_103", "boejning90_4", "svg_104", "boejning90_5", "svg_102"],
    "PS4": ["t_stykke_8", "boejning90_9", "t_stykke_5", "roer_l", "svg_135", "svg_160", "svg_134", "svg_172", "roer_l_3",
            "boejning90_8", "roer_v_3", "boejning90_7", "roer_v_5", "svg_157", "boejning90_6", "svg_156", "boejning90_3", "svg_155"],
}
WARM_PIPES = {"svg_28", "t_stykke_11", "roer_v_4", "svg_12", "t_stykke_9", "svg_63", "boejning90_13", "svg_62", "t_stykke_8",
              "boejning90_9", "t_stykke_5", "roer_l", "boejning90_8", "roer_v_3", "roer_v", "roer_v_2", "boejning90_12", "t_stykke",
              "boejning90_10", "t_stykke_7", "boejning90_11", "t_stykke_6", "svg_16"}


def configs(index: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Konfiguration pr. symbol. `index`: tegningens symboler (element → type) så kun eksisterende bindes."""
    out: dict[str, dict[str, Any]] = {}
    for el, tag in FIELDS.items():
        if el in index:
            out[el] = view("statusfelt", [anim(pid(index, el, "tekst"), "text", tag,
                                               decimals=None, true_text="Kører", false_text="Stop", show_unit=True,
                                               prefix="", suffix="", expression="")])
    if "svg_112" in index:   # "FFTF" nederst: ramme i svg_277, tekst (svg_171) i svg_112
        out["svg_112"] = view("statusfelt", [anim(pid(index, "svg_112", "tekst"), "text", "FFTF", decimals=None, true_text="Til", false_text="Fra",
                                                  show_unit=True, prefix="", suffix="", expression="")])
    for src, els in PIPES.items():
        for el in els:
            if el not in index:
                continue
            typ = index[el]["type"] or "custom"
            light = WARM if el in WARM_PIPES else BLUE
            if typ == "t_stykke":
                parts = [index[el]["pids"][n] for n in ("tilloeb1", "tilloeb2", "midte") if n in index[el]["pids"]] or ["all"]
                out[el] = view(typ, [flow(p, src, light) for p in parts])
            else:
                out[el] = view(typ, [flow("all", src, light)])
    out["svg_48"] = view("pumpe", [anim("all", "spin", "PS1", invert=False)])
    out["svg_101"] = view("pumpe", [anim("all", "spin", "PS2", invert=False)])
    out["svg_142"] = view("pumpe", [anim("all", "spin", "PS3", invert=False)])
    out["svg_60"] = view("pumpe", [anim("all", "spin", "PS4", invert=False)])
    flick = {"invert": False, "at_least": 1.0, "palette": ["#ff3b00", "#ff8c1a", "#ffd21a"]}
    out["svg_39"] = view("kedel", [anim(pid(index, "svg_39", "flamme"), "flicker", "PILLE_KW", **flick)])
    out["svg_271"] = view("kedel", [anim(pid(index, "svg_271", "flamme"), "flicker", "FF_KW", **flick)])
    out["svg_4"] = view("varmepumpe", [anim(pid(index, "svg_4", "rotor"), "spin", "VP_RUN", invert=False),
                                       anim(pid(index, "svg_4", "lampe"), "fill", "VP_RUN", on=ON, off=GREY, thresholds=[])])
    # Motorventilerne kan betjenes (håndbetjening på motoren): Auto / AB-A / AB-B → cmd_mvsN. Portfarverne følger den
    # faktiske position (MVSn_POS), så man ser ventilen køre i de 30 s.
    for el, pos, cmd in (("trevejs_motorventil", "MVS1_POS", "cmd_mvs1"), ("trevejs_motorventil_2", "MVS2_POS", "cmd_mvs2")):
        out[el] = {**view("trevejs_motorventil", [
            anim(pid(index, el, "port_a"), "fill", pos, on=BLUE, off=GREY, thresholds=[{"value": 0, "color": BLUE}, {"value": 100, "color": GREY}]),
            anim(pid(index, el, "port_b"), "fill", pos, on=BLUE, off=GREY, thresholds=[{"value": 1, "color": BLUE}]),
            anim(pid(index, el, "port_ab"), "fill", "PS1", on=BLUE, off=GREY, thresholds=[])]),
            "op": "positions", "positions": [{"label": "Auto"}, {"label": "AB-A"}, {"label": "AB-B"}],
            "signals": [{"id": "S1", "tag": cmd, "fb": cmd, "write": "set"}], "planes": [{"signal": "S1", "values": [0, 1, 2]}],
            "display": "remote", "confirm": True, "click": "dialog", "badge": False}
    out["trevejsventil_2"] = view("trevejsventil", [anim("all", "fill", "LADDOMAT", on=WARM, off=GREY, thresholds=[])])
    for el in ("svg_179", "svg_285"):
        out[el] = view("sikkerhedsventil", [anim("all", "blink", "SV_AABEN", invert=False, speed="fast")])
    out["svg_9"] = view("tank", [anim(pid(index, "svg_9", "fyld"), "fill", "ATT1", on=WARM, off=BLUE,
                                      thresholds=[{"value": 0, "color": "#7aa7c7"}, {"value": 45, "color": "#e0a060"},
                                                  {"value": 65, "color": "#e06030"}])])
    chart = lambda tags, title, rng=3600: {"tags": tags, "range_s": rng, "style": "line", "bars": 24, "y_min": None, "y_max": None,
                                           "title": title, "legend": "top", "font_scale": 1.0, "bold": True, "values": True,
                                           "avg_h": 0, "avg_mode": "both"}
    out["trendgraf"] = view("trendgraf", [], chart(["ATT1", "ATT3", "ATT6"], "Akkumuleringstank"))
    out["trendgraf_2"] = view("trendgraf", [], chart(["STF", "STR", "T_UDE"], "Husets kreds"))
    out["trendgraf_3"] = view("trendgraf", [], chart(["ST"], "Systemtryk"))
    # Panelet
    for el, (tag, lib) in PANEL.items():
        if lib == "statusfelt":
            out[el] = view("statusfelt", [anim(pid(index, el, "tekst"), "text", tag, decimals=None, show_unit=True, prefix="", suffix="",
                                               expression="", true_text="Til", false_text="Fra")])
        elif lib == "trykknap_puls":
            out[el] = {"type": "trykknap_puls", "op": "pulse", "signals": [{"id": "S1", "tag": tag, "write": "pulse", "ms": 500}],
                       "confirm": tag == "cmd_efterfyld", "pulse_ms": 500, "badge": False,
                       "anims": [anim(pid(index, el, "flade"), "fill", tag, on="#7cc47f", off="#d6d6d6", thresholds=[])]}
        elif lib == "setpunkt":
            out[el] = {"type": "setpunkt", "op": "entry", "signals": [{"id": "S1", "tag": tag}], "confirm": True, "badge": False,
                       "anims": [anim(pid(index, el, "vaerdi"), "text", tag, decimals=None, show_unit=True, prefix="", suffix="", expression="",
                                      true_text="Til", false_text="Fra")]}
        elif lib == "vippekontakt":
            out[el] = {"type": "vippekontakt", "op": "positions", "positions": [{"label": "Fra"}, {"label": "Til"}],
                       "signals": [{"id": "S1", "tag": tag, "fb": tag, "write": "set"}], "planes": [{"signal": "S1", "values": [0, 1]}],
                       "display": "remote", "confirm": False, "click": "step", "badge": False,
                       "anims": [anim(pid(index, el, "spor"), "fill", tag, on="#7cc47f", off="#d6d6d6", thresholds=[]),
                                 anim(pid(index, el, "vippe"), "move", tag, min=0, max=1, dx=32, dy=0),
                                 anim(pid(index, el, "tekst"), "text", tag, true_text="TIL", false_text="FRA", show_unit=False,
                                      decimals=None, prefix="", suffix="", expression="")]}
        else:   # omskiftere
            n = 5
            angles = SELECTOR_ANGLES[n]
            out[el] = {"type": "omskifter", "op": "positions",
                       "positions": [{"label": l} for l in (MODE_LABELS if tag == "cmd_mode" else SCEN_LABELS)],
                       "signals": [{"id": "S1", "tag": tag, "fb": tag, "write": "set"}],
                       "planes": [{"signal": "S1", "values": list(range(n))}],
                       "display": "remote", "confirm": True, "click": "dialog",
                       "anims": [anim(pid(index, el, "greb"), "rotate", "@pos", min=0, max=100, angle_min=0, angle_max=360, angles=angles, glide_s=0.2)]}
    return out


MODE_LABELS = ["Fra", "Auto", "Sommer", "Pille", "Manuel"]
SCEN_LABELS = ["Normal", "Vinter", "Sommer", "Lækage", "P1-fejl"]
SELECTOR_ANGLES = {5: [-90, -45, 0, 45, 90]}


def symbol_index(svg: str) -> dict[str, dict[str, Any]]:
    """Tegningens symboler: element → type og dele (data-hv-pid → id). Rør uden bibliotekstype får typen 'custom'."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(svg)
    idx: dict[str, dict[str, Any]] = {}

    def walk(node: Any, owner: str | None) -> None:
        for ch in node:
            cid = ch.get("id")
            here = owner
            if owner is None and cid and (ch.get("data-hv-type") or ch.get("data-hv-name")):
                idx[cid] = {"type": ch.get("data-hv-type") or "custom", "pids": {}}
                here = cid
            elif owner is not None and cid and ch.get("data-hv-pid"):
                idx[owner]["pids"].setdefault(ch.get("data-hv-pid"), cid)
            walk(ch, here)
    walk(root, None)
    return idx


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a.split("=")[0]: (a.split("=", 1)[1] if "=" in a else True) for a in sys.argv[1:] if a.startswith("--")}
    if len(args) != 1:
        raise SystemExit(__doc__)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cafile = flags.get("--cafile")
    api = Api(args[0], str(cafile) if cafile else None)
    user, pw = os.environ.get("SCADA_USER", ""), os.environ.get("SCADA_PASS", "")
    if not user or not pw:
        raise SystemExit("Sæt SCADA_USER og SCADA_PASS")
    api.req("POST", "/api/auth/login", {"username": user, "password": pw})
    drawing = str(flags.get("--drawing", "varme"))
    syms = json.loads(Path(str(flags.get("--symbols", HERE / "syms.json"))).read_text(encoding="utf-8"))

    if not flags.get("--skip-plc"):
        setup_plc(api, str(flags.get("--plc", "http://10.1.1.34")))
        setup_tags(api)

    old = api.req("GET", f"/api/drawings/{drawing}/svg")
    if flags.get("--only-configs"):   # tegningen er uændret: sæt kun symbolerne op på den aktive version
        cfgs = configs(symbol_index(old))
        for el, cfg in cfgs.items():
            api.req("PUT", f"/api/drawings/{drawing}/symbols/{el}/config", {"config": cfg})
        print(f"Bindinger: {len(cfgs)} symboler opsat (tegningen uændret)")
        return
    svg = new_svg(old, syms)
    if flags.get("--dry-run"):
        Path(str(flags["--dry-run"]) if flags["--dry-run"] is not True else "varme-demo.svg").write_text(svg, encoding="utf-8")
        print("Tør-kørsel: SVG skrevet, intet gemt på serveren")
        return
    res = api.req("POST", f"/api/drawings/{drawing}/versions", {"svg": svg, "comment": "Demo-PLC: betjeningspanel og bindinger", "activate": True})
    print(f"Tegningen '{drawing}': ny version {res.get('version')}")

    index = symbol_index(svg)
    cfgs = configs(index)
    bad = 0
    for el, cfg in cfgs.items():
        r = api.req("PUT", f"/api/drawings/{drawing}/symbols/{el}/config", {"config": cfg})
        warn = (r or {}).get("warnings") or []
        if warn:
            bad += 1
            print(f"  {el}: {'; '.join(str(w) for w in warn)[:300]}")
    print(f"Bindinger: {len(cfgs)} symboler opsat{f', {bad} med advarsler' if bad else ''}")


if __name__ == "__main__":
    main()
