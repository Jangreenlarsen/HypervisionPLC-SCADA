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
  { id: 'move', label: 'Flyt', help: 'Flytter elementet fra sin plads (ved min) til forskydningen dx/dy (ved max) — fx spjæld, glider, cylinder' },
  { id: 'flow', label: 'Løbelys', help: 'To farver der løber langs en streg eller et rør — tagget styrer start/stop og retning' },
  { id: 'click:write', label: 'Klik: setpunkt', help: 'Operatøren indtaster en ny værdi (tagget skal være skrivbart)' },
  { id: 'click:toggle', label: 'Klik: til/fra', help: 'Skifter et til/fra-tag (coil eller heltals-register)' },
  { id: 'click:pulse', label: 'Klik: puls', help: 'Sætter tagget i et kort øjeblik — serveren nulstiller det' },
  { id: 'click:select', label: 'Klik: vælg position', help: 'Omskifter: operatøren vælger én af 2-8 positioner, og positionens værdi skrives' },
  { id: 'click:goto', label: 'Klik: gå til tegning', help: 'Åbner en anden tegning (drill-down)' },
];

export const isClick = (anim: Anim) => anim.startsWith('click:');

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
  prefix: string;
  suffix: string;
  on: string;
  off: string;
  thresholds: Threshold[];
  invert: boolean;
  min: string;
  max: string;
  direction: 'up' | 'down' | 'left' | 'right';
  angle_min: string;
  angle_max: string;
  dx: string;
  dy: string;
  /** Løbelys: hvordan tagget styrer start/stop og retning */
  mode: 'onoff' | 'signed' | 'code';
  reverse: boolean;
  base: string;
  light: string;
  speed: string;
  dash: string;
  /** Løbelys i T-stykke/kryds: valgt rør (som på skærmen) og om det løber ind i eller ud af krydset */
  arm: '' | 'left' | 'right' | 'up' | 'down';
  arm_flow: 'in' | 'out';
  /** Løbelys: valgfrit tag der styrer retningen (Fra = frem, Til = tilbage) */
  dir_tag: string;
  title: string;
  confirm: boolean;
  ms: string;
  positions: { value: string; label: string }[];
  drawing: string;
}

export function emptyForm(tag = '', anim: Anim = 'text'): BindingForm {
  return {
    tag, anim, decimals: '', true_text: 'Til', false_text: 'Fra', show_unit: true, prefix: '', suffix: '',
    on: '#2e7d32', off: '#9e9e9e', thresholds: [], invert: false,
    min: '0', max: '100', direction: 'up', angle_min: '0', angle_max: '360', dx: '100', dy: '0',
    mode: 'onoff', reverse: false, base: '#555555', light: '#8fc8ea', speed: '40', dash: '12', arm: '', arm_flow: 'in', dir_tag: '',
    title: '', confirm: anim === 'click:toggle', ms: '500', drawing: '',
    positions: [{ value: '0', label: 'Hånd' }, { value: '1', label: '0' }, { value: '2', label: 'Auto' }],
  };
}

/**
 * Én binding i editoren = ét tag med en eller flere animationer (fx tekst + blink), hver med egne
 * parametre. Backenden gemmer stadig én række pr. animation; `gid` samler dem i editoren.
 */
export type Draft = BindingForm & { gid: number };

/** Gruppér formularer pr. tag (gå-til-tegning har intet tag og står altid for sig selv). */
export function toDrafts(forms: BindingForm[], firstGid = 0): Draft[] {
  const byTag = new Map<string, number>();
  let next = firstGid;
  return forms.map((f) => {
    if (f.anim === 'click:goto' || !f.tag) return { ...f, gid: next++ };
    if (!byTag.has(f.tag)) byTag.set(f.tag, next++);
    return { ...f, gid: byTag.get(f.tag)! };
  });
}

/** Gruppernes rækkefølge (første forekomst). */
export function groupIds(drafts: Draft[]): number[] {
  return [...new Set(drafts.map((d) => d.gid))];
}

/** Flad liste til backenden, samlet pr. binding så de gemmes (og genindlæses) i samme rækkefølge. */
export function flatten(drafts: Draft[]): Draft[] {
  return groupIds(drafts).flatMap((g) => drafts.filter((d) => d.gid === g));
}

/**
 * Ny animation i en binding: samme tag som bindingens øvrige animationer og den første passende
 * animation der ikke allerede er brugt (tekst → blink → …). Tekst-elementer starter med tekst,
 * figurer med fyldfarve.
 */
