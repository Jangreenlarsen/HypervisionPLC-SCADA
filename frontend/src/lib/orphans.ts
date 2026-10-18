// Forsvundne elementer (v0.83.0): bindinger på elementer, der ikke findes i tegningens aktive version
// (slettet i Tegn, eller fået et nyt id). Hjælpere til at vise dem og flytte dem til et andet element.
import type { Binding } from './api';

export const MAX_BINDINGS = 10;   // samme grænse som serveren (pr. element)

type Raw = Pick<Binding, 'element' | 'tag' | 'anim' | 'params'>;
const strip = (b: Raw) => ({ tag: b.tag, anim: b.anim, params: b.params ?? {} });

/** Bindingerne pr. forsvundet element, i serverens rækkefølge. */
export function orphanGroups<T extends Raw>(all: T[], orphans: string[]): Record<string, T[]> {
  return Object.fromEntries(orphans.map((o) => [o, all.filter((b) => b.element === o)]));
}

/**
 * Elementets egne bindinger + de flyttede (dubletter springes over) som PUT-data til målet.
 * Fejl, hvis der bliver for mange.
 */
export function mergeMoved(target: Raw[], moved: Raw[]): { bindings: ReturnType<typeof strip>[] } | { error: string } {
  const out = target.map(strip);
  const seen = new Set(out.map((b) => JSON.stringify(b)));
  for (const b of moved.map(strip)) {
    const k = JSON.stringify(b);
    if (!seen.has(k)) { seen.add(k); out.push(b); }
  }
  if (out.length > MAX_BINDINGS) {
    return { error: `Elementet ville få ${out.length} bindinger — højst ${MAX_BINDINGS}. Fjern nogle først.` };
  }
  return { bindings: out };
}
