"""Egne symboler i biblioteket: eksport fra en tegning, versioner, opdeling og backup (v3.28.0)."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services import library as lib
from app.services.errors import ServiceError

ADMIN_PW = "test-admin-pw-1"
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">'
       '<defs><linearGradient id="grad1"><stop offset="0" stop-color="#fff"/></linearGradient>'
       '<linearGradient id="grad2" href="#grad1"/></defs>'
       '<g id="Grp" transform="translate(50 60)" data-hv-name="Min gruppe">'
       '<rect id="kasse" x="0" y="0" width="80" height="40" fill="url(#grad2)"/>'
       '<g id="P1" data-hv-type="pumpe" data-hv-name="Pumpe 1">'
       '<circle id="P1_hjul" data-hv-pid="loebehjul" cx="20" cy="20" r="10"/>'
       '<circle id="P1_hus" data-hv-pid="hus" cx="20" cy="20" r="15"/></g>'
       '<g id="K1" data-hv-type="knap" data-hv-name="Knap 1"><rect id="K1_flade" data-hv-pid="flade" x="50" y="5" width="20" height="10"/></g>'
       '<g id="K2" data-hv-type="knap" data-hv-name="Knap 2"><rect id="K2_flade" data-hv-pid="flade" x="50" y="25" width="20" height="10"/></g>'
       '</g><rect id="Andet" x="300" y="200" width="10" height="10"/></svg>')
BOX = {"x": 50, "y": 60, "w": 80, "h": 40}
TAGS = [{"name": "Drift", "source": "plc1:di:1"}, {"name": "Start", "source": "plc1:coil:1", "writable": True}]


@pytest.fixture
def api(tmp_path, mock_plc):
    settings = Settings(data_dir=tmp_path, frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0,
                        start_runtimes=False)
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada", "password": "scada123",
                                  "sse_enabled": False})
        for t in TAGS:
            assert c.post("/api/tags", json=t).status_code == 201
        c.did = c.post("/api/drawings", json={"name": "Anlæg", "svg": SVG}).json()["drawing"]["id"]
        spin = {"op": "view", "anims": [{"part": "P1_hjul", "type": "spin", "src": "Drift", "params": {}}]}
        assert c.put(f"/api/drawings/{c.did}/symbols/P1/config", json={"config": spin}).status_code == 200
        yield c


def export(api, **over):
    body = {"drawing_id": api.did, "element": "Grp", "box": BOX, "label": "Pumpestation", "hint": "Pumpe i kasse"}
    body.update(over)
    return api.post("/api/library/symbols", json=body)


def test_export_graphics_parts_and_preset(api):
    r = export(api)
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["type"] == "u_pumpestation" and s["version"] == 1 and s["label"] == "Pumpestation"
    svg = s["svg"]
    assert "translate(-50 -60)" in svg and 'transform="translate(50 60)"' in svg   # flyttet til (0,0), egen drejning bevaret
    assert 'id="loebehjul"' in svg and 'id="kasse"' in svg and 'id="p1"' in svg
    for gone in ("data-hv-name", "data-hv-type", "data-hv-pid", 'id="Grp"', 'id="Andet"'):
        assert gone not in svg
    # gradienten (og den den selv peger på) følger med under nye navne
    assert 'id="def_grad2"' in svg and 'id="def_grad1"' in svg and "url(#def_grad2)" in svg and 'href="#def_grad1"' in svg
    assert sorted(s["parts"]) == sorted(["kasse", "p1", "loebehjul", "hus", "k1", "flade", "k2", "flade_2"])
    anims = s["preset"]["anims"]
    assert anims == [{**anims[0], "part": "loebehjul", "type": "spin", "src": ""}]   # tagget fjernet som standard
    assert s["preset"]["type"] == "u_pumpestation"
    lib_all = api.get("/api/library").json()
    assert [x["type"] for x in lib_all["symbols"]] == ["u_pumpestation"]
    assert lib_all["layout"]["items"]["u_pumpestation"] == ["egne", 0]
    assert any(e["action"] == "library.save" for e in api.get("/api/audit").json())


def test_keep_tags_and_versions(api):
    assert export(api).status_code == 201
    r = export(api, keep_tags=True)
    assert r.status_code == 409 and "findes allerede" in r.json()["error"]
    r = export(api, keep_tags=True, replace=True, hint="Ny")
    assert r.status_code == 201 and r.json()["version"] == 2 and r.json()["hint"] == "Ny"
    assert r.json()["preset"]["anims"][0]["src"] == "Drift"
    assert export(api, label="Ukendt", replace=True).status_code == 404


def test_only_one_operating_symbol(api):
    for k in ("K1", "K2"):
        cfg = {"op": "pulse", "signals": [{"id": "S1", "tag": "Start", "fb": "", "write": "pulse"}]}
        assert api.put(f"/api/drawings/{api.did}/symbols/{k}/config", json={"config": cfg}).status_code == 200
    r = export(api)
    assert r.status_code == 400 and "'Knap 1'" in r.json()["error"] and "'Knap 2'" in r.json()["error"]
    # én knap med betjening er fint: den bliver symbolets betjening, og pumpens animation flettes ind
    assert api.delete(f"/api/drawings/{api.did}/symbols/K2/config").status_code == 204
    s = export(api).json()
    assert s["preset"]["op"] == "pulse" and s["preset"]["signals"][0]["tag"] == ""
    assert [a["part"] for a in s["preset"]["anims"]] == ["loebehjul"]


def test_export_without_config_and_errors(api):
    r = export(api, element="Andet", box={"x": 300, "y": 200, "w": 10, "h": 10}, label="Firkant")
    assert r.status_code == 201 and r.json()["preset"] is None
    assert export(api, element="Findes_ikke", label="X").status_code == 404
    assert export(api, box={"x": 0, "y": 0, "w": 0, "h": 5}, label="Y").status_code == 400
    assert export(api, label="  !!  ").status_code == 400


def test_rename_delete_and_used_in(api):
    t = export(api).json()["type"]
    assert export(api, element="Andet", box={"x": 300, "y": 200, "w": 10, "h": 10}, label="Firkant").status_code == 201
    assert api.patch(f"/api/library/symbols/{t}", json={"label": "firkant"}).status_code == 409   # navnet er taget
    r = api.patch(f"/api/library/symbols/{t}", json={"label": "Pumpe-station 2", "hint": "x"})
    assert r.status_code == 200 and r.json()["label"] == "Pumpe-station 2" and r.json()["type"] == t   # typen er fast
    # en tegning med symbolet: sletning fortæller hvor det bruges, men tegningen røres ikke
    used = SVG.replace('<rect id="Andet"', f'<g id="X1" data-hv-type="{t}"><rect x="0" y="0" width="5" height="5"/></g><rect id="Andet"')
    did2 = api.post("/api/drawings", json={"name": "Bruger", "svg": used}).json()["drawing"]["id"]
    r = api.delete(f"/api/library/symbols/{t}")
    assert r.status_code == 200 and r.json()["used_in"] == [did2]
    assert api.delete(f"/api/library/symbols/{t}").status_code == 404
    assert api.delete("/api/library/symbols/pumpe").status_code == 404   # indbyggede kan ikke slettes


def test_layout_sections_and_conflict(api):
    t = export(api).json()["type"]
    lay = api.get("/api/library").json()["layout"]
    assert lay["order"][:6] == list(lib.BUILTIN_SECTIONS) and "egne" in lay["order"]
    new = {"sections": [{"id": "s1", "label": "Varme"}], "order": ["s1", "egne"],
           "items": {t: ["s1", 0], "pumpe": ["s1", 1], "ventil": ["egne", 0]}}
    r = api.put("/api/library/layout", json={"layout": new, "rev": lay["rev"]})
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["order"][:2] == ["s1", "egne"] and saved["items"]["pumpe"] == ["s1", 1]
    # en gammel revision afvises (en anden har gemt imens)
    assert api.put("/api/library/layout", json={"layout": new, "rev": lay["rev"]}).status_code == 409
    # slet sektionen: eget symbol → "Egne symboler", indbygget → tilbage til sin kategori
    r = api.put("/api/library/layout", json={"layout": {"sections": [], "order": [], "items": saved["items"]}, "rev": saved["rev"]})
    assert r.json()["items"][t][0] == "egne" and "pumpe" not in r.json()["items"]
    for bad in ({"sections": [{"id": "vvs", "label": "X"}]}, {"sections": [{"id": "a", "label": ""}]},
                {"sections": [{"id": "a", "label": "X"}, {"id": "b", "label": "x"}]}, {"items": {"pumpe": ["ukendt", 0]}}):
        cur = api.get("/api/library").json()["layout"]["rev"]
        assert api.put("/api/library/layout", json={"layout": bad, "rev": cur}).status_code == 400, bad
    assert api.put("/api/library/layout", json={"layout": {}}).status_code == 422   # revisionen er påkrævet


def test_viewer_reads_engineer_writes(api):
    assert api.post("/api/users", json={"username": "v1", "role": "viewer", "password": "Hemmelig-123"}).status_code == 201
    with TestClient(api.app) as v:
        v.post("/api/auth/login", json={"username": "v1", "password": "Hemmelig-123"})
        v.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})
        v.post("/api/auth/login", json={"username": "v1", "password": "Hemmelig-123-ny"})
        assert v.get("/api/library").status_code == 200
        body = {"drawing_id": api.did, "element": "Grp", "box": BOX, "label": "X"}
        assert v.post("/api/library/symbols", json=body).status_code == 403
        assert v.put("/api/library/layout", json={"layout": {}, "rev": 0}).status_code == 403
        export(api, keep_tags=True)
        got = v.get("/api/library").json()["symbols"][0]
        assert got["preset"] is None and got["svg"]   # standardopsætningen (med tag-navne) kun til teknikere


def test_backup_roundtrip(api):
    t = export(api).json()["type"]
    backup = api.get("/api/backup").json()
    assert [s["type"] for s in backup["library_symbols"]] == [t]
    assert api.delete(f"/api/library/symbols/{t}").status_code == 200
    assert api.post("/api/backup/restore", json=backup).status_code == 200
    got = api.get("/api/library").json()
    assert [s["type"] for s in got["symbols"]] == [t] and got["symbols"][0]["preset"]["anims"][0]["part"] == "loebehjul"
    # en ældre backup uden egne symboler lader biblioteket være
    old = {k: v for k, v in backup.items() if k not in ("library_symbols", "library_layout")}
    assert api.post("/api/backup/restore", json=old).status_code == 200
    assert [s["type"] for s in api.get("/api/library").json()["symbols"]] == [t]
    # et preset der peger på en del, der ikke findes, afvises
    bad = {**backup, "library_symbols": [{**backup["library_symbols"][0],
                                          "preset": {"anims": [{"part": "ingen", "type": "spin", "src": ""}]}}]}
    r = api.post("/api/backup/restore", json=bad)
    assert r.status_code == 400 and "ingen" in r.json()["error"]


def test_clean_fragment_strips_scripts():
    out = lib.clean_fragment('<g onload="alert(1)"><script>alert(2)</script><rect width="5" height="5" '
                             'href="javascript:x"/></g>', {"x": 0, "y": 0, "w": 5, "h": 5})
    assert "onload" not in out and "script" not in out and "javascript" not in out
    with pytest.raises(ServiceError):
        lib.clean_fragment('<rect/><rect/>', {"x": 0, "y": 0, "w": 5, "h": 5})


def test_type_and_slug():
    assert lib.type_for("Pumpe Æble/Ø 2") == "u_pumpe_aeble_oe_2"
    assert len(lib.type_for("x" * 80)) <= 40
    with pytest.raises(ServiceError):
        lib.type_for("---")


def test_renamed_symbol_keeps_identity(api):
    t = export(api).json()["type"]
    assert api.patch(f"/api/library/symbols/{t}", json={"label": "Station A"}).status_code == 200
    # ny version under det nye navn rammer samme symbol
    r = export(api, label="Station A", replace=True)
    assert r.status_code == 201 and r.json()["type"] == t and r.json()["version"] == 2
    # det gamle navn er frit: et nyt symbol får en anden type end det omdøbte
    r = export(api, label="Pumpestation")
    assert r.status_code == 201 and r.json()["type"] == "u_pumpestation_2" and r.json()["label"] == "Pumpestation"
    assert api.get("/api/library").json()["symbols"][1]["label"] == "Station A"


def test_nested_def_ids_are_renamed(api):
    svg = SVG.replace('<stop offset="0" stop-color="#fff"/>', '<stop id="kasse" offset="0" stop-color="#fff"/>')
    did = api.post("/api/drawings", json={"name": "Defs", "svg": svg}).json()["drawing"]["id"]
    s = export(api, drawing_id=did, label="Med stop").json()["svg"]
    assert s.count('id="kasse"') == 1 and 'id="def_kasse"' in s   # stop-id'et kolliderer ikke med delen


def test_backup_rejects_duplicate_types(api):
    export(api)
    backup = api.get("/api/backup").json()
    row = backup["library_symbols"][0]
    bad = {**backup, "library_symbols": [row, {**row, "label": "Andet navn"}]}
    r = api.post("/api/backup/restore", json=bad)
    assert r.status_code == 400 and "findes to gange" in r.json()["error"]
    rev = api.get("/api/library").json()["layout"]["rev"]
    assert api.post("/api/backup/restore", json=backup).status_code == 200
    assert api.get("/api/library").json()["layout"]["rev"] > rev   # revisionen fortsætter efter gendannelse


# ------------------------------------------------------------------ import af SVG-filer og pakker (v3.31.0)

FILE_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="10 20 100 50" fill="#336">'
            '<style>.st0{fill:#f00;stroke:#000} .st1{stroke-width:3} svg rect{fill:blue}</style>'
            '<defs><linearGradient id="g"><stop offset="0" stop-color="#fff"/></linearGradient></defs>'
            '<rect id="Kasse" class="st0 st1" x="10" y="20" width="100" height="50"/>'
            '<circle id="lampe" cx="60" cy="45" r="10" fill="url(#g)"/>'
            '<script>alert(1)</script><a href="https://x.dk"><rect id="link" width="1" height="1"/></a></svg>')


def imp(api, files, **over):
    body = {"files": files, "on_conflict": "rename"}
    body.update(over)
    return api.post("/api/library/import", json=body)


def test_import_svg_files(api):
    r = imp(api, [{"name": "Min ventil.svg", "svg": FILE_SVG},
                  {"name": "stor.svg", "svg": '<svg xmlns="http://www.w3.org/2000/svg" width="960px" height="480">'
                                                '<path id="p" d="M0 0L960 480"/></svg>'},
                  {"name": "tom.svg", "svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><title>x</title></svg>'},
                  {"name": "uden-str.svg", "svg": '<svg xmlns="http://www.w3.org/2000/svg"><rect width="5" height="5"/></svg>'},
                  {"name": "ikke-svg.svg", "svg": "<html>hej</html>"}])
    assert r.status_code == 200, r.text
    res = r.json()["results"]
    assert [x["status"] for x in res] == ["created", "created", "error", "error", "error"]
    assert res[0]["label"] == "Min ventil" and res[0]["type"] == "u_min_ventil"
    assert set(res[0]["parts"]) == {"kasse", "lampe"}   # <a> (og indholdet) fjernes af rensningen
    assert any("CSS-reglen" in w for w in res[0]["warnings"])
    assert "ingen grafik" in res[2]["error"] and "viewBox" in res[3]["error"]
    lib_ = api.get("/api/library").json()
    svg = next(s for s in lib_["symbols"] if s["type"] == "u_min_ventil")["svg"]
    assert "translate(-10 -20)" in svg and 'fill="#336"' in svg               # flyttet til (0,0), arvet fyld bevaret
    assert "fill:#f00" in svg and "stroke-width:3" in svg and "<style" not in svg and "class=" not in svg
    assert 'id="def_g"' in svg and "url(#def_g)" in svg
    assert "script" not in svg and "https://" not in svg
    big = next(s for s in lib_["symbols"] if s["type"] == "u_stor")["svg"]
    assert "scale(0.25)" in big                                               # 960 → 240
    assert lib_["layout"]["items"]["u_min_ventil"][0] == "egne"


def test_import_conflicts_and_section(api):
    f = [{"name": "Lampe.svg", "svg": FILE_SVG}]
    assert imp(api, f).json()["results"][0]["status"] == "created"
    r2 = imp(api, f).json()["results"][0]
    assert r2["status"] == "renamed" and r2["label"] == "Lampe 2"
    r3 = imp(api, f, on_conflict="version").json()["results"][0]
    assert r3["status"] == "version" and r3["type"] == "u_lampe" and r3["version"] == 2
    assert imp(api, f, on_conflict="skip").json()["results"][0]["status"] == "skipped"
    r5 = imp(api, [{"name": "x.svg", "svg": FILE_SVG}], section="Ventiler").json()
    t = r5["results"][0]["type"]
    lay = api.get("/api/library").json()["layout"]
    sec = next(s for s in lay["sections"] if s["label"] == "Ventiler")
    assert lay["items"][t][0] == sec["id"]
    assert imp(api, f, on_conflict="bad").status_code in (400, 422)
    assert imp(api, []).status_code in (400, 422)


def test_import_limits_and_roles(api):
    huge = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="1" height="1"/>' + "<!--" + "x" * 300_000 + "--></svg>"
    r = imp(api, [{"name": "a.svg", "svg": huge}] * 45)
    assert r.status_code == 413
    api.post("/api/users", json={"username": "op", "password": "op-pw-123456", "role": "operator"})
    api.post("/api/auth/logout")
    api.post("/api/auth/login", json={"username": "op", "password": "op-pw-123456"})
    assert imp(api, [{"name": "a.svg", "svg": FILE_SVG}]).status_code == 403
    assert api.get("/api/library/package").status_code == 403


def test_package_roundtrip(api):
    export(api, keep_tags=True)
    imp(api, [{"name": "Lampe.svg", "svg": FILE_SVG}], section="Ventiler")
    pkg = api.get("/api/library/package").json()
    assert pkg["format"] == "hvlib" and len(pkg["symbols"]) == 2
    ps = next(s for s in pkg["symbols"] if s["label"] == "Pumpestation")
    assert ps["preset"] and all(a["src"] == "" for a in ps["preset"]["anims"])   # ingen tags i pakken
    assert next(s for s in pkg["symbols"] if s["label"] == "Lampe")["section"] == "Ventiler"
    # samme installation: navnene findes → nyt navn / ny version / spring over
    r = api.post("/api/library/package", json={"package": pkg, "on_conflict": "version"}).json()
    assert r["count"]["version"] == 2
    r = api.post("/api/library/package", json={"package": pkg, "on_conflict": "skip"}).json()
    assert r["count"]["skipped"] == 2
    # ugyldigt preset (del findes ikke) fejler kun det symbol
    bad = {**pkg, "symbols": [{**ps, "label": "Ny", "preset": {**ps["preset"], "anims": [{"part": "findes_ikke", "type": "spin", "src": "", "params": {}}]}},
                              {**ps, "label": "Ny 2"}]}
    r = api.post("/api/library/package", json={"package": bad, "on_conflict": "rename"}).json()
    assert [x["status"] for x in r["results"]] == ["error", "created"] and "findes_ikke" in r["results"][0]["error"]
    assert api.post("/api/library/package", json={"package": {"format": "andet"}}).status_code == 400
    assert api.post("/api/library/package", json={"package": {**pkg, "format_version": 9}}).status_code == 400
