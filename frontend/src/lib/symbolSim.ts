// Symboltest, avanceret (v0.110.0): flere simulerede tags og flere testanimationer på ét symbol, med redigerbare
// parametre. Alt kører lokalt i browseren og anvender præcis samme `applyBinding` som Overview — så det man ser her,
// er det man får i tegningen. Ren logik (ingen komponenter) — testet i symbolSim.test.ts.
import type { Binding, LiveValue, TagMeta } from './api';
import { applyBinding, resetAnim } from './animate';
import { alarmMarks, type MarkState } from './alarmMark';
import { SYMBOL_COLORS } from './symbols';
import { MAX_POSITIONS, MIN_POSITIONS, POS_ANIMS, ROOT, testBinding, type LibrarySetup, type TestPart } from './symbolTest';
import { ANIM_TXT, type AnimType, type SrcKind } from './symbolConfig';

export type Quality = LiveValue['quality'];
export type AlarmState = '' | MarkState;
export type PlayMode = 'off' | 'loop';

export interface SimTag {
  id: string;
  name: string;
  kind: SrcKind;
  /** antal positioner (kind = pos) */
  count: number;
  /** navne på positionerne (valgfrit) */
  labels: string[];
  /** talområde (kind = num) */
  min: number;
  max: number;
  value: number;
  unit: string;
  quality: Quality;
  /** værdien mangler (PLC nede) — som en binding uden live-værdi */
  missing: boolean;
  alarm: AlarmState;
  /** afspilning: værdien løber automatisk gennem sit område */
  play: PlayMode;
  /** sekunder for én hel runde */
  period: number;
}

export interface SimAnim {
  id: string;
  part: string;
  anim: AnimType;
  /** id på det simulerede tag animationen følger */
  tag: string;
  params: Record<string, any>;
  /** "Gælder i positionerne" følger dette positions-tag (id), når `params.only` er sat */
  posTag?: string;
}

export const MAX_TAGS = 8, MAX_ANIMS = 12;
export const DEFAULT_PERIOD = 6, MIN_PERIOD = 1, MAX_PERIOD = 60;

let counter = 0;
const uid = (prefix: string): string => `${prefix}${++counter}`;

export function newTag(existing: SimTag[], kind: SrcKind = 'bool'): SimTag {
  let n = existing.length + 1;
  while (existing.some((t) => t.name === `T${n}`)) n++;
  return { id: uid('t'), name: `T${n}`, kind, count: kind === 'pos' ? 3 : MIN_POSITIONS, labels: [], min: 0, max: 100,
    value: kind === 'bool' ? 1 : 0, unit: '', quality: 'good', missing: false, alarm: '', play: 'off', period: DEFAULT_PERIOD };
}

export const clampCount = (n: unknown): number => Math.min(MAX_POSITIONS, Math.max(MIN_POSITIONS, Math.round(Number(n)) || MIN_POSITIONS));

/** Højeste værdi tagget kan have (skyderen): 1 for til/fra, antal−1 for position, ellers max. */
export function tagRange(t: Pick<SimTag, 'kind' | 'count' | 'min' | 'max'>): { min: number; max: number } {
  if (t.kind === 'bool') return { min: 0, max: 1 };
  if (t.kind === 'pos') return { min: 0, max: clampCount(t.count) - 1 };
  return Number.isFinite(t.min) && Number.isFinite(t.max) && t.max > t.min ? { min: t.min, max: t.max } : { min: 0, max: 100 };
}

/** Hold værdien inden for tagget (efter skift af art/område). Hele tal for til/fra og position. */
export function clampValue(t: SimTag): number {
  const { min, max } = tagRange(t);
  const v = Number.isFinite(t.value) ? t.value : min;
  const c = Math.min(max, Math.max(min, v));
  return t.kind === 'num' ? c : Math.round(c);
}

/** Perioden holdt inden for grænserne (tomt/ugyldigt giver standarden). */
export const clampPeriod = (p: unknown): number => {
  const n = Number(p);
  return Number.isFinite(n) && n > 0 ? Math.min(MAX_PERIOD, Math.max(MIN_PERIOD, n)) : DEFAULT_PERIOD;
};

