// Tags oven på tegningen i Tegn (v6.8.0, Jan: "til og fra vælge at man også kan se de tags som er i brug ved de forskellige symboler").
// Kun visning: hvilke PLC-tags et symbol (eller et element med en binding) bruger, som en mærkat under det.
import { bindingTags } from './canvas';
import type { Binding } from './api';

/** Interne værdier (symbolets afledte værdier, flowberegningen, fjernede signalveje) er ikke PLC-tags. */
const INTERNAL = ['sym:', 'flow:', 'flowp:', 'flowlvl:', 'path:', '@'];
const isPlcTag = (t: string): boolean => !!t && !INTERNAL.some((p) => t.startsWith(p));

/** element-id → de tags, det bruger: symbolets opsætning og elementets egne bindinger (uden dubletter, i den rækkefølge de mødes). */
export function tagsByElement(symbols: { element: string; tags?: string[] }[],
  bindings: Pick<Binding, 'element' | 'tag' | 'anim' | 'params'>[]): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  const add = (el: string, t: string): void => {
    if (!el || !isPlcTag(t)) return;
    const list = (out[el] ??= []);
    if (!list.includes(t)) list.push(t);
  };
  for (const s of symbols) for (const t of s.tags ?? []) add(s.element, t);
  for (const b of bindings) for (const t of bindingTags(b)) add(b.element, t);
  return out;
}

/** Linjerne i mærkaten: højst `max` tags, resten som "+n flere". */
export function tagLines(tags: string[], max = 4): string[] {
  if (tags.length <= max) return tags;
  return [...tags.slice(0, max - 1), `+${tags.length - max + 1} flere`];
}
