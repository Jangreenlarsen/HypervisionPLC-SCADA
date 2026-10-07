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

function rotate(el: Element, angle: number): void {
  const base = remember(el, 'transform');
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
  el.setAttribute('transform', `${base ? base + ' ' : ''}rotate(${angle} ${cx} ${cy})`);
}

export function applyBinding(el: Element, b: Binding, live: LiveValue | undefined, meta?: TagMeta): void {
  const quality = live?.quality ?? 'unknown';
  el.setAttribute('data-hv-quality', quality);
  if (!live || live.value === null || live.value === undefined) {
    if (b.anim === 'text') setText(el, '—');
    return;
  }
  const v = live.value;
  const p = b.params ?? {};
  switch (b.anim) {
    case 'text':
      setText(el, formatValue(v, meta, p));
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
  }
}