/**
 * Værdien et afspillet tag har `seconds` sekunder inde i afspilningen: til/fra er Til første halvdel af runden og
 * Fra anden; et tal løber op og ned mellem sit min og max; en position går gennem alle positionerne i runden.
 */
export function playValue(t: Pick<SimTag, 'kind' | 'count' | 'min' | 'max' | 'period'>, seconds: number): number {
  const period = clampPeriod(t.period);
  const frac = (((seconds % period) + period) % period) / period;
  if (t.kind === 'bool') return frac < 0.5 ? 1 : 0;
  if (t.kind === 'pos') return Math.min(clampCount(t.count) - 1, Math.floor(frac * clampCount(t.count)));
  const { min, max } = tagRange(t);
  const tri = 1 - Math.abs(2 * frac - 1);   // 0 → 1 → 0
  return Math.round((min + tri * (max - min)) * 100) / 100;
}

/** Hvilken art parametrene har for animationen på tagget: en position gælder kun de typer der har værdi pr. position. */
export const kindFor = (anim: AnimType, tag: Pick<SimTag, 'kind'>): SrcKind =>
  tag.kind === 'pos' && !POS_ANIMS.includes(anim) ? 'num' : tag.kind;

/** Standardparametre for animationen på tagget (som guiden ville foreslå dem). */
export function defaultParams(anim: AnimType, tag: Pick<SimTag, 'kind' | 'count' | 'labels'> & Partial<Pick<SimTag, 'min' | 'max'>>): Record<string, any> {
  const params = testBinding('', anim, kindFor(anim, tag), clampCount(tag.count)).params;
  // guidens standard giver alle positioner samme farve ved ≠ 2 positioner — i testen får hver position sin egen, så ændringen kan ses
  if (params.pos && (anim === 'fill' || anim === 'stroke') && tag.count !== 2) params.colors = Array.from({ length: clampCount(tag.count) }, (_, j) => POSITION_COLORS[j % POSITION_COLORS.length]);
  // tal og positioner: området følger tagget (en position er 0 … antal−1), så skyderen dækker hele animationens område
  if (!params.pos && 'min' in params && 'max' in params && tag.kind !== 'bool') {
    const r = tagRange({ kind: tag.kind, count: tag.count, min: tag.min ?? 0, max: tag.max ?? 100 });
    params.min = r.min;
    params.max = r.max;
  }
  if (params.pos && anim === 'text' && tag.labels.length) params.labels = Array.from({ length: clampCount(tag.count) }, (_, j) => tag.labels[j] || `Position ${j + 1}`);
  return params;
}

const POSITION_COLORS = ['#d6d6d6', '#7cc47f', '#ffd21a', '#c62828', '#7aa7c7', '#ff8c1a', '#555555', '#8fc8ea'];

export function newAnim(tag: SimTag, part: string, anim: AnimType): SimAnim {
  return { id: uid('a'), part, anim, tag: tag.id, params: defaultParams(anim, tag) };
}

/** Et tags art eller antal positioner er ændret: dets animationer får standardparametre for den nye art. */
export function retune(anims: SimAnim[], tag: SimTag): void {
  for (const a of anims) if (a.tag === tag.id) a.params = defaultParams(a.anim, tag);
}

/** Bibliotekets opsætning (som guiden foreslår den) som tag + animationer. */
export function fromSetup(setup: LibrarySetup): { tags: SimTag[]; anims: SimAnim[] } {
  const tag = newTag([], setup.kind);
  tag.name = 'Signal';
  if (setup.kind === 'pos') {
    tag.count = clampCount(setup.positions.length);
    tag.labels = [...setup.positions];
    tag.value = 0;
  } else if (setup.kind === 'num') tag.value = 0;
  const anims = setup.bindings.map((b): SimAnim => ({ id: uid('a'), part: b.element, anim: b.anim as AnimType, tag: tag.id, params: structuredClone(b.params) }));
  return { tags: [tag], anims };
}

