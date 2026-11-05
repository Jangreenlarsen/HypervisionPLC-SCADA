// Symbolbiblioteket samlet: de indbyggede symboler (symbols.ts) + egne symboler gemt fra Tegn (v3.28.0) og opdelingen
// i sektioner (backend/app/services/library.py). Ren logik her — testet i library.test.ts; tilstanden ligger i
// libraryStore.svelte.ts.
import { sanitizeSvgFragment } from './svg';
import { CATEGORIES, SYMBOLS, type SymbolDef } from './symbols';
import type { SymbolConfig } from './symbolConfig';

export const OWN_SECTION = 'egne';
export const OWN_LABEL = 'Egne symboler';

export interface OwnSymbol {
  type: string; label: string; hint: string; svg: string; preset: SymbolConfig | null; version: number;
  created_at: number; created_by: string; updated_at: number; updated_by: string;
}
export interface Layout {
  sections: { id: string; label: string }[];
  order: string[];
  /** symboltype → [sektion, plads]; mangler et symbol, står det i sin egen kategori (egne: "Egne symboler") */
  items: Record<string, [string, number]>;
  rev: number;
}
export interface Section { id: string; label: string; builtin: boolean }

export const emptyLayout = (): Layout => ({ sections: [], order: [], items: {}, rev: 0 });

/** Et eget symbol som bibliotekssymbol. Grafikken er renset på serveren — og renses igen her (forsvar i dybden). */
export function ownDef(s: OwnSymbol): SymbolDef {
  return { id: s.type, label: s.label, hint: s.hint || 'Eget symbol', category: OWN_SECTION, svg: sanitizeSvgFragment(s.svg), version: s.version };
}

/** Alle symboler: de indbyggede først, så de egne. */
export function allDefs(own: OwnSymbol[]): SymbolDef[] {
  return [...SYMBOLS, ...own.map(ownDef)];
}

/** Sektionerne i opdelingens rækkefølge: indbyggede kategorier, "Egne symboler" og egne sektioner. */
export function sections(layout: Layout): Section[] {
  const all: Section[] = [
    ...CATEGORIES.map((c) => ({ id: c.id as string, label: c.label, builtin: true })),
    { id: OWN_SECTION, label: OWN_LABEL, builtin: true },
    ...layout.sections.map((s) => ({ ...s, builtin: false })),
  ];
  const rank = new Map(layout.order.map((id, i) => [id, i]));
  return all
    .map((s, i) => ({ s, i }))
    .sort((a, b) => (rank.get(a.s.id) ?? 1000 + a.i) - (rank.get(b.s.id) ?? 1000 + b.i))
    .map((x) => x.s);
}

export function sectionOf(def: SymbolDef, layout: Layout): string {
  const ids = new Set(sections(layout).map((s) => s.id));
  const placed = layout.items[def.id]?.[0];
  return placed && ids.has(placed) ? placed : def.category;
}

/** Symbolerne i en sektion: dem med en plads først (efter pladsen), derefter resten i bibliotekets rækkefølge. */
export function symbolsIn(defs: SymbolDef[], layout: Layout, section: string, filter = ''): SymbolDef[] {
  const q = filter.trim().toLowerCase();
  return defs
    .map((d, i) => ({ d, i }))
    .filter(({ d }) => sectionOf(d, layout) === section && (!q || d.label.toLowerCase().includes(q) || d.hint.toLowerCase().includes(q)))
    .sort((a, b) => (layout.items[a.d.id]?.[1] ?? 100000 + a.i) - (layout.items[b.d.id]?.[1] ?? 100000 + b.i))
    .map((x) => x.d);
}

/** Flyt et symbol til en sektion og/eller plads (index i sektionen) → nyt layout; alle i sektionen får fast plads. */
export function moveSymbol(defs: SymbolDef[], layout: Layout, id: string, section: string, index: number): Layout {
  const def = defs.find((d) => d.id === id);
  if (!def) return layout;
  const list = symbolsIn(defs, layout, section).filter((d) => d.id !== id);
  list.splice(Math.max(0, Math.min(index, list.length)), 0, def);
  const items = { ...layout.items };
  list.forEach((d, i) => (items[d.id] = [section, i]));
  return { ...layout, items };
}

/** Standardopsætningen for et eget symbol, med delene oversat fra delnavn til id'et i tegningen. */
export function presetFor(preset: SymbolConfig | null, partOf: (pid: string) => string | undefined): SymbolConfig | null {
  if (!preset) return null;
  const cfg: SymbolConfig = structuredClone(preset);
  cfg.anims = cfg.anims
    .map((a) => (a.part === 'all' ? a : { ...a, part: partOf(a.part) ?? '' }))
    .filter((a) => a.part !== '');
  return cfg;
}

/** Næste ledige id til en ny egen sektion. */
export function newSectionId(layout: Layout): string {
  let i = 1;
  while (layout.sections.some((s) => s.id === `s${i}`)) i++;
  return `s${i}`;
}
