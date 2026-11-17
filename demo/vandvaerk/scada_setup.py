# SPDX-License-Identifier: AGPL-3.0-or-later
"""Opsæt brøndstationen i SCADA: tags, tegningen `vandvaerk` og symbolernes opsætning (bindinger, animationer, betjening).

Brug:  SCADA_URL=https://scada.laces.dk SCADA_USER=... SCADA_PASS=... PLC_NAME=demo python demo/vandvaerk/scada_setup.py
       --tags      kun tags
       --drawing   kun tegningen (ny version, hvis den findes)
       --config    kun symbolernes opsætning

Forudsætter, at ST-programmerne er indlæst (load.py), og at SCADA kender PLC'en (PLC_NAME er dens navn i SCADA, standard `demo`).
Tags oprettes som `<PLC>:logic:2:<navn>` og `<PLC>:logic:3:<navn>`; findes de, springes de over. Tegningen er genereret i Tegn
(symbolerne fra biblioteket, rørene tegnet mellem tilslutningspunkterne, Bind forbindelser) og ligger som `vandvaerk.svg`.
Adgangskoden læses fra miljøet og skrives aldrig ud.
"""
import json
import os
import sys
import urllib.error
import urllib.request
import http.cookiejar
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = os.environ.get("SCADA_URL", "https://scada.laces.dk").rstrip("/")
PLC = os.environ.get("PLC_NAME", "demo")
D = "vandvaerk"
ARGS = {a for a in sys.argv[1:] if a.startswith("--")}
DO = lambda x: not ARGS or x in ARGS  # noqa: E731
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
if not user or not password:
    raise SystemExit("Sæt SCADA_USER og SCADA_PASS i miljøet")
if call("POST", "/api/auth/login", {"username": user, "password": password})[0] != 200:
    raise SystemExit("Login fejlede")

# symbolernes id i tegningen (nøgle i dette script -> element-id)
ID = {
 "broend": "broend",
 "kontra": "kontraventil",
 "tee": "t_stykke",
 "kontakt": "kontakttank",
 "beh": "tank",
 "hypotank": "tank_2",
 "dosp": "doseringspumpe",
 "xv1": "motorventil",
 "ft": "ft",
 "pt": "pt",
 "at1": "at",
 "at2": "at_2",
 "lt1": "lt",
 "lt2": "lt_2",
 "lt3": "lt_3",
 "v_q": "vaerdi",
 "v_tryk": "vaerdi_2",
 "v_brond": "vaerdi_3",
 "v_hypo": "vaerdi_4",
 "v_at1": "vaerdi_5",
 "v_at2": "vaerdi_6",
 "v_ct": "vaerdi_7",
 "v_tkont": "vaerdi_8",
 "v_beh": "vaerdi_9",
 "v_behov": "vaerdi_10",
 "v_doegn": "vaerdi_11",
 "v_dose": "vaerdi_12",
 "v_p2lh": "vaerdi_13",
 "v_p2pct": "vaerdi_14",
 "v_klokke": "vaerdi_15",
 "v_trin": "vaerdi_16",
 "sf_status": "statusfelt",
 "sf_trip": "statusfelt_2",
 "sf_scen": "statusfelt_3",
 "mode": "omskifter3",
 "kvit": "trykknap_puls",
 "fyld": "trykknap_puls_2",
 "man_p1": "vippekontakt",
 "man_p2": "vippekontakt_2",
 "man_xv1": "vippekontakt_3",
 "trim": "vippekontakt_4",
 "f_an": "vippekontakt_5",
 "f_p2": "vippekontakt_6",
 "f_lav": "vippekontakt_7",
 "sp_start": "setpunkt",
 "sp_stop": "setpunkt_2",
 "sp_dose": "setpunkt_3",
 "sp_res": "setpunkt_4",
 "sp_lav": "setpunkt_5",
 "sp_hoej": "setpunkt_6",
 "sp_speed": "setpunkt_7",
 "sp_scen": "setpunkt_8",
 "alarm": "genvej_alarmer",
 "trend1": "trendgraf",
 "trend2": "trendgraf_2",
 "trend3": "trendgraf_3"
}

