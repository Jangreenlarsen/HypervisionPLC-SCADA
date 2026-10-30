// Segment-display (v2.9.0): 7- eller 11-segment, 1–16 cifre, ét tal-tag. Ren logik — testet i segDisplay.test.ts.
//  · 7 segmenter: a–g + decimalpunkt (dp).
//  · 11 segmenter: a–f, midterstregen delt i g1/g2, to lodrette midtersegmenter (i øverst, l nederst) og dp — viser tal og de
//    fleste store bogstaver.
// Tegningen er et symbol (`segDisplaySymbol`): en gruppe med `data-hv-kind` og ét `data-hv-digit` pr. ciffer, hvert med
// segmenter (`data-hv-seg="a"` …). Animationen "Segmenter" (`renderSegments`) tænder/slukker segmenterne ud fra tallet.

export type SegKind = 7 | 11;
export const MIN_DIGITS = 1, MAX_DIGITS = 16;
export const SEG_ON = '#7cc47f', SEG_OFF = '#3d3d3d', SEG_BG = '#1f1f1f';

export const SEGMENTS: Record<SegKind, readonly string[]> = {
  7: ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'dp'],
  11: ['a', 'b', 'c', 'd', 'e', 'f', 'g1', 'g2', 'i', 'l', 'dp'],
};

/** 7-segment: tegn → tændte segmenter (uden dp). Små og store bogstaver slås op i den rækkefølge, de er skrevet. */
const SEVEN: Record<string, string> = {
  '0': 'abcdef', '1': 'bc', '2': 'abdeg', '3': 'abcdg', '4': 'bcfg', '5': 'acdfg', '6': 'acdefg', '7': 'abc', '8': 'abcdefg', '9': 'abcdfg',
  '-': 'g', '_': 'd', '=': 'dg', '°': 'abfg', ' ': '',
  A: 'abcefg', b: 'cdefg', C: 'adef', c: 'deg', d: 'bcdeg', E: 'adefg', F: 'aefg', G: 'acdef', H: 'bcefg', h: 'cefg', I: 'ef',
  J: 'bcde', L: 'def', n: 'ceg', o: 'cdeg', O: 'abcdef', P: 'abefg', q: 'abcfg', r: 'eg', S: 'acdfg', t: 'defg', U: 'bcdef',
  u: 'cde', y: 'bcdfg', Y: 'bcdfg', Z: 'abdeg',
};
/** 11-segment: bogstaver med de lodrette midtersegmenter (i/l) og delt midterstreg (g1/g2). Tal og tegn som i 7-segment. */
const ELEVEN: Record<string, readonly string[]> = {
  A: ['a', 'b', 'c', 'e', 'f', 'g1', 'g2'], C: ['a', 'd', 'e', 'f'], D: ['a', 'b', 'c', 'd', 'i', 'l'],
  E: ['a', 'd', 'e', 'f', 'g1'], F: ['a', 'e', 'f', 'g1'], G: ['a', 'c', 'd', 'e', 'f', 'g2'],
  H: ['b', 'c', 'e', 'f', 'g1', 'g2'], I: ['a', 'd', 'i', 'l'], J: ['b', 'c', 'd', 'e'], L: ['d', 'e', 'f'],
  O: ['a', 'b', 'c', 'd', 'e', 'f'], P: ['a', 'b', 'e', 'f', 'g1', 'g2'], S: ['a', 'c', 'd', 'f', 'g1', 'g2'],
  T: ['a', 'i', 'l'], U: ['b', 'c', 'd', 'e', 'f'], Y: ['b', 'c', 'd', 'f', 'g1', 'g2'], Z: ['a', 'b', 'd', 'e', 'g1', 'g2'],
};
const SYMBOLS_7 = /^[0-9\-_=° ]$/;

/** Tændte segmenter for ét tegn (uden dp), som mængde af segmentnavne. Ukendt tegn = tomt (slukket). */
export function segmentsFor(ch: string, kind: SegKind): Set<string> {
  if (kind === 11) {
    const own = ELEVEN[ch] ?? ELEVEN[ch.toUpperCase()];
    if (own) return new Set(own);
    if (!SYMBOLS_7.test(ch)) return new Set();
  }
  const spec = SEVEN[ch] ?? SEVEN[ch.toLowerCase()] ?? SEVEN[ch.toUpperCase()] ?? '';
  const out = new Set<string>();
  for (const c of spec) {
    if (kind === 11 && c === 'g') { out.add('g1'); out.add('g2'); } else out.add(c);   // midterstregen er delt i 11-segment
  }
  return out;
}

export interface SegParams { align?: 'right' | 'left'; zeros?: boolean; on?: string; off?: string }
export interface Cell { ch: string; dp: boolean }

/**
 * Teksten fordelt på `count` cifre. "." og "," hører til tegnet foran (dp). Bliver teksten for lang, vises "-" i alle cifre
 * (overløb). `zeros`: et tal fyldes op med foranstillede nuller (fortegnet bliver stående forrest).
 */