/** Symbolets egne animationer (`data-hv-part`) som tag + animationer — til/fra-tag, ét for alle. */
export function fromOwn(parts: TestPart[]): { tags: SimTag[]; anims: SimAnim[] } {
  const tag = newTag([], 'bool');
  tag.name = 'Signal';
  const anims: SimAnim[] = [];
  for (const p of parts) {
    for (const o of p.own) anims.push({ id: uid('a'), part: p.id, anim: o.anim as AnimType, tag: tag.id, params: structuredClone(o.params) });
  }
  return { tags: [tag], anims };
}

// ------------------------------------------------------------------------------------------------ anvendelse

/**
 * Live-værdien tagget giver (ukendt = værdi mangler). Et til/fra-tag giver sand/falsk, som en coil fra PLC'en — så
 * tekst-animationen bruger sine Til/Fra-tekster; tal og positioner er tal.
 */
export function liveOfTag(t: SimTag): LiveValue {
  const value = t.kind === 'bool' ? Boolean(t.value) : t.value;
  // Som i driften: kun God og Kommunikationsfejl har en værdi (den sidst kendte ved kommunikationsfejl) — Dårlig og
  // Ukendt har ingen
  const none = t.missing || t.quality === 'bad' || t.quality === 'unknown';
  return { value: none ? null : value, quality: t.quality, ts: Date.now() / 1000, error: t.quality === 'good' ? null : 'simuleret' };
}

export const metaOf = (t: SimTag): TagMeta => ({ unit: t.unit, decimals: null, description: t.name, plc: 'test' });

export function bindingOf(a: SimAnim, tags: SimTag[]): Binding {
  const tag = tags.find((t) => t.id === a.tag);
  const params = { ...a.params };
  // løbelysets retnings-tag vælges blandt de simulerede tags (navnet), og følger det
  return { element: a.part, tag: tag?.name ?? 'test', anim: a.anim, params };
}

const elementOf = (host: Element, part: string): Element | null =>
  part === ROOT ? host.firstElementChild : host.querySelector(`[id="${CSS.escape(part)}"]`);

/** Anvend én animation. Returnerer false hvis delen ikke findes. */
export function applySim(host: Element, a: SimAnim, tags: SimTag[]): boolean {
  const el = elementOf(host, a.part);
  const tag = tags.find((t) => t.id === a.tag);
  if (!el || !tag) return false;
  const dir = typeof a.params.dir_tag === 'string' && a.params.dir_tag ? tags.find((t) => t.name === a.params.dir_tag) : undefined;
  const pos = a.posTag && Array.isArray(a.params.only) ? tags.find((t) => t.id === a.posTag) : undefined;
  applyBinding(el, bindingOf(a, tags), liveOfTag(tag), metaOf(tag), dir ? liveOfTag(dir) : undefined, pos ? liveOfTag(pos) : undefined);
  return true;
}

export interface Applied { part: string; anim: AnimType; params: Record<string, any>; key: string }

/**
 * Bring symbolet i overensstemmelse med tags og animationer: det der er ændret eller fjernet nulstilles (delen som
 * tegnet), derefter anvendes alle. Returnerer hvad der nu er anvendt og de dele der ikke findes.
 */
export function syncSim(host: Element, anims: SimAnim[], tags: SimTag[], applied: Map<string, Applied>): string[] {
  const missing: string[] = [];
  const now = new Map<string, SimAnim>(anims.map((a) => [a.id, a]));
  for (const [id, old] of [...applied]) {
    const a = now.get(id);
    if (a && a.part === old.part && a.anim === old.anim && JSON.stringify(a.params) === old.key) continue;
    const el = elementOf(host, old.part);
    if (el) resetAnim(el, old.anim, old.params);
    applied.delete(id);
  }
  for (const a of anims) {
    if (!applySim(host, a, tags)) {
      if (!missing.includes(a.part)) missing.push(a.part);
      continue;
    }
    applied.set(a.id, { part: a.part, anim: a.anim, params: structuredClone(a.params), key: JSON.stringify(a.params) });
  }
  return missing;
}

