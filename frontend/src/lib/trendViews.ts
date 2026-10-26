// Gemte trend-visninger (v1.16.0): et navn (fx "Tank temp") på tags, grafer og periode. Ren logik — testet i trendViews.test.ts.

export interface TrendView { name: string; tags: string[]; assign: Record<string, number>; range: string }

/**
 * Det en visning giver for den der åbner den: kun de tags, brugeren kan se/trende (`available`), højst `max` kurver, graf-valg kun for dem.
 * `missing` = tags i visningen, der ikke er tilgængelige (slettet, uden historik eller uden adgang).
 */
export function applyView(view: TrendView, available: ReadonlySet<string>, max: number): { tags: string[]; assign: Record<string, number>; missing: string[]; over: string[] } {
  const present = view.tags.filter((t) => available.has(t));
  const tags = present.slice(0, max);
  const assign: Record<string, number> = {};
  for (const t of tags) if (view.assign[t]) assign[t] = view.assign[t];
  return { tags, assign, missing: view.tags.filter((t) => !available.has(t)), over: present.slice(max) };
}

/** Visningen med det aktuelle udvalg: graf-valg kun for de valgte tags; en brugerdefineret periode huskes ikke (→ 1 time). */
export function viewFrom(name: string, tags: string[], assign: Record<string, number>, range: string, knownRanges: readonly string[]): TrendView {
  const own: Record<string, number> = {};
  for (const t of tags) if (assign[t]) own[t] = assign[t];
  return { name: name.trim(), tags: [...tags], assign: own, range: knownRanges.includes(range) ? range : '1h' };
}

/** Samme udvalg, grafer og periode? (til at vise, om den valgte visning er ændret siden den blev gemt) */
export function sameView(a: TrendView, b: TrendView): boolean {
  const ka = Object.keys(a.assign).sort(), kb = Object.keys(b.assign).sort();
  return a.range === b.range && a.tags.length === b.tags.length && a.tags.every((t, i) => t === b.tags[i])
    && ka.length === kb.length && ka.every((k, i) => k === kb[i] && a.assign[k] === b.assign[k]);
}
