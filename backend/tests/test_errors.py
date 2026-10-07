from app.api.errors import format_validation_errors
from app.plc.errors import extract_error_message


def test_plc_error_json():
    assert extract_error_message(400, {"error": "Count must be 1-200", "status": 400}, "") == "Count must be 1-200"


def test_plc_error_blank_falls_through():
    assert extract_error_message(500, {"error": "   "}, "") == "HTTP 500 fra PLC"


def test_plc_error_non_json_text():
    assert extract_error_message(502, None, "<html>Bad gateway</html>") == "<html>Bad gateway</html>"


def test_plc_error_list_form():
    assert extract_error_message(422, [{"msg": "a"}, {"msg": "b"}], "") == "a; b"


def test_plc_error_empty():
    assert extract_error_message(503, None, "") == "HTTP 503 fra PLC"


def test_validation_errors_flattened_to_string():
    errors = [
        {"type": "missing", "loc": ("body", "base_url"), "msg": "Field required"},
        {"type": "extra_forbidden", "loc": ("body", "foo"), "msg": "Extra inputs are not permitted"},
        {"type": "float_parsing", "loc": ("body", "scale"), "msg": "Input should be a valid number"},
    ]
    text = format_validation_errors(errors)
    assert isinstance(text, str)
    assert "base_url: mangler" in text and "foo: ukendt felt" in text and "scale: Input should be a valid number" in text
