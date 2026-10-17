// Anvend bindinger på SVG-elementer ud fra live-værdier.
// Ren DOM-manipulation via attributter/style — der indsættes aldrig HTML.
import { chainPhases, dashOffset, splitSubpaths, type Phase, type Piece } from './flowChain';
import type { Binding, LiveValue, TagMeta } from './api';
import { evalExpression } from './expression';

const SHAPES = 'path,rect,circle,ellipse,polygon,polyline,line';

export function toNumber(value: unknown): number | null {
  if (typeof value === 'boolean') return value ? 1 : 0;
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  return null;
}

export function isOn(value: unknown): boolean {
  if (typeof value === 'boolean') return value;
  const n = toNumber(value);
  return n !== null && n !== 0;
}

export function formatValue(value: unknown, meta: TagMeta | undefined, params: Record<string, any> = {}): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? params.true_text ?? 'Til' : params.false_text ?? 'Fra';
  const unit = params.show_unit === false || !meta?.unit ? '' : ` ${meta.unit}`;
  if (typeof value === 'number') {
    // Beregning (fx "x / 10") først — decimaler og enhed gælder resultatet. Ikke et tal (fx ÷ 0) = ingen værdi.
    let shown = value;
    if (typeof params.expression === 'string' && params.expression.trim()) {
      const r = evalExpression(params.expression.trim(), value);
      if (r === null) return '—';
      shown = r;
    }
    // decimals: binding-parameter vinder over tag-default; 0 er en gyldig værdi.
    const decimals = params.decimals ?? meta?.decimals ?? null;
    const text = decimals !== null && decimals !== undefined
      ? shown.toFixed(decimals)
      : Number.isInteger(shown) ? String(shown) : String(Math.round(shown * 1000) / 1000);
    return text + unit;
  }
  return String(value) + unit;
}

/** Tekst-binding: fast tekst før/efter værdien ("Tank : " … " liter"); også rundt om "—" når værdien mangler. */
export function textFor(value: unknown, meta: TagMeta | undefined, params: Record<string, any> = {}): string {
  return `${params.prefix ?? ''}${formatValue(value, meta, params)}${params.suffix ?? ''}`;
}

export function colorFor(value: unknown, params: Record<string, any>): string {
  const thresholds: { value: number; color: string }[] = params.thresholds ?? [];
  const n = toNumber(value);
  if (thresholds.length && n !== null && typeof value !== 'boolean') {
    let color: string = params.off ?? '#9e9e9e';
    for (const t of thresholds) if (n >= t.value) color = t.color;
    return color;
  }
  return isOn(value) ? params.on ?? '#2e7d32' : params.off ?? '#9e9e9e';
}

export function fraction(value: unknown, min = 0, max = 100): number {
  const n = toNumber(value);
  if (n === null || max <= min) return 0;
  return Math.min(1, Math.max(0, (n - min) / (max - min)));
}

function remember(el: Element, attr: string): string | null {
  const key = `data-hv-orig-${attr}`;
  if (!el.hasAttribute(key)) el.setAttribute(key, el.getAttribute(attr) ?? '');
  const v = el.getAttribute(key);
  return v === '' ? null : v;
}

function setText(el: Element, text: string): void {
  const target = el.querySelector('tspan') ?? el;
  if (target.textContent !== text) target.textContent = text;
}

function paint(el: Element, prop: 'fill' | 'stroke', color: string): void {
  const targets = el.tagName === 'g' ? Array.from(el.querySelectorAll(SHAPES)) : [el];
  for (const t of targets) (t as SVGElement).style[prop] = color;
}

function level(el: Element, f: number, direction: string): void {
  if (el.tagName !== 'rect') {
    el.setAttribute('data-hv-warning', 'level kræver et <rect>-element');
    return;
  }
  const x = parseFloat(remember(el, 'x') ?? '0');
  const y = parseFloat(remember(el, 'y') ?? '0');
  const w = parseFloat(remember(el, 'width') ?? '0');
  const h = parseFloat(remember(el, 'height') ?? '0');
  if (direction === 'up' || direction === 'down') {
    el.setAttribute('height', String(h * f));
    el.setAttribute('y', String(direction === 'up' ? y + h * (1 - f) : y));
  } else {
    el.setAttribute('width', String(w * f));
    el.setAttribute('x', String(direction === 'left' ? x + w * (1 - f) : x));
  }
}

/**
 * Flyt og Rotation ændrer begge transform. Hver gemmer sin del, og transform sammensættes som
 * original + flyt + rotation — så de kan kombineres på samme element uden at overskrive hinanden.
 */
function setTransformPart(el: Element, part: 'move' | 'rotate', value: string): void {
  const base = remember(el, 'transform');
  el.setAttribute(`data-hv-t-${part}`, value);
  const parts = [base, el.getAttribute('data-hv-t-move'), el.getAttribute('data-hv-t-rotate')].filter(Boolean);
  if (parts.length) el.setAttribute('transform', parts.join(' '));
  else el.removeAttribute('transform');
}

