# SPDX-License-Identifier: AGPL-3.0-or-later
"""Lægger tre alarmlamper på tegningen test_ny_editor, så testens alarmer (TNE_ALARM, TNE_ALARM2, TNE_TRYK_HOEJ) hører til dens system.

Alarmer-siden kan filtrere pr. system (en tegning og de tags, den bruger). Uden lamperne står testens alarmer ikke på nogen tegning.
Brug:  SCADA_URL=https://scada.laces.dk SCADA_USER=... SCADA_PASS=... python demo/test-ny-editor/alarm_lamps.py
Kan køres igen: findes lamperne, sker der intet. Adgangskoden læses fra miljøet og skrives aldrig ud.
"""
import http.cookiejar
import json
import os
import re
import urllib.error
import urllib.request

BASE = os.environ.get("SCADA_URL", "https://scada.laces.dk").rstrip("/")
D = os.environ.get("DRAWING", "test-ny-editor")
LAMPS = [("al_tne_1", "TNE_ALARM", "Alarm hovedpumpe"), ("al_tne_2", "TNE_ALARM2", "Alarm reservepumpe"), ("al_tne_3", "TNE_TRYK_HOEJ", "Højt tryk (over 5,5 bar)")]
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def call(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with op.open(req, timeout=60) as r:
            txt = r.read().decode()
            return r.status, (json.loads(txt) if txt else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


user, password = os.environ.get("SCADA_USER", ""), os.environ.get("SCADA_PASS", "")
if not user or not password or call("POST", "/api/auth/login", {"username": user, "password": password})[0] != 200:
    raise SystemExit("Sæt SCADA_USER og SCADA_PASS (og tjek dem)")
st, view = call("GET", f"/api/drawings/{D}/view")
if st != 200:
    raise SystemExit(f"Tegningen {D} findes ikke")
svg = view["svg"]
if 'id="al_tne_1"' not in svg:
    parts = ['<text id="t_alarmer_tne" x="40" y="28" font-size="12" font-family="Segoe UI, Arial" fill="#333" font-weight="700">Alarmer (røde lamper er aktive)</text>']
    for n, (i, _, name) in enumerate(LAMPS):
        x = 40 + 230 * n
        parts.append(f'<g data-hv-name="{name}" data-hv-type="lampe" data-hv-unused="*" id="{i}" transform="translate({x} 38)">'
                     f'<circle cx="16" cy="16" data-hv-pid="glas" fill="#9e9e9e" id="{i}_glas" r="14" stroke="#555" stroke-width="2"/></g>')
        parts.append(f'<text id="t_{i}" x="{x + 40}" y="59" font-size="12" font-family="Segoe UI, Arial" fill="#333">{name}</text>')
    new = re.sub(r"</g>\s*</svg>\s*$", "".join(parts) + "</g></svg>", svg)
    st, r = call("POST", f"/api/drawings/{D}/versions", {"svg": new, "comment": "Alarmlamper (alarmerne hører til systemet)", "activate": True})
    print("ny version:", st)
base = {"type": "lampe", "op": "view", "passive": False, "positions": [], "signals": [], "planes": [], "fault": "", "display": "remote", "validate_s": 5.0,
        "alarm": "", "confirm": False, "badge": False, "click": "dialog", "pulse_ms": 500, "lock": {"positions": [], "leave": False}, "logic": [],
        "chart": None, "flow": None, "state_look": {}}
for i, tag, _ in LAMPS:
    cfg = {**base, "anims": [{"part": f"{i}_glas", "type": "fill", "when": False, "src": tag, "only": None, "auto": False, "by_value": False, "pos_values": None,
                              "params": {"on": "#e53935", "off": "#d6d6d6", "thresholds": [], "at_least": None}}]}
    st, r = call("PUT", f"/api/drawings/{D}/symbols/{i}/config", {"config": cfg})
    print("ok  " if st == 200 else "FEJL", i, tag, "" if st == 200 else str(r)[:300])
