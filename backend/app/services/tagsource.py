"""Tag-kilder: hvor i hvilken PLC et tag får sin værdi fra.

Grammatik (docs/RESEARCH_OG_DESIGN.md §3.2):
    <plc>:hr:<addr>[:<datatype>]      datatype: uint (default) | int | dint | dword | real
    <plc>:ir:<addr>[:<datatype>]
    <plc>:coil:<addr>
    <plc>:di:<addr>
    <plc>:logic:<program 1-4>:<variabelnavn>
    <plc>:global:<variabelnavn>

32-bit typer fylder 2 registre, high word først (PLC api_handlers.cpp).
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from typing import Any

PLC_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
VAR_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\[\]]{0,63}$")

# Adresserum i firmware v7.9.68.122 (include/constants.h): HR 256, IR 320, coils/DI 256.
ADDR_COUNT = {"hr": 256, "ir": 320, "coil": 256, "di": 256}
REGISTER_TYPES = ("uint", "int", "dint", "dword", "real")
WIDE_TYPES = ("dint", "dword", "real")

# ST-typer fra GET /api/logic/{id} → SCADA-datatype
ST_TYPE_MAP = {
    "BOOL": "bool", "INT": "int", "DINT": "dint", "DWORD": "dword",
    "REAL": "real", "TIME": "dint", "STRING": "string",
}


class TagSourceError(ValueError):
    pass


@dataclass(frozen=True)
class TagSource:
    plc: str
    kind: str  # hr | ir | coil | di | logic | global
    datatype: str
    addr: int | None = None
    program: int | None = None
    var: str | None = None

    @property
    def words(self) -> int:
        return 2 if self.datatype in WIDE_TYPES and self.kind in ("hr", "ir") else 1

    @property
    def is_register(self) -> bool:
        return self.kind in ADDR_COUNT

    def unit(self) -> tuple[int, int]:
        """(første, sidste) adresse — til poll-planlæggeren."""
        assert self.addr is not None
        return (self.addr, self.addr + self.words - 1)

    def __str__(self) -> str:
        if self.kind == "logic":
            return f"{self.plc}:logic:{self.program}:{self.var}"
        if self.kind == "global":
            return f"{self.plc}:global:{self.var}"
        if self.kind in ("hr", "ir") and self.datatype != "uint":
            return f"{self.plc}:{self.kind}:{self.addr}:{self.datatype}"
        return f"{self.plc}:{self.kind}:{self.addr}"


def parse_source(text: str) -> TagSource:
    if not isinstance(text, str) or not text.strip():
        raise TagSourceError("Kilde mangler (fx plc1:hr:100 eller plc1:logic:1:Niveau)")
    parts = [p.strip() for p in text.strip().split(":")]
    if len(parts) < 3:
        raise TagSourceError(f"Ugyldig kilde '{text}': forventet <plc>:<type>:<adresse> (fx plc1:hr:100)")
    plc, kind = parts[0], parts[1].lower()
    if not PLC_KEY_RE.match(plc):
        raise TagSourceError(f"Ugyldig PLC-nøgle '{plc}' (små bogstaver, tal og _; starter med bogstav)")

    if kind in ADDR_COUNT:
        if len(parts) > 4:
            raise TagSourceError(f"Ugyldig kilde '{text}': for mange dele")
        addr = _parse_int(parts[2], "adresse")
        if kind in ("coil", "di"):
            if len(parts) == 4 and parts[3].lower() != "bool":
                raise TagSourceError(f"{kind} er altid bool — datatype '{parts[3]}' giver ikke mening")
            datatype = "bool"
        else:
            datatype = parts[3].lower() if len(parts) == 4 else "uint"
            if datatype not in REGISTER_TYPES:
                raise TagSourceError(f"Ukendt datatype '{datatype}' (brug {', '.join(REGISTER_TYPES)})")
        source = TagSource(plc=plc, kind=kind, datatype=datatype, addr=addr)
        first, last = source.unit()
        limit = ADDR_COUNT[kind] - 1
        if first < 0 or last > limit:
            extra = f" ({datatype} bruger 2 registre)" if source.words == 2 else ""
            raise TagSourceError(f"Adresse {addr} er uden for {kind} 0-{limit}{extra}")
        return source

    if kind == "logic":
        if len(parts) != 4:
            raise TagSourceError(f"Ugyldig kilde '{text}': forventet <plc>:logic:<program 1-4>:<variabel>")
        program = _parse_int(parts[2], "programnummer")
        if not 1 <= program <= 4:
            raise TagSourceError(f"ST-programnummer skal være 1-4, ikke {program}")
        return TagSource(plc=plc, kind="logic", datatype="auto", program=program, var=_parse_var(parts[3]))

    if kind == "global":
        if len(parts) != 3:
            raise TagSourceError(f"Ugyldig kilde '{text}': forventet <plc>:global:<variabel>")
        return TagSource(plc=plc, kind="global", datatype="auto", var=_parse_var(parts[2]))

    raise TagSourceError(f"Ukendt kildetype '{kind}' (brug hr, ir, coil, di, logic eller global)")


def _parse_int(text: str, what: str) -> int:
    try:
        return int(text, 10)
    except ValueError:
        raise TagSourceError(f"Ugyldig {what} '{text}' — skal være et heltal") from None


def _parse_var(text: str) -> str:
    if not VAR_NAME_RE.match(text):
        raise TagSourceError(f"Ugyldigt variabelnavn '{text}'")
    return text


def decode_words(words: list[int], datatype: str) -> int | float | bool:
    """Afkod rå 16-bit ord (high word først) til en værdi."""
    if datatype == "bool":
        return bool(words[0])
    if datatype == "uint":
        return words[0] & 0xFFFF
    if datatype == "int":
        return struct.unpack(">h", struct.pack(">H", words[0] & 0xFFFF))[0]
    packed = struct.pack(">HH", words[0] & 0xFFFF, words[1] & 0xFFFF)
    if datatype == "dint":
        return struct.unpack(">i", packed)[0]
    if datatype == "dword":
        return struct.unpack(">I", packed)[0]
    if datatype == "real":
        return struct.unpack(">f", packed)[0]
    raise ValueError(f"ukendt datatype {datatype}")


def apply_scaling(value: Any, scale: float, offset: float) -> Any:
    """Teknisk værdi = rå * scale + offset. Bool/strenge skaleres ikke."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    if scale == 1 and offset == 0:
        return value
    return value * scale + offset