/**
 * Glidende Flyt/Drej (symbolstandarden): som CSS-transform om delens centrum, så skiftet glider (CSS-transition
 * .hv-glide) i stedet for at hoppe. Kun på dele uden egen transform-attribut — en CSS-transform ville ellers
 * erstatte den.
 */
function setGlide(el: Element, part: 'move' | 'rotate', value: string): void {
  el.setAttribute(`data-hv-c-${part}`, value);
  const st = (el as SVGElement).style;
  st.transform = [el.getAttribute('data-hv-c-move'), el.getAttribute('data-hv-c-rotate')].filter(Boolean).join(' ');
  st.transformBox = 'fill-box';
  st.transformOrigin = 'center';
  el.classList.add('hv-glide');
}

const canGlide = (el: Element, p: Record<string, any>) => Boolean(p.pos) && remember(el, 'transform') === null;
const r2 = (n: number) => Math.round(n * 100) / 100;

function moveBy(el: Element, dx: number, dy: number, p: Record<string, any>): void {
  if (canGlide(el, p)) setGlide(el, 'move', `translate(${r2(dx)}px, ${r2(dy)}px)`);
  else setTransformPart(el, 'move', `translate(${r2(dx)} ${r2(dy)})`);
}

function move(el: Element, f: number, dx: number, dy: number): void {
  setTransformPart(el, 'move', `translate(${r2(f * dx)} ${r2(f * dy)})`);
}

function rotate(el: Element, angle: number, p: Record<string, any> = {}): void {
  if (canGlide(el, p)) {
    setGlide(el, 'rotate', `rotate(${r2(angle)}deg)`);
    return;
  }
  const g = el as SVGGraphicsElement;
  let cx = 0;
  let cy = 0;
  try {
    const box = g.getBBox();
    cx = box.x + box.width / 2;
    cy = box.y + box.height / 2;
  } catch {
    // getBBox findes ikke i alle miljøer (fx jsdom) — roter om (0,0).
  }
  const r = (n: number) => Math.round(n * 100) / 100;
  setTransformPart(el, 'rotate', `rotate(${r(angle)} ${r(cx)} ${r(cy)})`);
}

/**
 * Løbelysets tilstand ud fra tagværdien: 1 = frem (langs tegneretningen), -1 = tilbage, 0 = stop.
 * `mode`: onoff (til = kør, fast retning), signed (> 0 frem, < 0 tilbage, 0 stop) eller code (0 stop,
 * 1 frem, 2 tilbage; alt andet = stop). `reverse` vender retningen i alle tilstande.
 */
export function flowState(value: unknown, p: Record<string, any> = {}): -1 | 0 | 1 {
  let dir: -1 | 0 | 1 = 0;
  const n = toNumber(value);
  if (p.mode === 'signed') dir = n === null || n === 0 ? 0 : n > 0 ? 1 : -1;
  else if (p.mode === 'code') dir = n === 1 ? 1 : n === 2 ? -1 : 0;
  else dir = value !== null && value !== undefined && isOn(value) !== Boolean(p.invert) ? 1 : 0;
  return dir !== 0 && p.reverse ? (-dir as -1 | 1) : dir;
}

/** Hvor mange gange en længde langs retningen (dx, dy) forstørres af en matrix (a b c d): |M·dir| / |dir|. */
export function lengthScale(m: { a: number; b: number; c: number; d: number }, dx: number, dy: number): number {
  const len = Math.hypot(dx, dy);
  if (!(len > 0)) return Math.sqrt(Math.abs(m.a * m.d - m.b * m.c)) || 1;       // ingen retning: geometrisk middel
  return Math.hypot(m.a * dx + m.c * dy, m.b * dx + m.d * dy) / len || 1;
}

type Mat = { a: number; b: number; c: number; d: number; e: number; f: number };
const mulMat = (m: Mat, n: Mat): Mat => ({
  a: m.a * n.a + m.c * n.b, b: m.b * n.a + m.d * n.b, c: m.a * n.c + m.c * n.d, d: m.b * n.c + m.d * n.d,
  e: m.a * n.e + m.c * n.f + m.e, f: m.b * n.e + m.d * n.f + m.f,
});
const invMat = (m: Mat): Mat | null => {
  const det = m.a * m.d - m.b * m.c;
  if (!det || !Number.isFinite(det)) return null;
  return { a: m.d / det, b: -m.b / det, c: -m.c / det, d: m.a / det, e: (m.c * m.f - m.d * m.e) / det, f: (m.b * m.e - m.a * m.f) / det };
};

/**
 * Skalering af lys-stregen ud fra elementets samlede transform (egen + forfædres), målt langs stregen: er et rør strakt 3
 * gange i længden, er 1 lokal enhed 3 enheder i tegningen. Lysets længde og fart skal være den samme i tegningen uanset
 * hvordan røret er skaleret, så de regnes om med denne faktor. Tegningens egen visning (viewBox/zoom) tæller IKKE med —
 * den skalerer røret og lyset ens — så den fjernes ved at dividere med en probe lagt direkte under roden. Kan der ikke
 * måles (uden for skærmen, jsdom), er faktoren 1 — som før.
 */
