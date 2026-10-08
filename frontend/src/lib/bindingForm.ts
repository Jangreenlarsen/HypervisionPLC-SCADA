// Formular-model for én binding i editoren, og konvertering til/fra backendens params.
// Backenden validerer igen (bindings.py) — her fanges de oplagte fejl med danske beskeder.
import type { Binding } from './api';

export type Anim = Binding['anim'];

export const ANIMS: { id: Anim; label: string; help: string }[] = [
  { id: 'text', label: 'Tekst', help: 'Viser værdien (med enhed) i et tekst-element' },
  { id: 'fill', label: 'Fyldfarve', help: 'Farve efter til/fra eller tærskler' },
  { id: 'stroke', label: 'Stregfarve', help: 'Som fyldfarve, men på kanten' },
  { id: 'visible', label: 'Synlighed', help: 'Vis når værdien er sand (eller omvendt)' },
  { id: 'blink', label: 'Blink', help: 'Blinker når værdien er sand (fx alarm)' },
  { id: 'level', label: 'Niveau', help: 'Fylder et <rect> fra min til max (tank/bar)' },
  { id: 'rotate', label: 'Rotation', help: 'Roterer elementet efter værdien' },
  { id: 'opacity', label: 'Gennemsigtighed', help: 'Fra usynlig (min) til fuldt synlig (max)' },
];

export interface Threshold {
  value: string;
  color: string;
}

export interface BindingForm {
  tag: string;
  anim: Anim;
  decimals: string;
  true_text: string;
  false_text: string;
  show_unit: boolean;
  on: string;
  off: string;
  thresholds: Threshold[];
  invert: boolean;
  min: string;
  max: string;
  direction: 'up' | 'down' | 'left' | 'right';
  angle_min: string;
  angle_max: string;
}

export function emptyForm(tag = '', anim: Anim = 'text'): BindingForm {
  return {
    tag, anim, decimals: '', true_text: 'Til', false_text: 'Fra', show_unit: true,
    on: '#2e7d32', off: '#9e9e9e', thresholds: [], invert: false,
    min: '0', max: '100', direction: 'up', angle_min: '0', angle_max: '360',
  };
}

const str = (v: unknown, fallback: string) => (v === null || v === undefined ? fallback : String(v));

export function toForm(b: Pick<Binding, 'tag' | 'anim' | 'params'>): BindingForm {
  const p = b.params ?? {};
  const f = emptyForm(b.tag, b.anim);
  return {
    ...f,
    decimals: str(p.decimals, ''),
    true_text: str(p.true_text, f.true_text),
    false_text: str(p.false_text, f.false_text),
    show_unit: p.show_unit ?? true,
    on: str(p.on, f.on),
    off: str(p.off, f.off),
    thresholds: (p.thresholds ?? []).map((t: { value: number; color: string }) => ({ value: String(t.value), color: t.color })),
    invert: Boolean(p.invert),
    min: str(p.min, f.min),
    max: str(p.max, f.max),
    direction: p.direction ?? 'up',
    angle_min: str(p.angle_min, f.angle_min),
    angle_max: str(p.angle_max, f.angle_max),
  };
}

/** Tal fra et inputfelt. Accepterer decimalkomma. 0 er en gyldig værdi; tom er en fejl. */
export function parseNumber(text: string, field: string): number {
  const t = text.trim().replace(',', '.');
  if (t === '') throw new Error(`${field} skal udfyldes`);
  const n = Number(t);
  if (!Number.isFinite(n)) throw new Error(`${field} skal være et tal, ikke "${text}"`);
  return n;
}

function range(f: BindingForm): { min: number; max: number } {
  const min = parseNumber(f.min, 'Min');
  const max = parseNumber(f.max, 'Max');
  if (!(min < max)) throw new Error('Min skal være mindre end max');
  return { min, max };
}

/** Formular → {tag, anim, params}. Kaster Error med dansk tekst ved ugyldigt input. */
export function fromForm(f: BindingForm): { tag: string; anim: Anim; params: Record<string, unknown> } {
  if (!f.tag.trim()) throw new Error('Vælg et tag');
  let params: Record<string, unknown> = {};
  switch (f.anim) {
    case 'text': {
      params = { true_text: f.true_text, false_text: f.false_text, show_unit: f.show_unit };
      if (f.decimals.trim() !== '') {
        const d = parseNumber(f.decimals, 'Decimaler');
        if (!Number.isInteger(d) || d < 0 || d > 6) throw new Error('Decimaler skal være et heltal 0-6');
        params.decimals = d;
      }
      break;
    }
    case 'fill':
    case 'stroke': {
      const thresholds = f.thresholds.map((t, i) => ({ value: parseNumber(t.value, `Tærskel ${i + 1}`), color: t.color.trim() }));
      for (let i = 1; i < thresholds.length; i++) {
        if (thresholds[i].value < thresholds[i - 1].value) throw new Error('Tærskler skal stå i stigende rækkefølge');
      }
      params = { on: f.on.trim(), off: f.off.trim(), thresholds };
      break;
    }
    case 'visible':
    case 'blink':
      params = { invert: f.invert };
      break;
    case 'level':
      params = { ...range(f), direction: f.direction };
      break;
    case 'rotate':
      params = { ...range(f), angle_min: parseNumber(f.angle_min, 'Vinkel ved min'), angle_max: parseNumber(f.angle_max, 'Vinkel ved max') };
      break;
    case 'opacity':
      params = range(f);
      break;
  }
  return { tag: f.tag.trim(), anim: f.anim, params };
}

/** Nærmeste element med id (inden for tegningen) — klik rammer ofte et barn uden id. */
export function pickElement(target: Element | null, root: Element): Element | null {
  let el: Element | null = target;
  while (el && el !== root) {
    if (el.id && el.tagName.toLowerCase() !== 'svg') return el;
    el = el.parentElement;
  }
  return null;
}

/** Til <input type=color>, som kun kan vise #rrggbb. */
export function toHex(color: string): string {
  const c = color.trim();
  if (/^#[0-9a-f]{6}$/i.test(c)) return c;
  if (/^#[0-9a-f]{3}$/i.test(c)) return '#' + [...c.slice(1)].map((x) => x + x).join('');
  return '#000000';
}