/** Nulstil alt anvendt (delene som tegnet). */
export function clearSim(host: Element, applied: Map<string, Applied>): void {
  for (const old of applied.values()) {
    const el = elementOf(host, old.part);
    if (el) resetAnim(el, old.anim, old.params);
  }
  applied.clear();
}

/** Alarmmarkeringen (rød) som i Overview: kun dele der viser tagget som værdi/niveau. */
export function alarmClasses(anims: SimAnim[], tags: SimTag[]): Map<string, MarkState> {
  const states = new Map<string, MarkState>();
  for (const t of tags) if (t.alarm) states.set(t.name, t.alarm);
  return alarmMarks(anims.map((a) => bindingOf(a, tags)), states);
}

export function applyAlarmMarks(host: Element, anims: SimAnim[], tags: SimTag[]): void {
  for (const a of anims) {
    const el = elementOf(host, a.part);
    el?.classList.remove('hv-alarm-unack', 'hv-alarm-ack');
  }
  for (const [part, st] of alarmClasses(anims, tags)) {
    elementOf(host, part)?.classList.add(st === 'unack' ? 'hv-alarm-unack' : 'hv-alarm-ack');
  }
}

// ------------------------------------------------------------------------------------------------ parameter-editor

export type Field = { key: string; label: string; hint?: string } & (
  | { type: 'number'; step?: number; optional?: boolean }
  | { type: 'color' }
  | { type: 'bool'; defaultOn?: boolean }
  | { type: 'text'; optional?: boolean }
  | { type: 'select'; options: { v: string; label: string }[]; optional?: boolean }
  | { type: 'colors'; n: number }
  | { type: 'numbers'; n: number; step?: number }
  | { type: 'bools'; n: number }
  | { type: 'texts'; n: number }
  | { type: 'thresholds' }
  | { type: 'palette' }
  | { type: 'tag' }
);

const SPEED = [{ v: 'slow', label: 'Langsom (0,5 Hz)' }, { v: 'normal', label: 'Normal (1 Hz)' }, { v: 'fast', label: 'Hurtig (2 Hz)' }];
const DIRECTION = [{ v: 'up', label: 'Op' }, { v: 'down', label: 'Ned' }, { v: 'left', label: 'Venstre' }, { v: 'right', label: 'Højre' }];
const GLIDE = [{ v: '', label: 'Standard' }, { v: '0', label: 'Med det samme' }, { v: '0.2', label: 'Hurtig (0,2 s)' }, { v: '0.4', label: 'Normal (0,4 s)' }, { v: '1', label: '1 s' }, { v: '2', label: '2 s' }, { v: '5', label: 'Ekstra langsom (5 s)' }];
const ARMS = [{ v: '', label: 'Ingen' }, { v: 'left', label: 'Venstre' }, { v: 'right', label: 'Højre' }, { v: 'up', label: 'Op' }, { v: 'down', label: 'Ned' }];