function flowScale(d: SVGElement): number {
  try {
    const own = (d as SVGGraphicsElement).getCTM?.() as Mat | null | undefined;
    if (!own) return 1;
    let m: Mat = own;
    const root = d.ownerSVGElement;
    if (root) {
      const probe = document.createElementNS(SVG_NS, 'g') as SVGGElement;
      root.appendChild(probe);
      let base: Mat | null = null;
      try {
        base = (probe.getCTM?.() as Mat | null | undefined) ?? null;
      } finally {
        root.removeChild(probe);
      }
      const inv = base ? invMat(base) : null;
      if (inv) m = mulMat(inv, own);
    }
    let dx = 0, dy = 0;
    if (d.tagName === 'line') {
      const n = (a: string) => parseFloat(d.getAttribute(a) ?? '0') || 0;
      dx = n('x2') - n('x1');
      dy = n('y2') - n('y1');
    } else {
      const b = (d as SVGGraphicsElement).getBBox?.();
      if (b && b.width > 0 && b.height > 0 && Math.min(b.width, b.height) / Math.max(b.width, b.height) > 0.3) return lengthScale(m, 0, 0);   // bøjning/kurve
      if (b) [dx, dy] = b.width >= b.height ? [1, 0] : [0, 1];
    }
    const s = lengthScale(m, dx, dy);
    return Number.isFinite(s) && s > 0.001 && s < 1000 ? s : 1;
  } catch {
    return 1;   // getCTM/getBBox kan kaste for elementer der ikke vises
  }
}

/** Stiplet kopi (lyset) til hvert element der løber — nøgle: det bundne element. */
const flowLayers = new WeakMap<Element, SVGGElement>();
const SVG_NS = 'http://www.w3.org/2000/svg';

/** De figurer lyset tegnes på: streger kopieres; et udfyldt <rect> (lige rør) får en streg ad sin midterlinje. */
function flowDash(shape: Element): SVGElement | null {
  const tag = shape.tagName;
  if (tag === 'rect') {
    const n = (a: string) => parseFloat(shape.getAttribute(a) ?? '0') || 0;
    const [x, y, w, h] = [n('x'), n('y'), n('width'), n('height')];
    if (w <= 0 || h <= 0) return null;
    const line = document.createElementNS(SVG_NS, 'line');
    const horizontal = w >= h;
    line.setAttribute('x1', String(horizontal ? x : x + w / 2));
    line.setAttribute('y1', String(horizontal ? y + h / 2 : y));
    line.setAttribute('x2', String(horizontal ? x + w : x + w / 2));
    line.setAttribute('y2', String(horizontal ? y + h / 2 : y + h));
    line.setAttribute('stroke-width', String(horizontal ? h : w));
    const t = shape.getAttribute('transform');
    if (t) line.setAttribute('transform', t);
    return line;
  }
  if (!['path', 'line', 'polyline', 'polygon', 'circle', 'ellipse'].includes(tag)) return null;
  const sw = parseFloat(shape.getAttribute('stroke-width') ?? '1');
  const stroke = shape.getAttribute('stroke');
  if (!stroke || stroke === 'none' || !(sw > 0)) return null;
  const copy = shape.cloneNode(false) as SVGElement;
  for (const a of [...copy.attributes]) if (a.name === 'id' || a.name.startsWith('data-hv') || a.name === 'class') copy.removeAttribute(a.name);
  copy.setAttribute('fill', 'none');
  copy.removeAttribute('style');
  return copy;
}

function shapesOf(el: Element): Element[] {
  if (el.tagName !== 'g') return [el];
  return Array.from(el.querySelectorAll(SHAPES)).filter((s) => !s.closest('.hv-flow'));
}

// ---------------------------------------------------------------- Løbelys i T-stykke og kryds
export type Seg = [number, number, number, number];
export type ArmName = 'left' | 'right' | 'up' | 'down';

