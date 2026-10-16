"""Simpel matematik på en tekst-binding (fx "x / 10"): validering og beregning.

Samme grammatik som frontend/src/lib/expression.ts (visningen regner i browseren; serveren afviser ugyldige
udtryk når en binding gemmes, så en tegning aldrig indeholder en formel der ikke kan beregnes):

  tal       1   2.5   2,5       (decimalkomma eller -punktum)
  værdien   x   værdi   parameter   (store/små bogstaver er ens)
  regnearter + - * / %  og parenteser; fortegn
  funktioner abs round floor ceil sqrt min max — flere værdier adskilles med ; (komma er decimalkomma)

Ingen eval: udtrykket parses til lukninger.
"""

from __future__ import annotations

import math
import re
from typing import Callable

MAX_LENGTH = 80
VARS = {"x", "værdi", "vaerdi", "parameter"}


def _round(v: float) -> float:
    return math.copysign(math.floor(abs(v) + 0.5), v) if v else 0.0  # .5 rundes væk fra 0, som i browseren


FUNCS: dict[str, tuple[int, int, Callable[[list[float]], float]]] = {
    "abs": (1, 1, lambda a: abs(a[0])),
    "round": (1, 1, lambda a: _round(a[0])),
    "floor": (1, 1, lambda a: float(math.floor(a[0]))),
    "ceil": (1, 1, lambda a: float(math.ceil(a[0]))),
    "sqrt": (1, 1, lambda a: math.sqrt(a[0]) if a[0] >= 0 else math.nan),
    "min": (2, 8, lambda a: min(a)),
    "max": (2, 8, lambda a: max(a)),
}

_NUM = re.compile(r"(\d+([.,]\d+)?|[.,]\d+)")
_ID = re.compile(r"[A-Za-zÆØÅæøå_][A-Za-zÆØÅæøå_0-9]*")
Compiled = Callable[[float], float]


class ExpressionError(ValueError):
    pass


def _tokenize(src: str) -> list[tuple[str, object]]:
    out: list[tuple[str, object]] = []
    i = 0
    while i < len(src):
        c = src[i]
        if c.isspace():
            i += 1
        elif m := _NUM.match(src, i):
            out.append(("num", float(m.group(0).replace(",", "."))))
            i = m.end()
        elif m := _ID.match(src, i):
            out.append(("id", m.group(0).lower()))
            i = m.end()
        elif c in "+-*/%();":
            out.append(("op", c))
            i += 1
        else:
            raise ExpressionError(f'Uventet tegn "{c}"')
    return out


def compile_expression(src: str) -> Compiled:
    if len(src) > MAX_LENGTH:
        raise ExpressionError(f"For langt (højst {MAX_LENGTH} tegn)")
    toks = _tokenize(src)
    if not toks:
        raise ExpressionError("Tomt udtryk")
    pos = 0

    def is_op(v: str) -> bool:
        return pos < len(toks) and toks[pos] == ("op", v)

    def eat(v: str) -> None:
        nonlocal pos
        if not is_op(v):
            raise ExpressionError('Manglende ")"' if v == ")" else f'Forventede "{v}"')
        pos += 1

    def expr() -> Compiled:
        nonlocal pos
        left = term()
        while is_op("+") or is_op("-"):
            op = toks[pos][1]
            pos += 1
            l, r = left, term()
            left = (lambda l, r: lambda x: l(x) + r(x))(l, r) if op == "+" else (lambda l, r: lambda x: l(x) - r(x))(l, r)
        return left

    def term() -> Compiled:
        nonlocal pos
        left = unary()
        while is_op("*") or is_op("/") or is_op("%"):
            op = toks[pos][1]
            pos += 1
            l, r = left, unary()
            if op == "*":
                left = (lambda l, r: lambda x: l(x) * r(x))(l, r)
            elif op == "/":
                left = (lambda l, r: lambda x: _div(l(x), r(x)))(l, r)
            else:
                left = (lambda l, r: lambda x: _mod(l(x), r(x)))(l, r)
        return left

    def unary() -> Compiled:
        nonlocal pos
        if is_op("-"):
            pos += 1
            inner = unary()
            return lambda x: -inner(x)
        if is_op("+"):
            pos += 1
            return unary()
        return primary()

    def primary() -> Compiled:
        nonlocal pos
        if pos >= len(toks):
            raise ExpressionError("Udtrykket slutter for tidligt")
        kind, val = toks[pos]
        pos += 1
        if kind == "num":
            number = float(val)  # type: ignore[arg-type]
            return lambda x: number
        if kind == "id":
            name = str(val)
            if is_op("("):
                spec = FUNCS.get(name)
                if spec is None:
                    raise ExpressionError(f'Ukendt funktion "{name}" (brug {", ".join(FUNCS)})')
                pos += 1
                args = [expr()]
                while is_op(";"):
                    pos += 1
                    args.append(expr())
                eat(")")
                lo, hi, fn = spec
                if not lo <= len(args) <= hi:
                    count = str(lo) if lo == hi else f"{lo}-{hi}"
                    raise ExpressionError(f"{name} tager {count} værdi{'er (adskilt med ;)' if hi > 1 else ''}")
                return lambda x: fn([a(x) for a in args])
            if name not in VARS:
                raise ExpressionError(f'Ukendt navn "{name}" — brug x (tagets værdi)')
            return lambda x: x
        if val == "(":
            inner = expr()
            eat(")")
            return inner
        raise ExpressionError(f'Uventet "{val}"')

    result = expr()
    if pos < len(toks):
        raise ExpressionError(f'Uventet "{toks[pos][1]}" — mangler der et regnetegn (+ - * /)?')
    return result


def _div(a: float, b: float) -> float:
    return a / b if b else math.nan  # division med 0 = ingen værdi (som i browseren: ikke et endeligt tal)


def _mod(a: float, b: float) -> float:
    return math.fmod(a, b) if b else math.nan  # fmod følger fortegnet på a — samme som JavaScripts %


def evaluate(src: str, x: float) -> float | None:
    """Beregn udtrykket; None hvis resultatet ikke er et endeligt tal."""
    v = compile_expression(src)(x)
    return v if math.isfinite(v) else None


def validate_expression(src: str) -> str:
    """Normaliser (trim) og valider; kaster ExpressionError. Tom streng = ingen beregning."""
    text = (src or "").strip()
    if text:
        compile_expression(text)
    return text