export function layoutDigits(text: string, count: number, p: SegParams = {}): Cell[] {
  const n = Math.min(MAX_DIGITS, Math.max(MIN_DIGITS, Math.round(count) || MIN_DIGITS));
  const cells: Cell[] = [];
  for (const ch of text.replace(/\s+$/g, '')) {
    if ((ch === '.' || ch === ',') && cells.length && !cells[cells.length - 1].dp) cells[cells.length - 1].dp = true;
    else cells.push({ ch: ch === ',' ? '.' : ch, dp: false });
  }
  if (cells.length > n) return Array.from({ length: n }, () => ({ ch: '-', dp: false }));
  if (p.zeros && /^-?\d/.test(text)) {
    const neg = cells[0]?.ch === '-';
    const zeros = Array.from({ length: n - cells.length }, () => ({ ch: '0', dp: false }));
    cells.splice(neg ? 1 : 0, 0, ...zeros);
  }
  const blanks = Array.from({ length: n - cells.length }, () => ({ ch: ' ', dp: false }));
  return p.align === 'left' ? [...cells, ...blanks] : [...blanks, ...cells];
}

/** Teksten et tal/en værdi skal vises som: ukendt = "-", til/fra = 1/0. Resten formateres af kaldet. */
export const SEG_UNKNOWN = '-';

// ---------------------------------------------------------------- tegning

const CELL_W = 30, CELL_H = 46, PAD = 8;
const T = 4;   // segmentets tykkelse

/** Vandret sekskant-segment fra x1 til x2 med centerlinje y. */
const hSeg = (x1: number, x2: number, y: number) =>
  `${x1},${y} ${x1 + T / 2},${y - T / 2} ${x2 - T / 2},${y - T / 2} ${x2},${y} ${x2 - T / 2},${y + T / 2} ${x1 + T / 2},${y + T / 2}`;
/** Lodret sekskant-segment fra y1 til y2 med centerlinje x. */
const vSeg = (x: number, y1: number, y2: number) =>
  `${x},${y1} ${x + T / 2},${y1 + T / 2} ${x + T / 2},${y2 - T / 2} ${x},${y2} ${x - T / 2},${y2 - T / 2} ${x - T / 2},${y1 + T / 2}`;

/** Formen for hvert segment i en celle (0,0 = øverste venstre hjørne). */
function shapes(kind: SegKind): Record<string, string> {
  const L = 3, R = 22, TOP = 3, MID = 22, BOT = 41, CX = 12.5;
  const s: Record<string, string> = {
    a: hSeg(L + 1.5, R - 1.5, TOP), d: hSeg(L + 1.5, R - 1.5, BOT),
    f: vSeg(L, TOP + 1.5, MID - 1.5), b: vSeg(R, TOP + 1.5, MID - 1.5),
    e: vSeg(L, MID + 1.5, BOT - 1.5), c: vSeg(R, MID + 1.5, BOT - 1.5),
  };
  if (kind === 7) s.g = hSeg(L + 1.5, R - 1.5, MID);
  else {
    s.g1 = hSeg(L + 1.5, CX - 0.5, MID);
    s.g2 = hSeg(CX + 0.5, R - 1.5, MID);
    s.i = vSeg(CX, TOP + 1.5, MID - 1.5);
    s.l = vSeg(CX, MID + 1.5, BOT - 1.5);
  }
  return s;
}

/**
 * Displayet som SVG til biblioteket/Tegn: `digits` (1–16) cifre af typen `kind`. Roden har `data-hv-kind` og er ét symbol;
 * alle segmenter står slukket (`SEG_OFF`) — animationen tænder dem (Symboltest og Overview viser de tændte).
 */
export function segDisplaySvg(kind: SegKind, digits: number): string {
  const n = Math.min(MAX_DIGITS, Math.max(MIN_DIGITS, Math.round(digits) || MIN_DIGITS));
  const sh = shapes(kind);
  const w = n * CELL_W + 2 * PAD, h = CELL_H + 2 * PAD;
  let body = '';
  for (let i = 0; i < n; i++) {
    const x = PAD + i * CELL_W;
    let seg = '';
    for (const name of SEGMENTS[kind]) {
      if (name === 'dp') seg += `<circle data-hv-seg="dp" cx="${x + 27}" cy="${PAD + 41}" r="2.2" fill="${SEG_OFF}"/>`;
      else seg += `<polygon data-hv-seg="${name}" points="${sh[name]}" transform="translate(${x} ${PAD})" fill="${SEG_OFF}"/>`;
    }
    body += `<g data-hv-digit="${i}">${seg}</g>`;
  }
  return `<g data-hv-kind="${kind}"><rect x="0" y="0" width="${w}" height="${h}" rx="6" fill="${SEG_BG}" stroke="#555" stroke-width="2"/>${body}</g>`;
}

// ---------------------------------------------------------------- visning (animationen "Segmenter")

/** Sæt segmenterne i `el` (displayets rod) ud fra teksten. */
export function renderSegmentText(el: Element, text: string, p: SegParams = {}): void {
  const digits = [...el.querySelectorAll('[data-hv-digit]')];
  if (!digits.length) return;
  const kind: SegKind = el.getAttribute('data-hv-kind') === '11' ? 11 : 7;
  const on = p.on || SEG_ON, off = p.off || SEG_OFF;
  const cells = layoutDigits(text, digits.length, p);
  digits.forEach((d, i) => {
    const lit = segmentsFor(cells[i].ch, kind);
    if (cells[i].dp) lit.add('dp');
    for (const s of d.querySelectorAll('[data-hv-seg]')) s.setAttribute('fill', lit.has(s.getAttribute('data-hv-seg') ?? '') ? on : off);
  });
}

/** Alle segmenter slukket (animationen nulstilles). */
export function clearSegments(el: Element, p: SegParams = {}): void {
  for (const s of el.querySelectorAll('[data-hv-seg]')) s.setAttribute('fill', p.off || SEG_OFF);
}