/** Rette linjestykker i en figur (path med M/L/H/V/Z, line, polyline, polygon, rect-midterlinje). null = buer o.l. */
export function segmentsOf(shape: Element): Seg[] | null {
  const n = (a: string) => parseFloat(shape.getAttribute(a) ?? '0') || 0;
  const tag = shape.tagName;
  if (tag === 'line') return [[n('x1'), n('y1'), n('x2'), n('y2')]];
  if (tag === 'rect') {
    const [x, y, w, h] = [n('x'), n('y'), n('width'), n('height')];
    return w >= h ? [[x, y + h / 2, x + w, y + h / 2]] : [[x + w / 2, y, x + w / 2, y + h]];
  }
  if (tag === 'polyline' || tag === 'polygon') {
    const v = (shape.getAttribute('points') ?? '').trim().split(/[\s,]+/).map(Number);
    const out: Seg[] = [];
    for (let i = 0; i + 3 < v.length; i += 2) out.push([v[i], v[i + 1], v[i + 2], v[i + 3]]);
    if (tag === 'polygon' && v.length >= 6) out.push([v[v.length - 2], v[v.length - 1], v[0], v[1]]);
    return out.every((sg) => sg.every(Number.isFinite)) ? out : null;
  }
  if (tag !== 'path') return null;
  const toks = (shape.getAttribute('d') ?? '').match(/[a-zA-Z]|-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?/g) ?? [];
  const out: Seg[] = [];
  let x = 0, y = 0, sx = 0, sy = 0, cmd = '', i = 0;
  const num = () => Number(toks[i++]);
  while (i < toks.length) {
    if (/[a-zA-Z]/.test(toks[i])) cmd = toks[i++];
    const rel = cmd === cmd.toLowerCase();
    const C = cmd.toUpperCase();
    if (C === 'Z') { if (x !== sx || y !== sy) out.push([x, y, sx, sy]); x = sx; y = sy; continue; }
    if (!'MLHV'.includes(C)) return null; // buer og kurver: ikke et kryds af lige rør
    if (C === 'M') { x = (rel ? x : 0) + num(); y = (rel ? y : 0) + num(); sx = x; sy = y; cmd = rel ? 'l' : 'L'; continue; }
    const [ox, oy] = [x, y];
    if (C === 'L') { x = (rel ? x : 0) + num(); y = (rel ? y : 0) + num(); }
    if (C === 'H') x = (rel ? x : 0) + num();
    if (C === 'V') y = (rel ? y : 0) + num();
    if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
    out.push([ox, oy, x, y]);
  }
  return out;
}

const near = (a: number, b: number) => Math.abs(a - b) < 0.5;
function onSeg([x1, y1, x2, y2]: Seg, px: number, py: number): boolean {
  const len = Math.hypot(x2 - x1, y2 - y1);
  if (len === 0) return near(px, x1) && near(py, y1);
  const cross = Math.abs((x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)) / len;
  const t = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / (len * len);
  return cross < 0.5 && t > -0.01 && t < 1.01;
}

/** Krydspunkt og rørene ud fra det (endepunkter), fx 4 for et kryds og 3 for et T-stykke. null = intet kryds. */
export function junctionArms(segs: Seg[]): { cx: number; cy: number; arms: [number, number][] } | null {
  let c: [number, number] | null = null;
  for (let i = 0; i < segs.length && !c; i++) {
    for (let j = i + 1; j < segs.length && !c; j++) {
      const [x1, y1, x2, y2] = segs[i], [x3, y3, x4, y4] = segs[j];
      const den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4);
      if (Math.abs(den) < 1e-9) continue; // parallelle
      const px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / den;
      const py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / den;
      if (onSeg(segs[i], px, py) && onSeg(segs[j], px, py)) c = [px, py];
    }
  }
  if (!c) return null;
  const [cx, cy] = c;
  const arms: [number, number][] = [];
  for (const sg of segs) {
    if (!onSeg(sg, cx, cy)) continue;
    for (const [ex, ey] of [[sg[0], sg[1]], [sg[2], sg[3]]] as [number, number][]) {
      if (Math.hypot(ex - cx, ey - cy) < 0.5) continue;
      if (!arms.some(([ax, ay]) => near(ax, ex) && near(ay, ey))) arms.push([ex, ey]);
    }
  }
  return arms.length >= 3 ? { cx, cy, arms } : null;
}

/** Retningen af et rør som det ses på skærmen (m = elementets transform: roteret/spejlet symbol). */
export function armName(vx: number, vy: number, m: { a: number; b: number; c: number; d: number } = { a: 1, b: 0, c: 0, d: 1 }): ArmName {
  const sx = m.a * vx + m.c * vy, sy = m.b * vx + m.d * vy;
  return Math.abs(sx) >= Math.abs(sy) ? (sx >= 0 ? 'right' : 'left') : (sy >= 0 ? 'down' : 'up');
}

/** Ét rørs lysretning i et kryds: true = ud fra krydset. Det valgte rør følger arm_flow, de øvrige det modsatte. */
export function armFlowsOut(isChosen: boolean, armFlow: string, state: -1 | 1): boolean {
  const out = isChosen ? armFlow === 'out' : armFlow !== 'out';
  return state > 0 ? out : !out;
}