L2, L3 = f"{PLC}:logic:2:", f"{PLC}:logic:3:"
W = {"writable": True}
T = {"trend": True, "trend_interval_s": 10.0}
AL = {"alarm_on": "true"}
TAGS = [
    # ---- Logic2: styring
    (L2, "VW_MODE", "Vandværk: driftsform 0 Fra, 1 Auto, 2 Manuel", {**W, "min": 0, "max": 2}),
    (L2, "VW_KVIT", "Vandværk: kvittér trip (puls)", W),
    (L2, "VW_MAN_P1", "Vandværk: manuel start brøndpumpe", W),
    (L2, "VW_MAN_P2", "Vandværk: manuel start dosering", W),
    (L2, "VW_MAN_XV1", "Vandværk: manuel åbn skylleventil", W),
    (L2, "VW_SP_START", "Vandværk: startniveau højdebeholder", {**W, "unit": "%", "decimals": 0, "min": 5, "max": 80}),
    (L2, "VW_SP_STOP", "Vandværk: stopniveau højdebeholder", {**W, "unit": "%", "decimals": 0, "min": 50, "max": 95}),
    (L2, "VW_SP_DOSE", "Vandværk: klordosis", {**W, "unit": "mg/l", "decimals": 2, "min": 0.2, "max": 3.0}),
    (L2, "VW_SP_RES", "Vandværk: mål-residual efter kontakttank", {**W, "unit": "mg/l", "decimals": 2, "min": 0.1, "max": 2.0}),
    (L2, "VW_TRIM", "Vandværk: trim af dosis fra AT2", W),
    (L2, "VW_SP_LAV", "Vandværk: klor lav-grænse", {**W, "unit": "mg/l", "decimals": 2, "min": 0.05, "max": 1.0}),
    (L2, "VW_SP_HOEJ", "Vandværk: klor høj-grænse", {**W, "unit": "mg/l", "decimals": 2, "min": 0.5, "max": 5.0}),
    (L2, "VW_STATUS", "Vandværk: status 0 Stoppet, 1 Starter, 2 Drift, 3 Stopper, 4 Trip", {}),
    (L2, "VW_TRIN", "Vandværk: sekvenstrin 0-5", {}),
    (L2, "VW_TRIP", "Vandværk: tripårsag 0 ingen, 1 brønd, 2 hypo/dosering, 3 klor, 4 pumpe", {}),
    (L2, "VW_KOM_P1", "Vandværk: kommando brøndpumpe", {}),
    (L2, "VW_KOM_P2", "Vandværk: kommando doseringspumpe", {}),
    (L2, "VW_KOM_XV1", "Vandværk: kommando skylleventil", {}),
    (L2, "VW_DOSIS_EFF", "Vandværk: effektiv dosis", {"unit": "mg/l", "decimals": 2}),
    (L2, "VW_P2_PCT", "Vandværk: doseringspumpens ydelse", {"unit": "%", "decimals": 0}),
    (L2, "VW_ALARMER", "Vandværk: antal aktive alarmer", {}),
    (L2, "VW_AL_BROND", "Vandværk alarm: brøndniveau lavt (under 2 m)", AL),
    (L2, "VW_AL_BROND_LL", "Vandværk alarm: brøndniveau lav-lav (under 1 m)", AL),
    (L2, "VW_AL_HYPO", "Vandværk alarm: hypotank lav (under 15 %)", AL),
    (L2, "VW_AL_HYPO_TOM", "Vandværk alarm: hypotank tom (under 3 %)", AL),
    (L2, "VW_AL_KLOR_LAV", "Vandværk alarm: klor for lavt efter kontakttank", AL),
    (L2, "VW_AL_KLOR_HOEJ", "Vandværk alarm: klor for højt efter kontakttank", AL),
    (L2, "VW_AL_P1", "Vandværk alarm: brøndpumpe fejl", AL),
    (L2, "VW_AL_P2", "Vandværk alarm: doseringspumpe fejl", AL),
    (L2, "VW_AL_FLOW", "Vandværk alarm: brøndpumpe kommanderet uden flow", AL),
    (L2, "VW_AL_DOEGN", "Vandværk alarm: døgnmængde over 90 % af tilladelsen", AL),
    (L2, "VW_AL_AN", "Vandværk alarm: analysatorfejl", AL),
    (L2, "VW_AL_BEH_LAV", "Vandværk alarm: højdebeholder lav (under 20 %)", AL),
    (L2, "VW_AL_BEH_HOEJ", "Vandværk alarm: højdebeholder høj (over 95 %)", AL),
    (L2, "VW_AL_TRIP", "Vandværk alarm: trip låst", AL),
    # ---- Logic3: proces
    (L3, "VW_SPEED", "Vandværk: tidsfaktor", {**W, "decimals": 0, "min": 1, "max": 120}),
    (L3, "VW_SCEN", "Vandværk: scenarie 0 Normal, 1 pumpefejl, 2 hypo tom, 3 høj efterspørgsel, 4 overdosering", {**W, "min": 0, "max": 4}),
    (L3, "VW_F_AN", "Vandværk: fejlinjektion analysatorfejl", W),
    (L3, "VW_F_P2", "Vandværk: fejlinjektion doseringspumpe fejl", W),
    (L3, "VW_F_LAV", "Vandværk: fejlinjektion lav grundvandsstand", W),
    (L3, "VW_FYLD", "Vandværk: fyld hypotank (puls)", W),
    (L3, "VW_KLOKKE", "Vandværk: simuleret klokke", {"unit": "t", "decimals": 2}),
    (L3, "VW_BROND", "Vandværk: brøndniveau", {"unit": "m", "decimals": 2, **T}),
    (L3, "VW_Q", "Vandværk: flow fra brøndpumpen", {"unit": "l/s", "decimals": 1, **T}),
    (L3, "VW_TRYK", "Vandværk: tryk efter pumpen", {"unit": "bar", "decimals": 2}),
    (L3, "VW_P1_FB", "Vandværk: brøndpumpe kører", {}),
    (L3, "VW_P2_FB", "Vandværk: doseringspumpe kører", {}),
    (L3, "VW_XV1_AABEN", "Vandværk: skylleventil åben", {}),
    (L3, "VW_XV1_LUKKET", "Vandværk: skylleventil lukket", {}),
    (L3, "VW_XV1_POS", "Vandværk: skylleventil position", {"unit": "%", "decimals": 0}),
    (L3, "VW_HYPO", "Vandværk: hypotank niveau", {"unit": "%", "decimals": 1, **T}),
    (L3, "VW_P2_LH", "Vandværk: doseret hypo", {"unit": "l/t", "decimals": 2}),
    (L3, "VW_BEH", "Vandværk: højdebeholder niveau", {"unit": "%", "decimals": 1, **T}),
    (L3, "VW_BEHOV", "Vandværk: forbrug", {"unit": "l/s", "decimals": 1, **T}),
    (L3, "VW_DOEGN", "Vandværk: døgnmængde", {"unit": "m³", "decimals": 0}),
    (L3, "VW_DOSE", "Vandværk: doseret klor", {"unit": "mg/l", "decimals": 2}),
    (L3, "VW_AT1", "Vandværk: klor efter indsprøjtning (AT1)", {"unit": "mg/l", "decimals": 2, **T}),
    (L3, "VW_AT2", "Vandværk: klor efter kontakttank (AT2), -1 = analysatorfejl", {"unit": "mg/l", "decimals": 2, **T}),
    (L3, "VW_TKONT", "Vandværk: kontakttid", {"unit": "min", "decimals": 1}),
    (L3, "VW_CT", "Vandværk: CT (klor gange kontakttid)", {"unit": "mg·min/l", "decimals": 1}),
]

