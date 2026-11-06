"""Tegneredskaberne fra v3.33.0: alt hvad Tegn nu laver, skal overleve serverens rensning uændret."""

from app.services.svg_sanitize import sanitize_svg

PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
SVG = f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="200" height="100">
<defs>
<marker id="hv_pil_000000" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse" markerUnits="strokeWidth"><path d="M0,0 L10,5 L0,10 Z" fill="#000000"/></marker>
<linearGradient id="hv_grad_r1" x1="0" y1="0.5" x2="1" y2="0.5"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#000"/></linearGradient>
<filter id="hv_skygge_r1" x="-50%" y="-50%" width="200%" height="200%"><feDropShadow dx="3" dy="3" stdDeviation="2" flood-color="#000" flood-opacity="0.5"/></filter>
</defs>
<g class="layer" data-hv-locked="1"><title>Baggrund</title>
<rect id="r1" x="1" y="1" width="50" height="20" fill="url(#hv_grad_r1)" filter="url(#hv_skygge_r1)" stroke-dasharray="8 4" stroke-linecap="round" stroke-linejoin="bevel"/>
<line id="l1" x1="0" y1="0" x2="10" y2="10" stroke="#000" marker-start="url(#hv_pil_000000)" marker-end="url(#hv_pil_000000)"/>
<polygon id="p1" points="10,0 20,10 0,10" data-hv-shape='{{"k":"star","n":5,"ri":0.5}}'/>
<image id="i1" x="0" y="0" width="10" height="10" preserveAspectRatio="xMidYMid meet" xlink:href="{PNG}"/>
</g></svg>'''


def test_new_tool_output_survives_sanitizer():
    res = sanitize_svg(SVG)
    assert not res.removed_elements and not res.removed_attributes, (res.removed_elements, res.removed_attributes)
    for needle in ("marker-end=", "orient=\"auto-start-reverse\"", "feDropShadow", "url(#hv_grad_r1)", "stroke-dasharray",
                   "data-hv-shape", "data-hv-locked", PNG):
        assert needle in res.svg, needle


def test_svg_image_or_external_image_is_still_removed():
    bad = SVG.replace(PNG, "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=")
    assert "data:image/svg" not in sanitize_svg(bad).svg
    ext = SVG.replace(PNG, "https://example.com/x.png")
    assert "example.com" not in sanitize_svg(ext).svg