export function nextBinding(existing: BindingForm[], isText: boolean): BindingForm {
  const used = new Set(existing.map((d) => d.anim));
  const order: Anim[] = isText ? ['text', 'blink', 'fill', 'visible', 'opacity'] : ['fill', 'blink', 'visible', 'stroke', 'opacity'];
  const anim = order.find((a) => !used.has(a)) ?? order[0];
  const tag = [...existing].reverse().find((d) => d.tag && d.anim !== 'click:goto')?.tag ?? '';
  return emptyForm(tag, anim);
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
    prefix: str(p.prefix, ''),
    suffix: str(p.suffix, ''),
    on: str(p.on, f.on),
    off: str(p.off, f.off),
    thresholds: (p.thresholds ?? []).map((t: { value: number; color: string }) => ({ value: String(t.value), color: t.color })),
    invert: Boolean(p.invert),
    min: str(p.min, f.min),
    max: str(p.max, f.max),
    direction: p.direction ?? 'up',
    angle_min: str(p.angle_min, f.angle_min),
    angle_max: str(p.angle_max, f.angle_max),
    dx: str(p.dx, f.dx),
    dy: str(p.dy, f.dy),
    mode: p.mode === 'signed' || p.mode === 'code' ? p.mode : 'onoff',
    reverse: Boolean(p.reverse),
    base: str(p.base, f.base),
    light: str(p.light, f.light),
    speed: str(p.speed, f.speed),
    dash: str(p.dash, f.dash),
    arm: ['left', 'right', 'up', 'down'].includes(p.arm) ? p.arm : '',
    arm_flow: p.arm_flow === 'out' ? 'out' : 'in',
    dir_tag: str(p.dir_tag, ''),
    title: str(p.title, ''),
    confirm: p.confirm ?? f.confirm,
    ms: str(p.ms, f.ms),
    positions: Array.isArray(p.positions)
      ? p.positions.map((x: { value: number; label: string }) => ({ value: String(x.value), label: x.label }))
      : f.positions,
    drawing: str(p.drawing, ''),
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
  if (f.anim === 'click:goto') {
    if (!f.drawing) throw new Error('Vælg den tegning der skal åbnes');
    return { tag: '', anim: f.anim, params: { drawing: f.drawing } };
  }
  if (!f.tag.trim()) throw new Error('Vælg et tag');
  let params: Record<string, unknown> = {};
  switch (f.anim) {
    case 'text': {
      params = { true_text: f.true_text, false_text: f.false_text, show_unit: f.show_unit };
      // Mellemrum er bevidste ("Tank : ") og bevares; kun tekst der er helt tom udelades
      if (f.prefix !== '') params.prefix = f.prefix;
      if (f.suffix !== '') params.suffix = f.suffix;
      if (f.prefix.length > 40 || f.suffix.length > 40) throw new Error('Tekst før/efter må højst være 40 tegn');
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
    case 'move': {
      const dx = parseNumber(f.dx, 'Flyt X');
      const dy = parseNumber(f.dy, 'Flyt Y');
      if (dx === 0 && dy === 0) throw new Error('Flyt X og Y kan ikke begge være 0 — så flytter elementet sig ikke');
      if (Math.abs(dx) > 100000 || Math.abs(dy) > 100000) throw new Error('Flyt X/Y må højst være ±100000');
      params = { ...range(f), dx, dy };
      break;
    }
    case 'flow': {
      const speed = parseNumber(f.speed, 'Hastighed');
      if (speed < 5 || speed > 500) throw new Error('Hastighed skal være 5-500 (enheder pr. sekund)');
      const dash = parseNumber(f.dash, 'Streglængde');
      if (dash < 2 || dash > 200) throw new Error('Streglængde skal være 2-200');
      const base = f.base.trim(), light = f.light.trim();
      if (!base || !light) throw new Error('Vælg begge farver til løbelyset');
      if (base.toLowerCase() === light.toLowerCase()) throw new Error('Løbelysets to farver skal være forskellige — ellers kan man ikke se det løbe');
      const dirTag = f.dir_tag.trim();
      if (dirTag && dirTag === f.tag.trim()) throw new Error('Retnings-tagget skal være et andet tag end start/stop-tagget');
      params = { mode: f.mode, reverse: f.reverse, invert: f.mode === 'onoff' && f.invert, base, light, speed, dash,
        arm: f.arm, arm_flow: f.arm ? f.arm_flow : 'in', dir_tag: dirTag };
      break;
    }
    case 'click:write':
      params = { title: f.title.trim() };
      break;
    case 'click:toggle':
      params = { confirm: f.confirm };
      break;
    case 'click:select': {
      if (f.positions.length < 2 || f.positions.length > 8) throw new Error('En omskifter skal have 2-8 positioner');
      const positions = f.positions.map((x, i) => {
        const label = x.label.trim();
        if (!label) throw new Error(`Position ${i + 1}: angiv et navn`);
        if (label.length > 20) throw new Error(`Position ${i + 1}: navnet må højst være 20 tegn`);
        return { value: parseNumber(x.value, `Position ${i + 1}`), label };
      });
      if (new Set(positions.map((x) => x.value)).size !== positions.length) throw new Error('Positionerne skal have forskellige værdier');
      params = { positions, confirm: f.confirm, title: f.title.trim() };
      break;
    }
    case 'click:pulse': {
      const ms = parseNumber(f.ms, 'Pulslængde');
      if (!Number.isInteger(ms) || ms < 100 || ms > 10000) throw new Error('Pulslængde skal være 100-10000 ms');
      params = { ms, confirm: f.confirm };
      break;
    }
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