/** Felterne en animation kan redigeres med (samme parametre som guiden skriver) — ud fra typen og tagget. */
export function paramFields(anim: AnimType, tag: Pick<SimTag, 'kind' | 'count'>): Field[] {
  const kind = kindFor(anim, tag);
  const n = clampCount(tag.count);
  const rangeFields = (): Field[] => [
    { key: 'min', label: 'Fra værdi', type: 'number' }, { key: 'max', label: 'Til værdi', type: 'number' },
  ];
  const active = (): Field[] => (kind === 'pos' ? [{ key: 'set', label: 'Aktiv i positionerne', type: 'bools', n }]
    : kind === 'num' ? [{ key: 'at_least', label: 'Aktiv fra værdi', type: 'number' }]
      : [{ key: 'invert', label: 'Omvendt (aktiv ved Fra)', type: 'bool' }]);
  switch (anim) {
    case 'fill':
    case 'stroke':
      if (kind === 'pos') return [{ key: 'colors', label: 'Farve pr. position', type: 'colors', n }];
      if (kind === 'bool') return [{ key: 'on', label: 'Til', type: 'color' }, { key: 'off', label: 'Fra', type: 'color' }];
      return [{ key: 'off', label: 'Under første grænse', type: 'color' }, { key: 'thresholds', label: 'Grænser', type: 'thresholds' }];
    case 'blink':
      return [...active(), { key: 'speed', label: 'Hastighed', type: 'select', options: SPEED }];
    case 'visible':
    case 'spin':
      return active();
    case 'flicker':
      return [...active(), { key: 'palette', label: 'Flammens farver', type: 'palette' }];
    case 'level':
      return [...rangeFields(), { key: 'direction', label: 'Retning', type: 'select', options: DIRECTION }];
    case 'opacity':
      return rangeFields();
    case 'scale':
      return [...rangeFields(), { key: 'size_min', label: 'Størrelse ved fra (%)', type: 'number' }, { key: 'size_max', label: 'Størrelse ved til (%)', type: 'number' }];
    case 'rotate':
      return [
        ...(kind === 'pos' ? [{ key: 'angles', label: 'Vinkel pr. position (°)', type: 'numbers', n } as Field]
          : [...rangeFields(), { key: 'angle_min', label: 'Vinkel ved fra (°)', type: 'number' } as Field, { key: 'angle_max', label: 'Vinkel ved til (°)', type: 'number' } as Field]),
        { key: 'glide_s', label: 'Hastighed', type: 'select', options: GLIDE, optional: true },
      ];
    case 'move':
      return kind === 'pos'
        ? [{ key: 'dxs', label: 'Flyt vandret pr. position', type: 'numbers', n }, { key: 'dys', label: 'Flyt lodret pr. position', type: 'numbers', n }]
        : [...rangeFields(), { key: 'dx', label: 'Flyt vandret', type: 'number' }, { key: 'dy', label: 'Flyt lodret', type: 'number' }];
    case 'text':
      if (kind === 'pos') return [{ key: 'labels', label: 'Tekst pr. position', type: 'texts', n }];
      if (kind === 'bool') return [{ key: 'true_text', label: 'Tekst ved Til', type: 'text', optional: true }, { key: 'false_text', label: 'Tekst ved Fra', type: 'text', optional: true }];
      return [
        { key: 'prefix', label: 'Før værdien', type: 'text', optional: true }, { key: 'suffix', label: 'Efter værdien', type: 'text', optional: true },
        { key: 'decimals', label: 'Decimaler', type: 'number', optional: true }, { key: 'expression', label: 'Beregning (fx x / 10)', type: 'text', optional: true },
        { key: 'show_unit', label: 'Vis enhed', type: 'bool', defaultOn: true },
      ];
    case 'flow':
      return [
        ...(kind === 'pos' ? [{ key: 'dirs', label: 'Retning pr. position (-1, 0, 1)', type: 'numbers', n, step: 1 } as Field]
          : [{ key: 'mode', label: 'Styring', type: 'select', options: [{ v: 'onoff', label: 'Til = kør' }, { v: 'signed', label: 'Fortegn = retning' }, { v: 'code', label: 'Kode (1 frem, 2 tilbage)' }] } as Field]),
        { key: 'reverse', label: 'Vend retningen', type: 'bool' },
        { key: 'base', label: 'Rørets farve', type: 'color' }, { key: 'light', label: 'Løbelysets farve', type: 'color' },
        { key: 'speed', label: 'Hastighed', type: 'number' }, { key: 'dash', label: 'Længde på streg', type: 'number' },
        { key: 'arm', label: 'Gren (T-stykke)', type: 'select', options: ARMS }, { key: 'arm_flow', label: 'Grenen', type: 'select', options: [{ v: 'in', label: 'Tilløb' }, { v: 'out', label: 'Afgang' }] },
        { key: 'dir_tag', label: 'Retnings-tag', type: 'tag' },
      ];
  }
}

/** Sæt ét felt: tomt valgfrit felt fjernes; tal gøres til tal. Returnerer nye parametre (originalen røres ikke). */
export function setParam(params: Record<string, any>, f: Field, value: unknown): Record<string, any> {
  const out = { ...params };
  const optional = 'optional' in f && f.optional;
  if (f.type === 'number' || (f.type === 'select' && f.key === 'glide_s')) {
    if (value === '' || value === null || value === undefined) {
      if (optional) delete out[f.key];
      return out;
    }
    const n = Number(value);
    if (Number.isFinite(n)) out[f.key] = n;
    return out;
  }
  if ((f.type === 'text' || f.type === 'select') && value === '' && optional) {
    delete out[f.key];
    return out;
  }
  out[f.key] = value;
  return out;
}