if DO("--tags"):
    made = skipped = 0
    for pre, name, desc, extra in TAGS:
        st, r = call("POST", "/api/tags", {"name": name, "source": pre + name, "description": desc, **extra})
        if st in (200, 201):
            made += 1
        elif st == 409:
            skipped += 1
        else:
            print("FEJL", name, st, str(r)[:200])
    print(f"tags: {made} oprettet, {skipped} fandtes")

if DO("--drawing"):
    svg = (HERE / "vandvaerk.svg").read_text(encoding="utf-8")
    st, _ = call("GET", f"/api/drawings/{D}/view")
    if st == 200:
        st, r = call("POST", f"/api/drawings/{D}/versions", {"svg": svg, "comment": "Fra demo/vandvaerk/vandvaerk.svg", "activate": True})
    else:
        st, r = call("POST", "/api/drawings", {"name": D, "svg": svg})
    print("tegning:", st, "" if st in (200, 201) else str(r)[:200])

if not DO("--config"):
    raise SystemExit(0)

def base(typ, op="view", **kw):
    c = {"type": typ, "op": op, "passive": False, "positions": [], "signals": [], "planes": [], "fault": "", "display": "remote", "validate_s": 5.0,
         "alarm": "", "confirm": False, "badge": False, "click": "dialog", "pulse_ms": 500, "lock": {"positions": [], "leave": False},
         "anims": [], "logic": [], "chart": None, "flow": None, "state_look": {}}
    c.update(kw)
    return c