/** Lys-streger til et kryds: én linje pr. rør fra krydspunktet; null hvis elementet ikke er et kryds med det valgte rør. */
function junctionDashes(el: Element, shapes: Element[], p: Record<string, any>, state: -1 | 1): { d: SVGElement; out: boolean }[] | string {
  const segs: Seg[] = [];
  let width = 0;
  for (const s of shapes) {
    const sg = segmentsOf(s);
    if (!sg) return 'krydsning kræver lige rør (ingen buer)';
    segs.push(...sg);
    const n = (a: string) => parseFloat(s.getAttribute(a) ?? '0') || 0;
    width ||= s.tagName === 'rect' ? Math.min(n('width'), n('height')) : parseFloat(s.getAttribute('stroke-width') ?? '1');
  }
  const j = junctionArms(segs);
  if (!j) return 'krydsning: fandt ikke et T-stykke eller kryds i elementet';
  let m = { a: 1, b: 0, c: 0, d: 1 };
  try {
    const ctm = (el as SVGGraphicsElement).getCTM?.();
    if (ctm) m = ctm;
  } catch {
    // getCTM findes ikke i alle miljøer (fx jsdom) — så gælder symbolets egne retninger
  }
  const names = j.arms.map(([x, y]) => armName(x - j.cx, y - j.cy, m));
  if (!names.includes(p.arm)) return `krydsning: røret "${p.arm}" findes ikke her (har: ${names.join(', ')})`;
  return j.arms.map(([x, y], k) => {
    const d = document.createElementNS(SVG_NS, 'line') as SVGElement;
    d.setAttribute('x1', String(j.cx)); d.setAttribute('y1', String(j.cy));
    d.setAttribute('x2', String(x)); d.setAttribute('y2', String(y));
    d.setAttribute('stroke-width', String(width));
    return { d, out: armFlowsOut(names[k] === p.arm, p.arm_flow, state) };
  });
}

/** Lys-stregerne til et element (uden at sætte dem ind). `warning`: hvorfor et kryds faldt tilbage til tegneretningen. */
function buildDashes(el: Element, shapes: Element[], p: Record<string, any>, state: -1 | 1): { dashes: { d: SVGElement; out: boolean; arm: boolean }[]; warning: string } {
  let warning = '';
  if (p.arm) {
    const j = junctionDashes(el, shapes, p, state);
    if (typeof j === 'string') warning = j; // falder tilbage til tegneretningen
    else return { dashes: j.map((x) => ({ ...x, arm: true })), warning };
  }
  const dashes: { d: SVGElement; out: boolean; arm: boolean }[] = [];
  for (const s of shapes) {
    const d = flowDash(s);
    if (!d) continue;
    // En sti med flere delstier (fx et T-stykkes gennemløb og afgrening) deles, så hver delsti kan indgå i et forløb
    const parts = d.tagName === 'path' ? splitSubpaths(d.getAttribute('d') ?? '') : null;
    if (parts && parts.length > 1) {
      for (const part of parts) {
        const c = d.cloneNode(false) as SVGElement;
        c.setAttribute('d', part);
        dashes.push({ d: c, out: state > 0, arm: false });
      }
    } else dashes.push({ d, out: state > 0, arm: false });
  }
  return { dashes, warning };
}

// ---------------------------------------------------------------- Sammenhængende løbelys (v0.64.0)
// Løbelys-dele med samme tag, hvis ender rører hinanden, danner et forløb med én fælles stiplingskoordinat (flowChain.ts).
interface FlowMember { p: Record<string, any>; group: string }
const flowMembers = new WeakMap<Element, Map<Element, FlowMember>>();   // pr. tegning (rod-<svg>)
const flowPhases = new WeakMap<Element, Map<string, Phase>>();
const lastFlow = new WeakMap<Element, { state: -1 | 0 | 1; p: Record<string, any> }>();
const rephasePending = new WeakSet<Element>();
const flowIds = new WeakMap<Element, number>();
let nextFlowId = 1;
const flowKey = (el: Element, i: number): string => {
  let id = flowIds.get(el);
  if (!id) flowIds.set(el, (id = nextFlowId++));
  return `${id}:${i}`;
};
function rootOf(el: Element): Element | null {
  let r = (el as SVGElement).ownerSVGElement ?? null;
  while (r?.ownerSVGElement) r = r.ownerSVGElement;
  return r;
}

/**
 * Gruppen et løbelys hører til: kun dele med samme tag og samme måde at tænde/vende på kan danne et forløb. Lyslængde og
 * fart er IKKE med — forløbet bruger den, flest dele har (ellers kan mønstret ikke fortsætte over samlingerne).
 */
export function flowGroup(tag: string, p: Record<string, any>): string {
  return [tag, p.dir_tag ?? '', p.mode ?? 'onoff', p.invert ? 1 : 0, p.pos ? 'pos' : ''].join('|');
}

/** Kendt løbelys på tegningen. Nye medlemmer giver nye forløb — de løbelys der allerede kører, regnes om (samlet). */
function registerFlow(el: Element, p: Record<string, any>, group: string): void {
  const root = rootOf(el);
  if (!root) return;
  let m = flowMembers.get(root);
  if (!m) flowMembers.set(root, (m = new Map()));
  const old = m.get(el);
  m.set(el, { p, group });
  if (old && old.group === group) return;
  flowPhases.delete(root);
  if (rephasePending.has(root)) return;
  rephasePending.add(root);
  queueMicrotask(() => {
    rephasePending.delete(root);
    for (const member of m!.keys()) {
      const last = lastFlow.get(member);
      const layer = flowLayers.get(member);
      if (!last?.state || !layer) continue;
      layer.removeAttribute('data-hv-flow');   // tving en ny tegning med de nye forskydninger
      flow(member, last.state, last.p);
    }
  });
}