/** Grænserne for en farve efter tal (værdi → farve): tilføj, ret og fjern. */
export type Threshold = { value: number; color: string };
export function setThreshold(params: Record<string, any>, i: number, patch: Partial<Threshold>): Record<string, any> {
  const list: Threshold[] = (params.thresholds ?? []).map((t: Threshold) => ({ ...t }));
  if (list[i]) list[i] = { ...list[i], ...patch };
  return { ...params, thresholds: list };
}
export function addThreshold(params: Record<string, any>): Record<string, any> {
  const list: Threshold[] = [...(params.thresholds ?? [])];
  const last = list[list.length - 1];
  list.push({ value: last ? Number(last.value) + 10 : 50, color: last?.color ?? '#b26a00' });
  return { ...params, thresholds: list };
}
export function removeThreshold(params: Record<string, any>, i: number): Record<string, any> {
  return { ...params, thresholds: (params.thresholds ?? []).filter((_: Threshold, j: number) => j !== i) };
}

/** Sæt ét element i en liste-parameter (farve/tal/tekst/til-fra pr. position). */
export function setItem(params: Record<string, any>, key: string, index: number, value: unknown, length: number): Record<string, any> {
  const list = Array.isArray(params[key]) ? [...params[key]] : [];
  while (list.length < length) list.push(key === 'set' ? false : key === 'colors' ? '' : key === 'labels' ? '' : 0);
  list[index] = value;
  return { ...params, [key]: list };
}

/** Paletten et farvefelt tilbyder: bibliotekets symbolfarver (SYMBOLSTANDARD §8) og animationernes signalfarver. */
export const PALETTE: readonly string[] = [...new Set([
  '#2e7d32', '#9e9e9e', '#b26a00', '#c62828', '#7cc47f', '#d6d6d6', '#ff3b00', '#ff8c1a', '#ffd21a', '#555555', '#8fc8ea',
  ...SYMBOL_COLORS,
])];

/** #rgb → #rrggbb (til `<input type=color>`); ukendt skrivemåde giver sort. */
export function toHex6(c: string): string {
  const s = (c ?? '').trim().toLowerCase();
  if (/^#[0-9a-f]{6}$/.test(s)) return s;
  const m = /^#([0-9a-f])([0-9a-f])([0-9a-f])$/.exec(s);
  return m ? `#${m[1]}${m[1]}${m[2]}${m[2]}${m[3]}${m[3]}` : '#000000';
}

/** Er teksten en farve browseren forstår (#rgb, #rrggbb, #rrggbbaa eller et farvenavn som red)? */
export function isColor(c: unknown): boolean {
  const v = typeof c === 'string' ? c.trim() : '';
  if (!v) return false;
  if (/^#([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$/i.test(v)) return true;
  if (v.startsWith('#') || typeof document === 'undefined') return false;
  const st = document.createElement('span').style;
  st.color = v;
  return st.color !== '';
}

/**
 * Animationer af samme type der rammer samme del (eller hele symbolet) — den nederste i listen vinder, så en ændring i en
 * af dem kan se ud til ikke at virke. Returnerer en besked pr. par.
 */
export function conflicts(anims: SimAnim[], label: (part: string) => string): string[] {
  const out: string[] = [];
  for (let i = 0; i < anims.length; i++) {
    for (let j = i + 1; j < anims.length; j++) {
      const a = anims[i], b = anims[j];
      if (a.anim !== b.anim) continue;
      if (!(a.part === b.part || a.part === ROOT || b.part === ROOT)) continue;
      out.push(`${ANIM_TXT[a.anim]} ligger både på ${label(a.part)} og ${label(b.part)} — den nederste i listen vinder.`);
    }
  }
  return out;
}