def A(part, typ, src, params):
    return {"part": part, "type": typ, "when": False, "src": src, "params": params, "only": None, "auto": False, "by_value": False, "pos_values": None}


def sig(tag, fb=None):
    return {"id": "S1", "tag": tag, "fb": fb or tag, "write": "set", "ms": 500, "rest": None, "virtual": False}


def put(key, cfg):
    el = ID[key]
    st, r = call("PUT", f"/api/drawings/{D}/symbols/{el}/config", {"config": cfg})
    print("ok  " if st == 200 else "FEJL", key, el, "" if st == 200 else str(r)[:400])


def flow(capacity, rate_tag):
    return {"pump": True, "capacity": capacity, "rate": {"src": rate_tag, "max": 1}, "restrict": {"src": "@val:1", "max": 1},
            "open": None, "measured": {"src": "", "max": 1, "low": 0, "high": 100}, "port_colors": None}


BLU, GRN, AMB, RED, OFF = "#90caf9", "#a5d6a7", "#ffe082", "#ef9a9a", "#eeeeee"
spin = {"invert": False, "at_least": None, "set": [True]}

# ---- proces
put("broend", base("broend", anims=[A(f"{ID['broend']}_loebehjul", "spin", "VW_P1_FB", spin),
                                    A(f"{ID['broend']}_fyld", "level", "VW_BROND", {"min": 0, "max": 10, "direction": "up"})], flow=flow(2100, "VW_P1_FB")))
put("dosp", base("doseringspumpe", anims=[A(f"{ID['dosp']}_loebehjul", "spin", "VW_P2_FB", spin)]))
put("beh", base("tank", anims=[A(f"{ID['beh']}_fyld", "level", "VW_BEH", {"min": 0, "max": 100, "direction": "up"})]))
put("hypotank", base("tank", anims=[A(f"{ID['hypotank']}_fyld", "level", "VW_HYPO", {"min": 0, "max": 100, "direction": "up"})]))
put("kontakt", base("kontakttank", anims=[A(f"{ID['kontakt']}_fyld", "fill", "VW_AT2", {"on": "#7aa7c7", "off": "#7aa7c7", "thresholds": [{"value": 0.2, "color": "#8fd0c0"}, {"value": 1.0, "color": "#5fc2a0"}], "at_least": None})]))
put("xv1", base("motorventil", anims=[A(f"{ID['xv1']}_hus", "fill", "VW_XV1_AABEN", {"on": "#7cc47f", "off": "#9e9e9e", "thresholds": [], "at_least": None})]))

# ---- værdifelter
for key, tag in [("v_q", "VW_Q"), ("v_tryk", "VW_TRYK"), ("v_brond", "VW_BROND"), ("v_hypo", "VW_HYPO"), ("v_at1", "VW_AT1"), ("v_at2", "VW_AT2"),
                 ("v_ct", "VW_CT"), ("v_tkont", "VW_TKONT"), ("v_beh", "VW_BEH"), ("v_behov", "VW_BEHOV"), ("v_doegn", "VW_DOEGN"),
                 ("v_dose", "VW_DOSIS_EFF"), ("v_p2lh", "VW_P2_LH"), ("v_p2pct", "VW_P2_PCT"), ("v_klokke", "VW_KLOKKE"), ("v_trin", "VW_TRIN")]:
    put(key, base("vaerdi", anims=[A(f"{ID[key]}_vaerdi", "text", tag, {"decimals": None, "texts": [], "true_text": "Til", "false_text": "Fra",
                                                                       "show_unit": True, "prefix": "", "suffix": "", "expression": ""})]))


# ---- tilstandsfelter
def field(key, tag, texts, colors):
    el = ID[key]
    put(key, base("statusfelt", anims=[
        A(f"{el}_tekst", "text", tag, {"texts": [{"value": i, "text": t} for i, t in enumerate(texts)], "decimals": None, "show_unit": False,
                                       "prefix": "", "suffix": "", "expression": "", "true_text": "Til", "false_text": "Fra"}),
        A(f"{el}_felt", "fill", tag, {"on": OFF, "off": OFF, "thresholds": [{"value": i, "color": c} for i, c in colors], "at_least": None})]))


