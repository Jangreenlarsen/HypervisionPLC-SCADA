// Anvend bindinger på SVG-elementer ud fra live-værdier.
// Ren DOM-manipulation via attributter/style — der indsættes aldrig HTML.
import type { Binding, LiveValue, TagMeta } from './api';

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
    // decimals: binding-parameter vinder over tag-default; 0 er en gyldig værdi.
    const decimals = params.decimals ?? meta?.decimals ?? null;
    const text = decimals !== null && decimals !== undefined
      ? value.toFixed(decimals)
      : Number.isInteger(value) ? String(value) : String(Math.round(value * 1000) / 1000);
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
  el.setAttribute('transform', parts.join(' '));
}

function move(el: Element, f: number, dx: number, dy: number): void {
  const r = (n: number) => Math.round(n * 100) / 100;
  setTransformPart(el, 'move', `translate(${r(f * dx)} ${r(f * dy)})`);
}

function rotate(el: Element, angle: number): void {
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

function flow(el: Element, state: -1 | 0 | 1, p: Record<string, any>): void {
  const base = p.base ?? '#555555', light = p.light ?? '#8fc8ea';
  const dash = Number(p.dash ?? 12), speed = Number(p.speed ?? 40);
  const key = `${state}|${base}|${light}|${dash}|${speed}`;
  const old = flowLayers.get(el);
  if (old?.getAttribute('data-hv-flow') === key) return; // uændret: lad animationen køre videre uden hop
  old?.remove();
  flowLayers.delete(el);
  const shapes = shapesOf(el);
  for (const s of shapes) {
    const st = (s as SVGElement).style;
    const filled = s.tagName === 'rect';
    // Stop: røret får sin egen farve igen. Kører: farve 1 under lyset.
    if (filled) st.fill = state ? base : '';
    else st.stroke = state ? base : '';
  }
  if (!state) return;
  const layer = document.createElementNS(SVG_NS, 'g') as SVGGElement;
  layer.setAttribute('class', 'hv-flow');
  layer.setAttribute('data-hv-flow', key);
  layer.setAttribute('pointer-events', 'none');
  const reduce = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  for (const s of shapes) {
    const d = flowDash(s);
    if (!d) continue;
    d.setAttribute('stroke', light);
    d.setAttribute('stroke-dasharray', `${dash} ${dash}`);
    d.setAttribute('stroke-linecap', 'butt');
    layer.appendChild(d);
    if (!reduce && typeof (d as any).animate === 'function') {
      // Lyset flytter én periode (lys + mørk) pr. omgang; startTime 0 holder alle løbelys i takt
      const a = d.animate([{ strokeDashoffset: 0 }, { strokeDashoffset: -2 * dash }],
        { duration: (2 * dash / speed) * 1000, iterations: Infinity, direction: state > 0 ? 'normal' : 'reverse' });
      a.startTime = 0;
    }
  }
  if (!layer.childNodes.length) {
    el.setAttribute('data-hv-warning', 'løbelys kræver en streg (path/line/polyline) eller et rør (rect)');
    return;
  }
  if (el.tagName === 'g') el.appendChild(layer);
  else el.parentNode?.insertBefore(layer, el.nextSibling);
  flowLayers.set(el, layer);
}

export function applyBinding(el: Element, b: Binding, live: LiveValue | undefined, meta?: TagMeta): void {
  if (b.anim.startsWith('click:')) {
    el.classList.add('hv-clickable');
    return;
  }
  const quality = live?.quality ?? 'unknown';
  el.setAttribute('data-hv-quality', quality);
  if (!live || live.value === null || live.value === undefined) {
    if (b.anim === 'text') setText(el, textFor(null, meta, b.params ?? {}));
    // Ukendt værdi (fx kommunikationsfejl): løbelyset står stille, så det aldrig viser flow der ikke er der
    if (b.anim === 'flow') flow(el, 0, b.params ?? {});
    return;
  }
  const v = live.value;
  const p = b.params ?? {};
  switch (b.anim) {
    case 'text':
      setText(el, textFor(v, meta, p));
      break;
    case 'fill':
    case 'stroke':
      paint(el, b.anim, colorFor(v, p));
      break;
    case 'visible':
      (el as SVGElement).style.display = isOn(v) !== Boolean(p.invert) ? '' : 'none';
      break;
    case 'blink':
      el.classList.toggle('hv-blink', isOn(v) !== Boolean(p.invert));
      break;
    case 'level':
      level(el, fraction(v, p.min, p.max), p.direction ?? 'up');
      break;
    case 'rotate': {
      const f = fraction(v, p.min, p.max);
      rotate(el, (p.angle_min ?? 0) + f * ((p.angle_max ?? 360) - (p.angle_min ?? 0)));
      break;
    }
    case 'opacity':
      (el as SVGElement).style.opacity = String(fraction(v, p.min, p.max));
      break;
    case 'move':
      move(el, fraction(v, p.min, p.max), p.dx ?? 100, p.dy ?? 0);
      break;
    case 'flow':
      flow(el, flowState(v, p), p);
      break;
  }
}
