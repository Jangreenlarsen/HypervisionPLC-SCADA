"""Navngivne symbolgrupper (v0.130.0): oprettelse, overlap, unikt navn, rettigheder, backup-rundtur og sletning med tegningen."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ADMIN_PW = "test-admin-pw-1"
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200"><g id="A" data-hv-type="pumpe"><circle id="A_c" cx="50" cy="40" r="20"/></g>'
       '<g id="B" data-hv-type="pumpe"><circle id="B_c" cx="150" cy="40" r="20"/></g></svg>')


@pytest.fixture
def api(tmp_path, mock_plc):
    settings = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9,
                        frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0)
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.did = c.post("/api/drawings", json={"name": "Anlæg", "svg": SVG}).json()["drawing"]["id"]
        yield c


def url(api, tail=""):
    return f"/api/drawings/{api.did}/groups{tail}"


def test_create_list_update_delete(api):
    r = api.post(url(api), json={"name": "Fyr uden akku-tank", "kind": "function", "members": ["A", "B", "A"]})
    assert r.status_code == 201, r.text
    g = r.json()
    assert g["members"] == ["A", "B"] and g["kind"] == "function"
    assert api.get(url(api)).json() == [g]
    # omdøb uden at røre medlemmerne (members udeladt)
    r = api.put(url(api, f"/{g['id']}"), json={"name": "Fyr", "kind": "selection"})
    assert r.status_code == 200 and r.json()["members"] == ["A", "B"] and r.json()["name"] == "Fyr"
    r = api.put(url(api, f"/{g['id']}"), json={"name": "Fyr", "kind": "selection", "members": ["B"]})
    assert r.json()["members"] == ["B"]
    assert api.delete(url(api, f"/{g['id']}")).status_code == 204
    assert api.get(url(api)).json() == []
    assert api.delete(url(api, f"/{g['id']}")).status_code == 404


def test_same_element_in_several_groups_and_unique_names(api):
    a = api.post(url(api), json={"name": "G1", "members": ["A"]}).json()
    b = api.post(url(api), json={"name": "G2", "members": ["A", "B"]})
    assert b.status_code == 201
    groups = {g["name"]: g["members"] for g in api.get(url(api)).json()}
    assert groups == {"G1": ["A"], "G2": ["A", "B"]}
    dup = api.post(url(api), json={"name": "G1", "members": []})
    assert dup.status_code == 409 and "G1" in dup.json()["error"]
    # omdøb til et eksisterende navn afvises og ændrer intet
    r = api.put(url(api, f"/{a['id']}"), json={"name": "G2", "members": ["B"]})
    assert r.status_code == 409
    assert {g["name"]: g["members"] for g in api.get(url(api)).json()}["G1"] == ["A"]


def test_validation_and_unknown(api):
    assert api.post(url(api), json={"name": "  ", "members": []}).status_code in (400, 422)
    assert api.post(url(api), json={"name": "X", "kind": "ukendt"}).status_code in (400, 422)
    assert api.put(url(api, "/999"), json={"name": "X", "kind": "selection"}).status_code == 404
    assert api.get("/api/drawings/findes-ikke/groups").status_code == 404


def test_viewer_can_read_but_not_write(api):
    api.post(url(api), json={"name": "G", "members": ["A"]})
    assert api.post("/api/users", json={"username": "v1", "role": "viewer", "password": "Hemmelig-123"}).status_code == 201
    with TestClient(api.app) as v:
        assert v.post("/api/auth/login", json={"username": "v1", "password": "Hemmelig-123"}).status_code == 200
        assert len(v.get(url(api)).json()) == 1
        assert v.post(url(api), json={"name": "H", "members": []}).status_code == 403


def test_backup_roundtrip_and_cascade(api):
    api.post(url(api), json={"name": "G1", "kind": "function", "members": ["A", "B"]})
    api.post(url(api), json={"name": "G2", "members": ["B"]})
    backup = api.get("/api/backup").json()
    assert {g["name"] for g in backup["symbol_groups"]} == {"G1", "G2"}
    api.delete(url(api, "/" + str(api.get(url(api)).json()[0]["id"])))
    r = api.post("/api/backup/restore", json=backup)
    assert r.status_code == 200, r.text
    groups = {g["name"]: (g["kind"], g["members"]) for g in api.get(url(api)).json()}
    assert groups == {"G1": ("function", ["A", "B"]), "G2": ("selection", ["B"])}
    # grupperne følger tegningen ved sletning
    assert api.delete(f"/api/drawings/{api.did}").status_code in (200, 204)
    assert api.get(url(api)).status_code == 404


def test_restore_rejects_bad_groups(api):
    backup = api.get("/api/backup").json()
    backup["symbol_groups"] = [{"drawing_id": api.did, "name": "G", "kind": "x", "members": []}]
    r = api.post("/api/backup/restore", json=backup)
    assert r.status_code == 400 and "Symbolgruppe" in r.json()["error"]


# ------------------------------------------------------------ animationer ejet af grupper (v0.131.0)

PIPE = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200">'
        '<g id="A" data-hv-type="pumpe" data-hv-name="Rør A"><rect id="A_r" x="10" y="10" width="40" height="10"/></g>'
        '<g id="B" data-hv-type="pumpe" data-hv-name="Rør B"><rect id="B_r" x="110" y="10" width="40" height="10"/></g></svg>')


@pytest.fixture
def gapi(tmp_path, mock_plc):
    settings = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9,
                        frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0)
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada",
                                  "password": "scada123", "sse_enabled": False})
        for n, a in (("Fyr", 10), ("Pumpe", 11)):
            assert c.post("/api/tags", json={"name": n, "source": f"plc1:coil:{a}"}).status_code == 201
        c.did = c.post("/api/drawings", json={"name": "Anlæg", "svg": PIPE}).json()["drawing"]["id"]
        c.g1 = c.post(url(c), json={"name": "Fyr", "kind": "function", "members": ["A", "B"]}).json()["id"]
        c.g2 = c.post(url(c), json={"name": "Pumpegruppe", "members": ["A"]}).json()["id"]
        yield c


def fill(tag, on="#d32f2f"):
    return {"part": "all", "type": "fill", "src": tag, "params": {"on": on, "off": "#9e9e9e"}}


def anims_url(api, gid, el):
    return url(api, f"/{gid}/anims/{el}")


def test_group_anims_overlap_and_view(gapi):
    assert gapi.put(anims_url(gapi, gapi.g1, "A"), json={"anims": [fill("Fyr")]}).status_code == 200
    assert gapi.put(anims_url(gapi, gapi.g2, "A"), json={"anims": [fill("Pumpe", "#2e7d32")]}).status_code == 200
    assert gapi.put(anims_url(gapi, gapi.g1, "B"), json={"anims": [fill("Fyr")]}).status_code == 200
    assert list(gapi.get(url(gapi, f"/{gapi.g1}/anims")).json()) == ["A", "B"]
    bindings = [b for b in gapi.get(f"/api/drawings/{gapi.did}/view").json()["bindings"] if b["source"] == "group"]
    on_a = [b for b in bindings if b["element"] == "A"]
    # begge gruppers animationer på A gælder samtidig, i gruppernes rækkefølge, og rør ikke symbolets egen opsætning
    assert [b["group_name"] for b in on_a] == ["Fyr", "Pumpegruppe"]
    assert [b["tag"] for b in on_a] == ["Fyr", "Pumpe"]
    assert on_a[0]["position"] < on_a[1]["position"]
    assert gapi.get(f"/api/drawings/{gapi.did}/symbols/A/config").json()["config"] is None


def test_group_anims_validation(gapi):
    r = gapi.put(anims_url(gapi, gapi.g2, "B"), json={"anims": [fill("Fyr")]})
    assert r.status_code == 400 and "ikke medlem" in r.json()["error"]
    r = gapi.put(anims_url(gapi, gapi.g1, "A"), json={"anims": [fill("Findes-ikke")]})
    assert r.status_code == 400 and "findes ikke" in r.json()["error"]
    r = gapi.put(anims_url(gapi, gapi.g1, "A"), json={"anims": [{**fill("Fyr"), "src": "@pos"}]})
    assert r.status_code == 400
    assert gapi.get(url(gapi, f"/{gapi.g1}/anims")).json() == {}


def test_group_anims_follow_membership_and_block_tag_delete(gapi):
    gapi.put(anims_url(gapi, gapi.g1, "A"), json={"anims": [fill("Fyr")]})
    r = gapi.delete("/api/tags/Fyr")
    assert r.status_code == 409 and "Fyr" in r.json()["error"]
    # medlem fjernet -> dets animationer fjernes med
    gapi.put(url(gapi, f"/{gapi.g1}"), json={"name": "Fyr", "kind": "function", "members": ["B"]})
    assert gapi.get(url(gapi, f"/{gapi.g1}/anims")).json() == {}
    assert gapi.delete("/api/tags/Fyr").status_code in (200, 204)


def test_group_anims_empty_list_removes_and_backup_roundtrip(gapi):
    gapi.put(anims_url(gapi, gapi.g1, "A"), json={"anims": [fill("Fyr")]})
    gapi.put(anims_url(gapi, gapi.g2, "A"), json={"anims": [fill("Pumpe")]})
    backup = gapi.get("/api/backup").json()
    assert {g["name"]: list(g["anims"]) for g in backup["symbol_groups"]} == {"Fyr": ["A"], "Pumpegruppe": ["A"]}
    r = gapi.post("/api/backup/restore", json=backup)
    assert r.status_code == 200, r.text
    ids = {g["name"]: g["id"] for g in gapi.get(url(gapi)).json()}
    assert gapi.get(url(gapi, f"/{ids['Fyr']}/anims")).json()["A"][0]["src"] == "Fyr"
    assert gapi.put(anims_url(gapi, ids["Fyr"], "A"), json={"anims": []}).status_code == 200
    assert gapi.get(url(gapi, f"/{ids['Fyr']}/anims")).json() == {}
    assert gapi.get(url(gapi, f"/{ids['Pumpegruppe']}/anims")).json()["A"][0]["src"] == "Pumpe"
    bad = gapi.get("/api/backup").json()
    bad["symbol_groups"][0]["anims"] = {"A": [{"part": "all", "type": "fill", "src": "Findes-ikke", "params": {}}]}
    r = gapi.post("/api/backup/restore", json=bad)
    assert r.status_code == 400 and "Findes-ikke" in r.json()["error"]


def test_group_anims_on_element(gapi):
    gapi.put(anims_url(gapi, gapi.g1, "A"), json={"anims": [fill("Fyr")]})
    gapi.put(anims_url(gapi, gapi.g2, "A"), json={"anims": [fill("Pumpe")]})
    r = gapi.get(f"/api/drawings/{gapi.did}/symbols/A/group-anims").json()
    assert [(o["group_name"], o["kind"], o["anims"][0]["src"]) for o in r] == [("Fyr", "function", "Fyr"), ("Pumpegruppe", "selection", "Pumpe")]
    gapi.put(anims_url(gapi, gapi.g1, "B"), json={"anims": [fill("Fyr")]})
    assert gapi.get(f"/api/drawings/{gapi.did}/symbols/B/group-anims").json()[0]["group_name"] == "Fyr"


# ------------------------------------------------------------ rettelser efter design-review (v0.131.1)

def test_used_ids_reserves_group_members(gapi):
    assert set(gapi.get(f"/api/drawings/{gapi.did}/used-ids").json()) >= {"A", "B"}


def test_logic_block_used_by_group_anim_cannot_be_removed(gapi):
    block = {"id": "L1", "name": "", "op": "and", "inputs": [{"src": "Fyr"}], "invert": False}
    own = [fill("Pumpe")]   # et visningssymbol skal have mindst én animation
    cfg = {"op": "view", "anims": own, "logic": [block]}
    assert gapi.put(f"/api/drawings/{gapi.did}/symbols/A/config", json={"config": cfg}).status_code == 200
    r = gapi.put(anims_url(gapi, gapi.g1, "B"), json={"anims": [{**fill("Fyr"), "src": "@A:L1"}]})
    assert r.status_code == 200, r.text
    r = gapi.put(f"/api/drawings/{gapi.did}/symbols/A/config", json={"config": {"op": "view", "anims": own, "logic": []}})
    assert r.status_code == 400 and "gruppen Fyr" in r.text and "L1" in r.text
    # fjernes gruppens henvisning først, kan blokken fjernes
    assert gapi.put(anims_url(gapi, gapi.g1, "B"), json={"anims": []}).status_code == 200
    assert gapi.put(f"/api/drawings/{gapi.did}/symbols/A/config", json={"config": {"op": "view", "anims": own, "logic": []}}).status_code == 200


# ------------------------------------------------------------ rettelser efter review del 2 (v0.131.2)

def test_member_deltas_do_not_overwrite_each_other(gapi):
    # to "faner" med samme (forældede) kopi tilføjer hver sit medlem: ingen af dem mister den andens
    gapi.post("/api/drawings", json={"name": "x", "svg": PIPE})
    g = gapi.post(url(gapi), json={"name": "Tom", "members": []}).json()
    assert gapi.post(url(gapi, f"/{g['id']}/members"), json={"add": ["A"]}).json()["members"] == ["A"]
    assert gapi.post(url(gapi, f"/{g['id']}/members"), json={"add": ["B", "A"]}).json()["members"] == ["A", "B"]
    gapi.put(anims_url(gapi, g["id"], "A"), json={"anims": [fill("Fyr")]})
    r = gapi.post(url(gapi, f"/{g['id']}/members"), json={"remove": ["A"]}).json()
    assert r["members"] == ["B"] and gapi.get(url(gapi, f"/{g['id']}/anims")).json() == {}
    assert gapi.post(url(gapi, "/999/members"), json={"add": ["A"]}).status_code == 404


def test_move_missing_member_keeps_group_anims(gapi):
    svg2 = PIPE.replace('id="A"', 'id="A2"').replace('id="A_r"', 'id="A2_r"')
    gapi.put(anims_url(gapi, gapi.g1, "A"), json={"anims": [fill("Fyr")]})
    assert gapi.post(f"/api/drawings/{gapi.did}/versions", json={"svg": svg2, "activate": True}).status_code == 201
    # A findes ikke mere; A2 har fået dets plads
    r = gapi.post(url(gapi, f"/{gapi.g1}/members/move"), json={"old": "A", "new": "A2"})
    assert r.status_code == 200, r.text
    assert r.json()["members"] == ["A2", "B"]
    assert list(gapi.get(url(gapi, f"/{gapi.g1}/anims")).json()) == ["A2"]
    # et element der stadig findes kan ikke "flyttes"
    assert gapi.post(url(gapi, f"/{gapi.g1}/members/move"), json={"old": "B", "new": "A2"}).status_code == 409


def test_reorder_groups_changes_who_wins(gapi):
    gapi.put(anims_url(gapi, gapi.g1, "A"), json={"anims": [fill("Fyr")]})
    gapi.put(anims_url(gapi, gapi.g2, "A"), json={"anims": [fill("Pumpe")]})
    r = gapi.post(url(gapi, "/order"), json={"ids": [gapi.g2, gapi.g1]})
    assert r.status_code == 200 and [g["id"] for g in r.json()] == [gapi.g2, gapi.g1]
    on_a = [b for b in gapi.get(f"/api/drawings/{gapi.did}/view").json()["bindings"] if b["source"] == "group" and b["element"] == "A"]
    assert [b["group_name"] for b in on_a] == ["Pumpegruppe", "Fyr"]
    assert gapi.post(url(gapi, "/order"), json={"ids": [gapi.g1]}).status_code == 400   # skal være alle grupper


def test_overlap_warnings(gapi):
    gapi.put(anims_url(gapi, gapi.g1, "A"), json={"anims": [fill("Fyr")]})
    r = gapi.put(anims_url(gapi, gapi.g2, "A"), json={"anims": [fill("Pumpe")]})
    assert r.status_code == 200 and any("gruppen Fyr" in w for w in r.json()["warnings"]), r.json()
    r = gapi.put(anims_url(gapi, gapi.g1, "B"), json={"anims": [fill("Fyr")]})
    assert r.json()["warnings"] == []


def test_operator_cannot_edit_groups_and_scoped_viewer_sees_group_tags(gapi):
    gapi.put(anims_url(gapi, gapi.g1, "A"), json={"anims": [fill("Fyr")]})
    for name, role, extra in (("op1", "operator", {}), ("v1", "viewer", {"drawings": [gapi.did]})):
        assert gapi.post("/api/users", json={"username": name, "role": role, "password": "Hemmelig-123", **extra}).status_code == 201
    def login(c, name):   # nye brugere skal skifte adgangskode, før de kan bruge API'et
        c.post("/api/auth/login", json={"username": name, "password": "Hemmelig-123"})
        assert c.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"}).status_code == 204

    with TestClient(gapi.app) as op:
        login(op, "op1")
        assert op.post(url(gapi), json={"name": "X", "members": []}).status_code == 403
        assert op.put(anims_url(gapi, gapi.g1, "A"), json={"anims": [fill("Pumpe")]}).status_code == 403
        assert op.post(url(gapi, f"/{gapi.g1}/members"), json={"add": ["B"]}).status_code == 403
    with TestClient(gapi.app) as v:
        login(v, "v1")
        assert "Fyr" in {t["name"] for t in v.get("/api/tags").json()}   # tagget kommer kun fra gruppe-animationen


def test_symbol_move_carries_group_membership(gapi):
    own = [fill("Pumpe")]
    assert gapi.put(f"/api/drawings/{gapi.did}/symbols/A/config", json={"config": {"op": "view", "anims": own}}).status_code == 200
    gapi.put(anims_url(gapi, gapi.g1, "A"), json={"anims": [fill("Fyr")]})
    svg2 = PIPE.replace('id="A"', 'id="A2"').replace('id="A_r"', 'id="A2_r"')
    assert gapi.post(f"/api/drawings/{gapi.did}/versions", json={"svg": svg2, "activate": True}).status_code == 201
    r = gapi.post(f"/api/drawings/{gapi.did}/symbols/A/move", json={"target": "A2"})
    assert r.status_code == 200, r.text
    groups = {g["name"]: g["members"] for g in gapi.get(url(gapi)).json()}
    assert groups == {"Fyr": ["A2", "B"], "Pumpegruppe": ["A2"]}
    assert list(gapi.get(url(gapi, f"/{gapi.g1}/anims")).json()) == ["A2"]


def test_move_translates_parts_and_reports_dropped_and_discarded(gapi):
    # gruppe-animation på en del (A_r) og en på en del der forsvinder (A_x findes ikke i det nye element)
    gapi.put(anims_url(gapi, gapi.g1, "A"), json={"anims": [{**fill("Fyr"), "part": "A_r"}]})
    svg2 = PIPE.replace('id="A"', 'id="A2"').replace('id="A_r"', 'id="A2_r"')
    assert gapi.post(f"/api/drawings/{gapi.did}/versions", json={"svg": svg2, "activate": True}).status_code == 201
    r = gapi.post(url(gapi, f"/{gapi.g1}/members/move"), json={"old": "A", "new": "A2"})
    assert r.status_code == 200 and r.json()["dropped"] == [] and r.json()["discarded"] == 0, r.text
    assert gapi.get(url(gapi, f"/{gapi.g1}/anims")).json()["A2"][0]["part"] == "A2_r"
    # sammenfald: g2 har både det gamle (A) og det nye (A2) medlem — det gamles animationer kasseres, og det meldes
    gapi.post(url(gapi, f"/{gapi.g2}/members"), json={"add": ["A2"]})
    gapi.post(url(gapi, f"/{gapi.g2}/members"), json={"remove": ["A"]})   # A er væk fra g2 (g2 har kun A2)
    r = gapi.post(url(gapi, f"/{gapi.g2}/members"), json={"add": ["A"]})   # genindsæt det forsvundne A som forældreløst medlem
    assert "A" in r.json()["members"]
    gapi.put(anims_url(gapi, gapi.g2, "A2"), json={"anims": [fill("Pumpe")]})
    r = gapi.post(url(gapi, f"/{gapi.g2}/members/move"), json={"old": "A", "new": "A2"})
    assert r.status_code == 200 and r.json()["members"] == ["A2"]
    assert gapi.get(url(gapi, f"/{gapi.g2}/anims")).json()["A2"][0]["src"] == "Pumpe"   # det nye medlems egne bevares