/** Matrix fra elementets koordinater til TEGNINGENS (uden visningens zoom/viewBox — som flowScale). */
function worldMatrix(d: SVGElement): Mat | null {
  const own = (d as SVGGraphicsElement).getCTM?.() as Mat | null | undefined;
  if (!own) return null;
  const root = d.ownerSVGElement;
  if (!root) return own;
  const probe = document.createElementNS(SVG_NS, 'g') as SVGGElement;
  root.appendChild(probe);
  try {
    const base = probe.getCTM?.() as Mat | null | undefined;
    const inv = base ? invMat(base) : null;
    return inv ? mulMat(inv, own) : own;
  } finally {
    root.removeChild(probe);
  }
}

/** Mål alle løbelys-dele på tegningen og beregn forløbene. Lukkede figurer og stier med flere delstier er ikke dele. */
function computePhases(root: Element): Map<string, Phase> {
  const members = [...(flowMembers.get(root)?.entries() ?? [])]
    .filter(([el]) => el.isConnected)
    .sort(([a], [b]) => (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1));
  const pieces: Piece[] = [];
  const widths: number[] = [];
  for (const [el, { p, group }] of members) {
    const { dashes } = buildDashes(el, shapesOf(el), p, 1);
    if (!dashes.length) continue;
    const tmp = document.createElementNS(SVG_NS, 'g') as SVGGElement;
    tmp.setAttribute('class', 'hv-flow');
    tmp.setAttribute('visibility', 'hidden');
    for (const { d } of dashes) tmp.appendChild(d);
    if (el.tagName === 'g') el.appendChild(tmp);
    else el.parentNode?.insertBefore(tmp, el.nextSibling);
    try {
      dashes.forEach(({ d, arm }, i) => {
        const tag = d.tagName;
        if (['circle', 'ellipse', 'polygon'].includes(tag)) return;
        if (tag === 'path' && ((d.getAttribute('d') ?? '').match(/[Mm]/g) ?? []).length > 1) return;   // kunne ikke deles i delstier
        const g = d as unknown as SVGGeometryElement;
        if (typeof g.getTotalLength !== 'function') return;
        const L = g.getTotalLength();
        const m = worldMatrix(d);
        if (!(L > 0) || !m) return;
        const at = (t: number): [number, number] => {
          const q = g.getPointAtLength(t);
          return [m.a * q.x + m.c * q.y + m.e, m.b * q.x + m.d * q.y + m.f];
        };
        const scale = flowScale(d);
        pieces.push({ key: flowKey(el, i), a: at(0), b: at(L), len: L * scale, group, dir: arm ? 0 : p.reverse ? -1 : 1,
          dash: Number(p.dash ?? 12), speed: Number(p.speed ?? 40) });
        widths.push((parseFloat(d.getAttribute('stroke-width') ?? '1') || 1) * scale);
      });
    } catch {
      // getTotalLength/getCTM kan kaste for elementer der ikke vises — så kører delen for sig selv (som før)
    } finally {
      tmp.remove();
    }
  }
  widths.sort((x, y) => x - y);
  const width = widths.length ? widths[Math.floor(widths.length / 2)] : 10;
  return chainPhases(pieces, Math.max(4, 0.8 * width));   // ender inden for ~en rørbredde hænger sammen
}

function phaseFor(el: Element, i: number): Phase | undefined {
  const root = rootOf(el);
  if (!root || !flowMembers.get(root)?.has(el)) return undefined;
  let ph = flowPhases.get(root);
  if (!ph) flowPhases.set(root, (ph = computePhases(root)));
  return ph.get(flowKey(el, i));
}

