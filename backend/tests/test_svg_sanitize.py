import pytest

from app.services.svg_sanitize import SvgError, index_svg, sanitize_svg

HEAD = '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 100 50">'


def clean(body: str, head: str = HEAD) -> str:
    return sanitize_svg(head + body + "</svg>").svg


def test_keeps_normal_drawing():
    out = clean('<g id="Pumpe1"><rect id="r" x="1" y="2" width="3" height="4" fill="url(#grad)"/>'
                '<text id="T1">12.3</text></g><defs><linearGradient id="grad"/></defs>')
    assert 'id="Pumpe1"' in out and 'fill="url(#grad)"' in out and ">12.3<" in out


@pytest.mark.parametrize("payload, forbidden", [
    ('<script>alert(1)</script>', "alert"),
    ('<rect onclick="alert(1)" width="1" height="1"/>', "onclick"),
    ('<rect ONLOAD="alert(1)" width="1" height="1"/>', "alert"),
    ('<a xlink:href="javascript:alert(1)"><rect/></a>', "javascript"),
    ('<use xlink:href="http://evil.example/x.svg#a"/>', "evil"),
    ('<use href="data:image/svg+xml;base64,PHN2Zz4="/>', "data:"),
    ('<foreignObject><div xmlns="http://www.w3.org/1999/xhtml">hej</div></foreignObject>', "foreignObject"),
    ('<animate attributeName="href" to="javascript:alert(1)"/>', "javascript"),
    ('<set attributeName="onmouseover" to="alert(1)"/>', "alert"),
    ('<style>@import url(http://evil.example/a.css); rect{fill:red}</style>', "evil"),
    ('<rect style="fill:url(http://evil.example/x)" width="1" height="1"/>', "evil"),
    ('<rect fill="url(https://evil.example/p)" width="1" height="1"/>', "evil"),
    ('<image href="data:image/svg+xml;base64,PHN2Zz4=" width="1" height="1"/>', "svg+xml"),
    ('<iframe src="http://evil.example"/>', "iframe"),
])
def test_removes_dangerous_content(payload, forbidden):
    out = clean(payload)
    assert forbidden not in out


def test_keeps_raster_data_image_and_reports():
    result = sanitize_svg(HEAD + '<image href="data:image/png;base64,iVBORw0KGgo=" width="1" height="1"/>'
                          '<script>x</script><rect onclick="x"/></svg>')
    assert "data:image/png;base64" in result.svg
    assert result.removed_elements == {"script": 1}
    assert result.removed_attributes == {"onclick": 1}


def test_inkscape_label_kept_other_inkscape_removed():
    head = HEAD.replace("<svg ", '<svg xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
                                 'xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd" ')
    result = sanitize_svg(head + '<sodipodi:namedview id="nv"/>'
                          '<rect id="rect12" inkscape:label="Pumpe1" inkscape:connector-curvature="0"/></svg>')
    assert "namedview" not in result.svg and "connector-curvature" not in result.svg
    assert result.labels == {"rect12": "Pumpe1"}
    assert index_svg(result.svg)["rect12"] == ("rect", "Pumpe1")


def test_rejects_entities_and_dtd():
    xxe = '<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]>' + HEAD + "<text>&x;</text></svg>"
    with pytest.raises(SvgError, match="DTD"):
        sanitize_svg(xxe)


@pytest.mark.parametrize("data, message", [
    ("", "tom"),
    ("   ", "tom"),
    ("<html></html>", "ikke en SVG"),
    ("ikke xml", "Ikke gyldig"),
    ('<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>', "viewBox"),
])
def test_rejects_invalid(data, message):
    with pytest.raises(SvgError, match=message):
        sanitize_svg(data)


def test_viewbox_added_from_width_height():
    result = sanitize_svg('<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="100"><rect/></svg>')
    assert 'viewBox="0 0 793.701 100"' in result.svg
    assert result.width == pytest.approx(793.7, abs=0.1)


def test_too_large():
    with pytest.raises(SvgError, match="for stor"):
        sanitize_svg(HEAD + "<!--" + "x" * (5 * 1024 * 1024) + "--></svg>")