field("sf_status", "VW_STATUS", ["Stoppet", "Starter", "Drift", "Stopper", "TRIP"], [(1, BLU), (2, GRN), (3, AMB), (4, RED)])
field("sf_trip", "VW_TRIP", ["Ingen", "Brønd lavt niveau", "Hypotank / dosering", "Klor uden for grænser", "Pumpefejl / intet flow"], [(1, AMB), (2, RED), (3, RED), (4, RED)])
field("sf_scen", "VW_SCEN", ["Normal", "Brøndpumpe fejl", "Hypotank tom", "Høj efterspørgsel", "Overdosering"], [(1, AMB), (2, AMB), (3, AMB), (4, AMB)])

# ---- betjening
put("mode", base("omskifter3", op="positions", positions=[{"label": "Manuel", "state": "Hånd"}, {"label": "Fra", "state": "0"}, {"label": "Auto", "state": "Auto"}],
                 signals=[sig("VW_MODE")], planes=[{"signal": "S1", "values": [2.0, 0.0, 1.0]}], lock={"positions": [False, False, False], "leave": False}))
put("kvit", base("trykknap_puls", op="pulse", signals=[sig("VW_KVIT", "")]))
put("fyld", base("trykknap_puls", op="pulse", signals=[sig("VW_FYLD", "")]))


def vippe(key, tag, lab=("Fra", "Til")):
    el = ID[key]
    put(key, base("vippekontakt", op="positions", positions=[{"label": lab[0], "state": None}, {"label": lab[1], "state": None}], signals=[sig(tag)],
                  planes=[{"signal": "S1", "values": [0.0, 1.0]}], click="step", lock={"positions": [False, False], "leave": False},
                  anims=[A(f"{el}_spor", "fill", "@pos", {"on": "#2e7d32", "off": "#9e9e9e", "thresholds": [], "at_least": None, "colors": ["#d6d6d6", "#7cc47f"]}),
                         A(f"{el}_vippe", "move", "@pos", {"min": 0.0, "max": 100.0, "dx": 100.0, "dy": 0.0, "dxs": [0.0, 32.0], "dys": [0.0, 0.0]}),
                         A(f"{el}_tekst", "text", "@pos", {"decimals": None, "texts": [], "true_text": "Til", "false_text": "Fra", "show_unit": True,
                                                           "prefix": "", "suffix": "", "expression": ""})]))


for key, tag in [("man_p1", "VW_MAN_P1"), ("man_p2", "VW_MAN_P2"), ("man_xv1", "VW_MAN_XV1"), ("trim", "VW_TRIM"),
                 ("f_an", "VW_F_AN"), ("f_p2", "VW_F_P2"), ("f_lav", "VW_F_LAV")]:
    vippe(key, tag)
for key, tag in [("sp_start", "VW_SP_START"), ("sp_stop", "VW_SP_STOP"), ("sp_dose", "VW_SP_DOSE"), ("sp_res", "VW_SP_RES"), ("sp_lav", "VW_SP_LAV"),
                 ("sp_hoej", "VW_SP_HOEJ"), ("sp_speed", "VW_SPEED"), ("sp_scen", "VW_SCEN")]:
    put(key, base("setpunkt", op="entry", signals=[sig(tag)], confirm=True,
                  anims=[A(f"{ID[key]}_vaerdi", "text", tag, {"decimals": None, "texts": [], "true_text": "Til", "false_text": "Fra", "show_unit": True,
                                                              "prefix": "", "suffix": "", "expression": ""})]))


# ---- grafer
def chart(key, tags, title, ymin=None, ymax=None):
    put(key, base("trendgraf", chart={"tags": tags, "range_s": 3600, "style": "line", "bars": 24, "y_min": ymin, "y_max": ymax, "title": title,
                                      "legend": "top", "font_scale": 1.0, "bold": True, "values": True, "avg_h": 0.0, "avg_mode": "both"}))


chart("trend1", ["VW_AT1", "VW_AT2"], "Klor (mg/l)")
chart("trend2", ["VW_BEH", "VW_HYPO"], "Beholder og hypotank (%)", 0, 100)
chart("trend3", ["VW_Q", "VW_BEHOV"], "Flow og forbrug (l/s)", 0, None)
