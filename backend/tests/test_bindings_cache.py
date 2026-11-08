"""Gemte beregninger for begrænsede brugere (v4.12.0, BUGS.md v0.131.4): effektive bindinger og synlige tags beregnes kun
forfra, når konfigurationen eller tegningen er ændret — aldrig forkert, og ikke ved hver forespørgsel."""

from tests.test_scope import ADMIN_PW, SVG_A, _as_admin, _as_op, setup  # noqa: F401 — fixture


def _stats(c):
    return dict(c.app.state.drawing_service.cache_stats)


def test_effective_bindings_are_computed_once_until_something_changes(setup):
    c, a, b = setup
    ds = c.app.state.drawing_service
    ds._eff.clear()
    base = _stats(c)
    first = ds.effective_bindings(a)
    again = ds.effective_bindings(a)
    assert first == again and again is not ds._eff[a][1]                      # en kopi: kaldere kan ikke ødelægge cachen
    s = _stats(c)
    assert s["misses"] - base["misses"] == 1 and s["hits"] - base["hits"] == 1
    _as_admin(c)
    assert c.put(f"/api/drawings/{a}/bindings/Knap_A", json={"bindings": []}).status_code == 200     # ændring → forfra
    assert "Motor_A" not in {t for x in ds.effective_bindings(a) for t in (x.get("tag"),)}
    assert _stats(c)["misses"] - s["misses"] == 1


def test_visible_tags_follow_every_kind_of_change_immediately(setup):
    c, a, b = setup
    scope = c.app.state.scope_service
    from app.services.auth import CurrentUser
    u = CurrentUser(username="op_a", role="operator", must_change_password=False, token_hash="", drawings=[a])
    assert scope.visible_tags(u) == {"Motor_A", "Niveau_A"}
    assert scope.visible_tags(u) == {"Motor_A", "Niveau_A"}                    # fra den gemte beregning
    _as_admin(c)
    cfg = {"op": "view", "anims": [{"part": "all", "type": "fill", "src": "Motor_B", "params": {}}]}
    assert c.put(f"/api/drawings/{a}/symbols/Knap_A/config", json={"config": cfg}).status_code == 200
    assert "Motor_B" in scope.visible_tags(u)                                 # symbol-opsætning
    assert c.delete(f"/api/drawings/{a}/symbols/Knap_A/config").status_code in (200, 204)
    assert "Motor_B" not in scope.visible_tags(u)
    # en ny version af tegningen (en anden SVG) giver andre automatiske bindinger
    svg2 = SVG_A.replace("</svg>", '<text id="Motor_B">-</text></svg>')
    assert c.post(f"/api/drawings/{a}/versions", json={"svg": svg2, "comment": "ny"}).status_code in (200, 201)
    assert "Motor_B" in scope.visible_tags(u)
    # adgang: en anden tegning i brugerens liste giver et andet resultat (nøglen er listen af tegninger)
    assert "Niveau_B" in scope.visible_tags(CurrentUser(username="op_a", role="operator", must_change_password=False,
                                                       token_hash="", drawings=[a, b]))


def test_returned_sets_are_copies(setup):
    c, a, b = setup
    scope = c.app.state.scope_service
    from app.services.auth import CurrentUser
    u = CurrentUser(username="op_a", role="operator", must_change_password=False, token_hash="", drawings=[a])
    first = scope.visible_tags(u)
    first.add("ØDELÆGGER")
    assert "ØDELÆGGER" not in scope.visible_tags(u)


def test_only_configuration_writes_invalidate(setup):
    """Sessioner, audit og alarmer må ikke tømme cachen (ellers hjælper den ikke) — tags og tegninger skal."""
    c, a, b = setup
    db = c.app.state.drawing_service.db
    g = db.config_gen
    db.touch_session("findes-ikke", 1.0)
    c.app.state.alarm_service.db.list_alarm_events(5)
    assert db.config_gen == g
    c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})        # sessioner skrives
    assert db.config_gen == g
    assert c.patch("/api/tags/Niveau_A", json={"description": "x"}).status_code == 200
    assert db.config_gen > g


def test_metrics_expose_the_cache():
    from app.services.metrics import render
    text = render({"version": {"version": "4", "build": "1"}, "plcs": [], "bindings_cache": {"hits": 7, "misses": 2}})
    assert "scada_bindings_cache_hits_total 7" in text and "scada_bindings_cache_misses_total 2" in text


def test_deleting_and_recreating_a_drawing_with_the_same_id_is_not_served_stale(setup):
    c, a, b = setup
    from app.services.auth import CurrentUser
    scope = c.app.state.scope_service
    u = CurrentUser(username="op_a", role="operator", must_change_password=False, token_hash="", drawings=[a])
    assert "Motor_A" in scope.visible_tags(u)
    _as_admin(c)
    assert c.delete(f"/api/drawings/{a}").status_code in (200, 204)
    new = c.post("/api/drawings", json={"name": "Anlæg A", "svg": SVG_A}).json()["drawing"]["id"]
    assert new == a                                                           # samme id igen, uden de gamle bindinger
    assert "Motor_A" not in scope.visible_tags(u) and "Niveau_A" in scope.visible_tags(u)


def test_cache_is_bounded(setup):
    c, a, b = setup
    from app.services import drawings as dmod
    ds = c.app.state.drawing_service
    ds._eff.clear()
    ds._eff.update({f"x{i}": ((0,), []) for i in range(dmod.CACHE_MAX)})
    ds.effective_bindings(a)
    assert len(ds._eff) == 1                                                  # tømt og genopbygget