function flow(el: Element, state: -1 | 0 | 1, p: Record<string, any>): void {
  lastFlow.set(el, { state, p });
  const base = p.base ?? '#555555', light = p.light ?? '#8fc8ea';
  const dash = Number(p.dash ?? 12), speed = Number(p.speed ?? 40);
  const key = `${state}|${base}|${light}|${dash}|${speed}|${p.arm ?? ''}|${p.arm_flow ?? ''}`;
  const old = flowLayers.get(el);
  if (old?.getAttribute('data-hv-flow') === key) return; // uændret: lad animationen køre videre uden hop
  old?.remove();
  flowLayers.delete(el);
  el.removeAttribute('data-hv-warning');
  const shapes = shapesOf(el);
  for (const s of shapes) {
    const st = (s as SVGElement).style;
    const filled = s.tagName === 'rect';
    // Stop: røret får sin egen farve igen. Kører: farve 1 under lyset.
    if (filled) st.fill = state ? base : '';
    else st.stroke = state ? base : '';
  }
  if (!state) return;
  // Hver lys-streg med sin retning: langs tegneretningen, eller pr. rør i et kryds (ud = væk fra krydspunktet)
  const { dashes, warning } = buildDashes(el, shapes, p, state);
  if (warning) el.setAttribute('data-hv-warning', warning);
  const layer = document.createElementNS(SVG_NS, 'g') as SVGGElement;
  layer.setAttribute('class', 'hv-flow');
  layer.setAttribute('data-hv-flow', key);
  layer.setAttribute('pointer-events', 'none');
  const reduce = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  for (const { d, out } of dashes) {
    d.setAttribute('stroke', light);
    d.setAttribute('stroke-linecap', 'butt');
    d.setAttribute('data-hv-dir', out ? 'out' : 'in');
    layer.appendChild(d);
  }
  if (!layer.childNodes.length) {
    el.setAttribute('data-hv-warning', 'løbelys kræver en streg (path/line/polyline) eller et rør (rect)');
    return;
  }
  // Først i tegningen — så elementernes samlede transform kan måles — og først derefter sættes længde og fart
  if (el.tagName === 'g') el.appendChild(layer);
  else el.parentNode?.insertBefore(layer, el.nextSibling);
  flowLayers.set(el, layer);
  dashes.forEach(({ d, out }, i) => {
    // Sammenhængende forløb: stiplingen fortsætter fra nabodelen, retningen følger forløbet, og hele forløbet har samme
    // lyslængde og fart (flertallets)
    const ph = phaseFor(el, i);
    const len = ph?.dash ?? dash, pace = ph?.speed ?? speed;
    // Lysets længde og fart er i TEGNINGENS enheder, uanset hvordan røret er skaleret: omregnet til rørets egne enheder
    const scale = flowScale(d);
    const unit = len / scale;
    d.setAttribute('stroke-dasharray', `${unit} ${unit}`);
    const off = ph ? dashOffset(ph, len) / scale : 0;
    const dir = ph?.flip ? !out : out;
    d.setAttribute('stroke-dashoffset', String(off));
    if (!reduce && typeof (d as any).animate === 'function') {
      // Lyset flytter én periode (lys + mørk) pr. omgang; startTime 0 holder alle løbelys i takt
      const a = d.animate([{ strokeDashoffset: off }, { strokeDashoffset: off - 2 * unit }],
        { duration: (2 * len / pace) * 1000, iterations: Infinity, direction: dir ? 'normal' : 'reverse' });
      a.startTime = 0;
    }
  });
}

/**
 * Løbelys med eget retnings-tag (`dir_tag`): Fra = som valgt, Til = modsat. Ukendt retning = stop, så der
 * aldrig vises en retning man ikke kender.
 */
export function withDirection(state: -1 | 0 | 1, p: Record<string, any>, dirLive?: LiveValue): -1 | 0 | 1 {
  if (!p.dir_tag || state === 0) return state;
  const v = dirLive?.value;
  if (v === null || v === undefined) return 0;
  return isOn(v) ? (-state as -1 | 1) : state;
}

/** `dirLive`: live-værdien af løbelysets retnings-tag, hvis bindingen har et. */
// Blinkfrekvens (symbolstandarden): periode i ms. Fasen sættes ud fra uret, så alle blink med samme frekvens er i takt.
export const BLINK_MS: Record<string, number> = { slow: 2000, normal: 1000, fast: 500 };

function setBlink(el: Element, on: boolean, speed = 'normal'): void {
  const was = el.classList.contains('hv-blink') ? el.getAttribute('data-hv-blink') : null;
  el.classList.remove('hv-blink-slow', 'hv-blink-fast');
  if (!on) {
    el.classList.remove('hv-blink');
    el.removeAttribute('data-hv-blink');
    return;
  }
  el.classList.add('hv-blink');
  if (speed !== 'normal') el.classList.add(`hv-blink-${speed}`);
  if (was !== speed) {
    // Kun når blinket starter (eller skifter frekvens) — ellers ville hver opdatering flytte fasen
    (el as SVGElement).style.animationDelay = `-${Date.now() % (BLINK_MS[speed] ?? 1000)}ms`;
    el.setAttribute('data-hv-blink', speed);
  }
}

/** Om en til/fra-agtig animation (synlig, blink, roterer) er aktiv: pr. position, "når ≥ X" eller til/fra. */
export function activeFor(v: unknown, p: Record<string, any>): boolean {
  if (p.pos) {
    const n = toNumber(v);
    return n !== null && Array.isArray(p.set) && Boolean(p.set[n]);
  }
  if (p.at_least !== undefined && p.at_least !== null && typeof v !== 'boolean') {
    const n = toNumber(v);
    return n !== null && n >= Number(p.at_least);
  }
  return isOn(v) !== Boolean(p.invert);
}

