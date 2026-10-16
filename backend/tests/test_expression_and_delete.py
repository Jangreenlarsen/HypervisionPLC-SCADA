"""Beregning på tekst-bindinger (v0.41.0) og sletning af tegning med oversigt over hvad det rammer (v0.42.0)."""

import math

import pytest

from app.services.expression import ExpressionError, compile_expression, evaluate, validate_expression
from tests.test_drawings_api import SVG, _create, api  # noqa: F401  (api = fixture)


# ------------------------------------------------------------------ udtryk (samme grammatik som frontend/src/lib/expression.ts)

@pytest.mark.parametrize("src,x,expected", [
    ("x / 10", 128, 12.8), ("parameter / 10", 128, 12.8), ("VÆRDI / 10", 128, 12.8), ("x * 1,8 + 32", 100, 212),
    ("round(x / 10)", 125, 13), ("round(x / 10)", -125, -13), ("abs(x)", -4, 4), ("min(x; 5)", 9, 5), ("max(x; 5)", 9, 9),
    ("sqrt(x)", 16, 4), ("floor(x / 3)", 10, 3), ("ceil(x / 3)", 10, 4), ("x % 5", 12, 2), ("-x + 1", 3, -2),
    ("(x + 2) * 3", 1, 9), ("-12 % 5", 0, -2),   # fmod følger fortegnet på første led, som JavaScript
])
def test_expressions_evaluate_like_the_browser(src, x, expected):
    assert evaluate(src, x) == pytest.approx(expected)


def test_division_by_zero_and_sqrt_of_negative_give_no_value():
    assert evaluate("x / 0", 5) is None
    assert evaluate("x % 0", 5) is None
    assert evaluate("sqrt(x)", -1) is None
    assert math.isnan(compile_expression("x / 0")(1.0))


@pytest.mark.parametrize("src,part", [
    ("x +", "slutter for tidligt"), ("foo", "Ukendt navn"), ("bar(x)", "Ukendt funktion"), ("(x", "Manglende"),
    ("x $ 2", "Uventet tegn"), ("x x", "regnetegn"), ("min(x)", "tager 2-8"), ("", "Tomt"),
    ("x + " * 30 + "1", "For langt"),
])
def test_invalid_expressions_give_danish_errors(src, part):
    with pytest.raises(ExpressionError, match=part):
        compile_expression(src)


def test_validate_trims_and_empty_means_no_calculation():
    assert validate_expression("  x / 10 ") == "x / 10"
    assert validate_expression("") == ""
    assert validate_expression("   ") == ""        # også whitespace-only
    assert validate_expression(None) == ""         # type: ignore[arg-type]


def _bind(api, did, params):
    return api.put(f"/api/drawings/{did}/bindings/Niveau", json={"bindings": [{"tag": "Niveau", "anim": "text", "params": params}]})


def test_text_binding_saves_a_valid_expression_and_rejects_an_invalid_one(api):
    did = _create(api)["drawing"]["id"]
    r = _bind(api, did, {"expression": " x / 10 ", "decimals": 1})
    assert r.status_code == 200, r.text
    saved = api.get(f"/api/drawings/{did}/view").json()["bindings"]
    assert next(b for b in saved if b["element"] == "Niveau")["params"]["expression"] == "x / 10"
    r = _bind(api, did, {"expression": "x +"})
    assert r.status_code == 400 and "slutter for tidligt" in r.text
    assert _bind(api, did, {"expression": "x" + " + 1" * 40}).status_code == 400      # over 80 tegn
    assert _bind(api, did, {"expression": "   "}).status_code == 200                  # whitespace-only = ingen beregning
    saved = api.get(f"/api/drawings/{did}/view").json()["bindings"]
    assert next(b for b in saved if b["element"] == "Niveau")["params"].get("expression", "") == ""


# ------------------------------------------------------------------ slet tegning: hvad rammer det?

def test_usage_counts_versions_bindings_goto_start_and_users(api):
    target = _create(api, "Detalje")["drawing"]["id"]
    other = _create(api, "Oversigt")["drawing"]["id"]
    assert api.put(f"/api/drawings/{target}/bindings/Niveau",
                   json={"bindings": [{"tag": "Niveau", "anim": "text"}, {"tag": "Pumpe", "anim": "fill"}]}).status_code == 200
    assert api.post(f"/api/drawings/{target}/versions", json={"svg": SVG, "activate": False}).status_code in (200, 201)
    assert api.put(f"/api/drawings/{other}/bindings/Tank",
                   json={"bindings": [{"anim": "click:goto", "params": {"drawing": target}}]}).status_code == 200
    assert api.put("/api/drawings/start", json={"drawing": target}).status_code == 200
    assert api.post("/api/users", json={"username": "vagt", "role": "viewer", "password": "Hemmelig-123",
                                        "drawings": [target]}).status_code in (200, 201)
    u = api.get(f"/api/drawings/{target}/usage").json()
    assert u["name"] == "Detalje" and u["versions"] == 2 and u["bindings"] == 2
    assert u["goto_from"] == ["Oversigt"] and u["start"] is True and u["users"] == ["vagt"]
    # den anden tegning henviser ikke fra sig selv, og er hverken start eller har brugere
    v = api.get(f"/api/drawings/{other}/usage").json()
    assert v["goto_from"] == [] and v["start"] is False and v["users"] == [] and v["bindings"] == 1


def test_usage_of_unknown_drawing_is_404_and_requires_engineer(api):
    assert api.get("/api/drawings/findes-ikke/usage").status_code == 404
    did = _create(api)["drawing"]["id"]
    api.post("/api/auth/logout")
    assert api.get(f"/api/drawings/{did}/usage").status_code == 401


def test_delete_removes_everything_and_clears_the_start_drawing(api):
    did = _create(api, "Slettes")["drawing"]["id"]
    keep = _create(api, "Bliver")["drawing"]["id"]
    api.put(f"/api/drawings/{did}/bindings/Niveau", json={"bindings": [{"tag": "Niveau", "anim": "text"}]})
    api.put("/api/drawings/start", json={"drawing": did})
    assert api.delete(f"/api/drawings/{did}").status_code == 204
    assert api.get(f"/api/drawings/{did}").status_code == 404
    assert api.get(f"/api/drawings/{did}/usage").status_code == 404
    assert api.delete(f"/api/drawings/{did}").status_code == 404                      # allerede væk
    left = api.get("/api/drawings").json()
    assert [d["id"] for d in left] == [keep] and not any(d["start"] for d in left)    # start nulstillet — ingen start-tegning
    assert api.get("/api/audit?action=drawing.delete").json()[0]["target"] == did
