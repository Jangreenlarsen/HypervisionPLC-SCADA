"""Poll-planlægger: saml de adresser der skal læses til så få bulk-kald som muligt.

Input er "enheder" — en enkelt adresse, eller et 32-bit-par (addr, addr+1) som ALDRIG
må deles over to kald (ellers kan high og low word komme fra hver sin PLC-cyklus).
"""

from __future__ import annotations

from dataclasses import dataclass

from .client import BULK_MAX, EXT_MAX

# Huller op til denne størrelse flettes ind i samme kald: et ekstra register i
# svaret koster ~25 bytes, et ekstra kald koster en hel request af rate-budgettet.
DEFAULT_GAP = {"hr": 32, "ir": 32, "coil": 64, "di": 64}


@dataclass(frozen=True)
class ReadRange:
    kind: str
    start: int
    count: int

    @property
    def end(self) -> int:
        return self.start + self.count - 1


def plan_reads(
    units: dict[str, set[tuple[int, int]]],
    gap: dict[str, int] | None = None,
) -> list[ReadRange]:
    """units: {kind: {(første, sidste), ...}} → sorteret liste af bulk-kald."""
    gap = gap or DEFAULT_GAP
    plan: list[ReadRange] = []
    for kind in ("hr", "ir", "coil", "di"):
        kind_units = sorted(units.get(kind, ()))
        if not kind_units:
            continue
        max_count = BULK_MAX[kind]
        max_gap = gap.get(kind, 0)
        start, end = kind_units[0]
        for first, last in kind_units[1:]:
            if last <= end:  # helt dækket af det aktuelle område
                continue
            fits = last - start + 1 <= max_count
            close = first - end - 1 <= max_gap
            if fits and close:
                end = max(end, last)
            else:
                plan.append(ReadRange(kind, start, end - start + 1))
                start, end = first, last
        plan.append(ReadRange(kind, start, end - start + 1))
    return plan


@dataclass(frozen=True)
class ExtRange:
    group: tuple  # (bus, board, kanal, slave, type)
    start: int
    count: int

    @property
    def kind(self) -> str:
        return self.group[4]


def plan_ext_reads(units: dict[tuple, set[tuple[int, int]]]) -> list[ExtRange]:
    """Eksterne slaver: kun ÆGTE sammenhængende adresser samles (højst 16) — ingen huller, for en slave kan
    afvise hele læsningen hvis den rammer et register den ikke har. 32-bit-par deles aldrig."""
    plan: list[ExtRange] = []
    for group in sorted(units, key=lambda g: tuple("" if x is None else str(x) for x in g)):
        items = sorted(units[group])
        start, end = items[0]
        for first, last in items[1:]:
            if last <= end:
                continue
            if first <= end + 1 and last - start + 1 <= EXT_MAX:
                end = max(end, last)
            else:
                plan.append(ExtRange(group, start, end - start + 1))
                start, end = first, last
        plan.append(ExtRange(group, start, end - start + 1))
    return plan
