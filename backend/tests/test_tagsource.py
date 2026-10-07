import math
import struct

import pytest

from app.services.tagsource import TagSourceError, apply_scaling, decode_words, parse_source


def _words(fmt: str, value) -> list[int]:
    return list(struct.unpack(">HH", struct.pack(fmt, value)))


@pytest.mark.parametrize("text, expected", [
    ("plc1:hr:100", "plc1:hr:100"),
    ("plc1:hr:100:uint", "plc1:hr:100"),
    ("plc1:HR:100:REAL", "plc1:hr:100:real"),
    ("plc1:ir:319", "plc1:ir:319"),
    ("plc1:coil:5", "plc1:coil:5"),
    ("plc1:di:255:bool", "plc1:di:255"),
    ("plc1:logic:1:Niveau", "plc1:logic:1:Niveau"),
    ("plc2:global:Mode", "plc2:global:Mode"),
    (" plc1 : hr : 7 : int ", "plc1:hr:7:int"),
])
def test_parse_valid(text, expected):
    assert str(parse_source(text)) == expected


@pytest.mark.parametrize("text, fragment", [
    ("", "mangler"),
    ("   ", "mangler"),
    ("plc1:hr", "forventet"),
    ("Plc1:hr:1", "PLC-nøgle"),
    ("plc1:xx:1", "Ukendt kildetype"),
    ("plc1:hr:abc", "heltal"),
    ("plc1:hr:256", "uden for hr 0-255"),
    ("plc1:ir:320", "uden for ir 0-319"),
    ("plc1:hr:255:real", "2 registre"),
    ("plc1:hr:-1", "uden for"),
    ("plc1:hr:1:float", "Ukendt datatype"),
    ("plc1:coil:1:int", "altid bool"),
    ("plc1:logic:5:X", "1-4"),
    ("plc1:logic:1", "forventet"),
    ("plc1:logic:1:ugyldigt navn", "variabelnavn"),
])
def test_parse_invalid(text, fragment):
    with pytest.raises(TagSourceError, match=fragment):
        parse_source(text)


def test_wide_unit_spans_two_registers():
    src = parse_source("plc1:hr:20:real")
    assert src.words == 2 and src.unit() == (20, 21)
    assert parse_source("plc1:hr:20").unit() == (20, 20)


def test_decode_high_word_first():
    assert decode_words(_words(">f", 21.5), "real") == pytest.approx(21.5)
    assert decode_words(_words(">i", -123456), "dint") == -123456
    assert decode_words(_words(">I", 4_000_000_000), "dword") == 4_000_000_000
    assert decode_words([0xFFFF], "int") == -1
    assert decode_words([0xFFFF], "uint") == 65535
    assert decode_words([1], "bool") is True


def test_decode_real_nan_is_float():
    assert math.isnan(decode_words([0x7FC0, 0x0000], "real"))


def test_scaling():
    assert apply_scaling(500, 0.1, 0) == pytest.approx(50.0)
    assert apply_scaling(10, 2, -5) == 15
    assert apply_scaling(True, 10, 1) is True  # bool skaleres ikke
    assert apply_scaling(7, 1, 0) == 7 and isinstance(apply_scaling(7, 1, 0), int)