/** Animationen virker ikke (uden for "gælder i positionerne" eller ukendt position): delen vises som tegnet. */
function resetAnim(el: Element, anim: string, p: Record<string, any>): void {
  const st = (el as SVGElement).style;
  switch (anim) {
    case 'fill':
    case 'stroke':
      paint(el, anim, '');
      break;
    case 'visible':
      st.display = '';
      break;
    case 'blink':
      setBlink(el, false);
      break;
    case 'spin':
      el.classList.remove('hv-spin');
      break;
    case 'opacity':
      st.opacity = '';
      break;
    case 'rotate':
    case 'move':
      if (el.hasAttribute(`data-hv-c-${anim}`)) setGlide(el, anim, '');
      else if (el.hasAttribute(`data-hv-t-${anim}`)) setTransformPart(el, anim, '');
      break;
    case 'text':
      if (el.hasAttribute('data-hv-orig-text')) setText(el, el.getAttribute('data-hv-orig-text') ?? '');
      break;
    case 'level':
      for (const a of ['x', 'y', 'width', 'height']) {
        const orig = el.getAttribute(`data-hv-orig-${a}`);
        if (orig !== null && orig !== '') el.setAttribute(a, orig);
      }
      break;
    case 'flow':
      flow(el, 0, p);
      break;
  }
}

/**
 * `dirLive`: live-værdien af løbelysets retnings-tag; `posLive`: symbolets position (til "gælder i positionerne").
 * Bindinger fra en symbol-konfiguration med kilden "position" har `params.pos` og værdier pr. position.
 */
export function applyBinding(el: Element, b: Binding, live: LiveValue | undefined, meta?: TagMeta, dirLive?: LiveValue,
  posLive?: LiveValue): void {
  if (b.anim.startsWith('click:')) {
    el.classList.add('hv-clickable');
    return;
  }
  const quality = live?.quality ?? 'unknown';
  el.setAttribute('data-hv-quality', quality);
  const p = b.params ?? {};
  if (b.anim === 'flow') registerFlow(el, p, flowGroup(b.tag, p));
  if (b.anim === 'text' && !el.hasAttribute('data-hv-orig-text')) {
    el.setAttribute('data-hv-orig-text', (el.querySelector('tspan') ?? el).textContent ?? '');
  }
  // "Gælder i positionerne": kun når positionen er kendt og ikke valgt, er animationen slået fra (som prototypen)
  const pos = posLive ? toNumber(posLive.value) : null;
  if (Array.isArray(p.only) && pos !== null && !p.only[pos]) {
    resetAnim(el, b.anim, p);
    return;
  }
  if (!live || live.value === null || live.value === undefined) {
    if (p.pos) {
      resetAnim(el, b.anim, p);   // ukendt position: delen som tegnet
      return;
    }
    if (b.anim === 'text') setText(el, textFor(null, meta, p));
    // Ukendt værdi (fx kommunikationsfejl): løbelyset står stille, så det aldrig viser flow der ikke er der
    if (b.anim === 'flow') flow(el, 0, p);
    return;
  }
  const v = live.value;
  const k = p.pos ? toNumber(v) : null;   // positionens indeks når kilden er symbolets position
  const at = (list: unknown): any => (Array.isArray(list) && k !== null ? list[k] : undefined);
  switch (b.anim) {
    case 'text':
      setText(el, p.pos ? String(at(p.labels) ?? '') : textFor(v, meta, p));
      break;
    case 'fill':
    case 'stroke': {
      const color = p.pos ? at(p.colors) : colorFor(v, p);
      if (color) paint(el, b.anim, color);
      else resetAnim(el, b.anim, p);
      break;
    }
    case 'visible':
      (el as SVGElement).style.display = activeFor(v, p) ? '' : 'none';
      break;
    case 'blink':
      setBlink(el, activeFor(v, p), p.speed ?? 'normal');
      break;
    case 'spin':
      el.classList.toggle('hv-spin', activeFor(v, p));
      break;
    case 'level':
      level(el, fraction(v, p.min, p.max), p.direction ?? 'up');
      break;
    case 'rotate': {
      if (p.pos) {
        const a = at(p.angles);
        if (a === undefined) resetAnim(el, 'rotate', p);
        else rotate(el, Number(a), p);
        break;
      }
      const f = fraction(v, p.min, p.max);
      rotate(el, (p.angle_min ?? 0) + f * ((p.angle_max ?? 360) - (p.angle_min ?? 0)), p);
      break;
    }
    case 'opacity':
      (el as SVGElement).style.opacity = String(fraction(v, p.min, p.max));
      break;
    case 'move':
      if (p.pos) {
        const dx = at(p.dxs), dy = at(p.dys);
        if (dx === undefined || dy === undefined) resetAnim(el, 'move', p);
        else moveBy(el, Number(dx), Number(dy), p);
        break;
      }
      move(el, fraction(v, p.min, p.max), p.dx ?? 100, p.dy ?? 0);
      break;
    case 'flow': {
      let state: -1 | 0 | 1 = p.pos ? (Number(at(p.dirs) ?? 0) as -1 | 0 | 1) : flowState(v, p);
      if (p.pos && p.reverse && state) state = -state as -1 | 1;
      flow(el, withDirection(state, p, dirLive), p);
      break;
    }
  }
}
