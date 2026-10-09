"""Tag-kilder: hvor i hvilken PLC et tag får sin værdi fra.

Grammatik (docs/RESEARCH_OG_DESIGN.md §3.2):
    <plc>:hr:<addr>[:<datatype>]      datatype: uint (default) | int | dint | dword | real
    <plc>:ir:<addr>[:<datatype>]
    <plc>:coil:<addr>
    <plc>:di:<addr>
    <plc>:logic:<program 1-4>:<variabelnavn>
    <plc>:global:<variabelnavn>
    <plc>:rtu:<slave 1-247>:<hr|ir|coil|di>:<addr>[:<datatype>]                  slave på PLC'ens RS485-bus
    <plc>:mbx:<board>:<kanal A-H|1-8>:<slave>:<hr|ir|coil|di>:<addr>[:<datatype>] slave bag et expansion board

Eksterne kilder læses/skrives via PLC'ens /api/ext (firmware ≥ v7.9.68.123, docs/HYPERVISIONPLC_ANALYSE.md §7).

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
EXT_ADDR_MAX = 65535
EXT_KINDS = {"hr": "hr", "ir": "ir", "coil": "coil", "coils": "coil", "di": "di"}
CHANNELS = "ABCDEFGH"
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
    bus: str | None = None      # None = PLC'ens egne registre; "rtu" = RS485-slave; "mbx" = slave bag expansion board
    slave: int | None = None
    board: int | None = None
    channel: str | None = None  # A-H

    @property
    def words(self) -> int:
        return 2 if self.datatype in WIDE_TYPES and self.kind in ("hr", "ir") else 1

    @property
    def is_register(self) -> bool:
        """PLC'ens egne registre (bulk-læsning og SSE). Eksterne registre er `is_external`."""
        return self.kind in ADDR_COUNT and self.bus is None

    @property
    def is_external(self) -> bool:
        return self.bus is not None

    @property
    def ext_group(self) -> tuple[str, int | None, str | None, int, str]:
        """(bus, board, kanal, slave, type) — én gruppe = samme enhed og registertype."""
        assert self.bus is not None and self.slave is not None
        return (self.bus, self.board, self.channel, self.slave, self.kind)

    @property
    def device(self) -> str:
        """Kort beskrivelse af hvor værdien kommer fra (til fejlbeskeder)."""
        if self.bus == "rtu":
            return f"RS485-slave {self.slave}"
        if self.bus == "mbx":
            return f"slave {self.slave} på expansion board {self.board} kanal {self.channel}"
        return f"PLC {self.plc}"

    def unit(self) -> tuple[int, int]:
        """(første, sidste) adresse — til poll-planlæggeren."""
        assert self.addr is not None
        return (self.addr, self.addr + self.words - 1)

    def __str__(self) -> str:
        if self.bus is not None:
            prefix = (f"{self.plc}:rtu:{self.slave}" if self.bus == "rtu"
                      else f"{self.plc}:mbx:{self.board}:{self.channel}:{self.slave}")
            dt = f":{self.datatype}" if self.kind in ("hr", "ir") and self.datatype != "uint" else ""
            return f"{prefix}:{self.kind}:{self.addr}{dt}"
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

    if kind == "rtu":
        if len(parts) not in (5, 6):
            raise TagSourceError(f"Ugyldig kilde '{text}': forventet <plc>:rtu:<slave>:<type>:<adresse>[:datatype] "
                                 "(fx plc1:rtu:90:hr:0)")
        return _ext(plc, "rtu", None, None, parts[2], parts[3:], text)
    if kind == "mbx":
        if len(parts) not in (7, 8):
            raise TagSourceError(f"Ugyldig kilde '{text}': forventet <plc>:mbx:<board>:<kanal>:<slave>:<type>:<adresse>"
                                 "[:datatype] (fx plc1:mbx:1:D:1:coil:0)")
        board = _parse_int(parts[2], "board-nummer")
        if not 1 <= board <= 16:
            raise TagSourceError(f"Board-nummer skal være 1-16, ikke {board}")
        ch = parts[3].upper()
        if ch.isdigit() and 1 <= int(ch) <= len(CHANNELS):
            ch = CHANNELS[int(ch) - 1]
        if len(ch) != 1 or ch not in CHANNELS:
            raise TagSourceError(f"Kanal skal være A-H eller 1-8, ikke '{parts[3]}'")
        return _ext(plc, "mbx", board, ch, parts[4], parts[5:], text)

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

    raise TagSourceError(f"Ukendt kildetype '{kind}' (brug hr, ir, coil, di, logic, global, rtu eller mbx)")


def _ext(plc: str, bus: str, board: int | None, channel: str | None, slave_text: str, rest: list[str],
         text: str) -> TagSource:
    """Ekstern kilde: <slave>, derefter <type>:<adresse>[:datatype] (som de interne)."""
    slave = _parse_int(slave_text, "slave-adresse")
    if not 1 <= slave <= 247:
        raise TagSourceError(f"Slave-adresse skal være 1-247, ikke {slave}")
    kind = EXT_KINDS.get(rest[0].lower())
    if kind is None:
        raise TagSourceError(f"Ukendt registertype '{rest[0]}' (brug hr, ir, coil eller di)")
    addr = _parse_int(rest[1], "adresse")
    if kind in ("coil", "di"):
        if len(rest) == 3 and rest[2].lower() != "bool":
            raise TagSourceError(f"{kind} er altid bool — datatype '{rest[2]}' giver ikke mening")
        datatype = "bool"
    else:
        datatype = rest[2].lower() if len(rest) == 3 else "uint"
        if datatype not in REGISTER_TYPES:
            raise TagSourceError(f"Ukendt datatype '{datatype}' (brug {', '.join(REGISTER_TYPES)})")
    source = TagSource(plc=plc, kind=kind, datatype=datatype, addr=addr, bus=bus, slave=slave, board=board,
                       channel=channel)
    first, last = source.unit()
    if first < 0 or last > EXT_ADDR_MAX:
        extra = f" ({datatype} bruger 2 registre)" if source.words == 2 else ""
        raise TagSourceError(f"Adresse {addr} er uden for 0-{EXT_ADDR_MAX}{extra}")
    return source


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
