// Live preview ved animationerne i symbol-guiden (v2.10.0): guidens opsætning → de samme bindinger som Overview bruger
// (backendens `config_bindings`), plus de kontroller (Fra/Til, skyder, position) preview'et styres med. Ren logik — testet i
// animPreview.test.ts. Selve tegningen sker af `renderAll` (canvas.ts), så preview'et ser ud som på Overview.
import type { Binding, LiveValue } from './api';
import { BY_VALUE_TYPES, ON, POS, isLogicRef, parseAlarmRef, parseValRef, type Anim, type SymbolConfig } from './symbolConfig';
import { clampCount, playValue } from './symbolSim';

export const POS_TAG = 'preview:pos';
export const PLAY_PERIOD_S = 6;

export interface PreviewControl {
  /** Det pseudo-tagnavn bindingerne læser */
  name: string;
  label: string;
  kind: 'bool' | 'num' | 'pos';
  min: number;
  max: number;
  step: number;
  /** positionernes navne (kind = pos) */
  labels: string[];
}

export interface Preview {
  bindings: Binding[];
  controls: PreviewControl[];
  /** animationer uden kilde endnu (vises ikke) */
  unset: number;
}

type KindOf = (tag: string) => 'bool' | 'num' | 'unknown';

/** Navnet bindingerne bruger for en kilde: `@pos`, en logikblok, en alarm eller et tag. "Altid til" og en fast værdi står som de er. */
function nameOf(src: string): string {
  if (src === POS) return POS_TAG;
  if (src === ON || parseValRef(src) !== null) return src;
  const alarm = parseAlarmRef(src);
  if (alarm) return `preview:alarm:${alarm.kind}:${alarm.tag}`;
  if (isLogicRef(src)) return `preview:logic:${src.slice(1)}`;
  return src;
}

const labelOf = (src: string): string => {
  if (src === POS) return 'Symbolets position';
  const alarm = parseAlarmRef(src);
  if (alarm) return `Alarm ${alarm.kind === 'unack' ? 'ukvitteret' : 'aktiv'}: ${alarm.tag}`;
  if (isLogicRef(src)) return `Logikblok ${src.slice(1)}`;
  return src;
};

/** Området et tal-tags skyder dækker: animationernes Min/Max, ellers op over den højeste grænse, ellers 0–100. */
function numRange(anims: Anim[]): { min: number; max: number } {
  for (const a of anims) {
    const { min, max } = a.params ?? {};
    if (typeof min === 'number' && typeof max === 'number' && max > min) return { min, max };
  }
  const limits = anims.flatMap((a) => (Array.isArray(a.params?.thresholds) ? a.params.thresholds.map((t: { value: number }) => Number(t.value)) : []))
    .filter(Number.isFinite);
  if (limits.length) {
    const hi = Math.max(...limits);
    return { min: 0, max: hi > 0 ? Math.ceil(hi * 1.25) : 100 };
  }
  return { min: 0, max: 100 };
}

export function buildPreview(cfg: SymbolConfig, element: string, kindOf: KindOf): Preview {
  const isPos = cfg.op === 'positions';
  const labels = cfg.positions.map((p, j) => p.label || `Position ${j + 1}`);
  const byValue = (a: Anim): boolean => !!a.by_value && isPos && !!a.src && !a.src.startsWith('@') && BY_VALUE_TYPES.includes(a.type);
  const bindings: Binding[] = [];
  const bySrc = new Map<string, Anim[]>();   // kilde → animationerne der bruger den (styrer kontrollens område)
  let unset = 0;
  let usesOnly = false;
  cfg.anims.forEach((a, i) => {
    if (!a.src || (a.src.startsWith('@val:') && parseValRef(a.src) === null)) { unset++; return; }
    const params: Record<string, any> = Object.fromEntries(Object.entries(a.params ?? {}).filter(([, v]) => v !== null && v !== undefined));
    const pos = a.src === POS || byValue(a);
    const src = byValue(a) ? POS : a.src;   // "pr. værdi": positionens nummer styrer (i preview'et vælges positionen direkte)
    if (pos) {
      params.pos = true;
      delete params.pos_values;
      if (a.type === 'text') params.labels = labels;
    }
    if (a.only?.length) { params.only = a.only; params.pos_tag = POS_TAG; usesOnly = true; }
    if (a.when) params.when = true;
    if (typeof params.dir_tag === 'string' && params.dir_tag) {
      const dir = params.dir_tag;
      params.dir_tag = nameOf(dir);
      if (!bySrc.has(`dir:${dir}`)) bySrc.set(`dir:${dir}`, []);
    }
    bindings.push({ element: a.part === 'all' ? element : a.part, tag: nameOf(src), anim: a.type, params, source: 'symbol', symbol: element, position: 1000 + i });
    bySrc.set(src, [...(bySrc.get(src) ?? []), a]);
  });
  if (usesOnly && !bySrc.has(POS)) bySrc.set(POS, []);

  const controls: PreviewControl[] = [];
  const n = clampCount(cfg.positions.length || 2);
  for (const [src, anims] of bySrc) {
    if (src === ON || parseValRef(src) !== null) continue;   // fast: intet at styre
    if (src.startsWith('dir:')) {
      const dir = src.slice(4);
      controls.push({ name: nameOf(dir), label: `Retning: ${labelOf(dir)}`, kind: 'num', min: -1, max: 2, step: 1, labels: [] });
      continue;
    }
    if (src === POS) {
      controls.push({ name: POS_TAG, label: labelOf(POS), kind: 'pos', min: 0, max: n - 1, step: 1, labels });
      continue;
    }
    const bool = parseAlarmRef(src) !== null || isLogicRef(src) || kindOf(src) === 'bool';
    if (bool) controls.push({ name: nameOf(src), label: labelOf(src), kind: 'bool', min: 0, max: 1, step: 1, labels: [] });
    else {
      const r = numRange(anims);
      controls.push({ name: nameOf(src), label: labelOf(src), kind: 'num', min: r.min, max: r.max, step: Math.max((r.max - r.min) / 100, 0.01), labels: [] });
    }
  }
  return { bindings, controls: controls.filter((c, i) => controls.findIndex((x) => x.name === c.name) === i), unset };
}

/** Kontrollernes værdier som live-værdier (til/fra som sand/falsk, som en coil fra PLC'en). */
export function previewValues(controls: PreviewControl[], state: Record<string, number>): Record<string, LiveValue> {
  const out: Record<string, LiveValue> = {};
  for (const c of controls) {
    const raw = state[c.name];
    const v = Math.min(c.max, Math.max(c.min, Number.isFinite(raw) ? raw : c.min));
    out[c.name] = { value: c.kind === 'bool' ? v >= 1 : v, quality: 'good', ts: 0, error: null };
  }
  return out;
}

/** Værdierne `seconds` sekunder inde i en afspilning: alle kontroller løber gennem deres område. */
export function playState(controls: PreviewControl[], seconds: number): Record<string, number> {
  const out: Record<string, number> = {};
  for (const c of controls) {
    out[c.name] = playValue({ kind: c.kind, count: c.kind === 'pos' ? c.max + 1 : 2, min: c.min, max: c.max, period: PLAY_PERIOD_S }, seconds);
  }
  return out;
}
