// Trends ud fra symbolerne (v0.80.0): vælg et symbol i Trends, og dets tags vises som kurver.

export interface TrendSymbol { drawing: string; drawing_name: string; element: string; name: string; tags: string[] }
export interface TagHistory { name: string; trend: boolean; samples: number }

/** Nøglen for et symbol — også ruten i Trends: #trends/<tegning>/<element>. */
export const symbolKey = (s: { drawing: string; element: string }): string => `${s.drawing}/${s.element}`;

/** Ruten "trends/<tegning>/<element>" → nøglen, eller null. */
export function keyFromRoute(route: string): string | null {
  const [page, drawing, element] = route.split('/');
  return page === 'trends' && drawing && element ? `${drawing}/${element}` : null;
}

/**
 * Hvilke af symbolets tags der kan vises: dem med historik (slået til eller gemte værdier), højst `max`.
 * `missing` = tags uden historik (kan slås til); `over` = tags der ikke var plads til.
 */
export function symbolSeries(sym: TrendSymbol, tags: TagHistory[], max: number): { show: string[]; missing: string[]; over: string[] } {
  const byName = new Map(tags.map((t) => [t.name, t]));
  const known = sym.tags.filter((n) => byName.has(n));
  const withHistory = known.filter((n) => byName.get(n)!.trend || byName.get(n)!.samples > 0);
  return {
    show: withHistory.slice(0, max),
    missing: known.filter((n) => !withHistory.includes(n)),
    over: withHistory.slice(max),
  };
}

/** Symbolerne grupperet pr. tegning (til rullelisten), tegninger og symboler i alfabetisk orden. */
export function byDrawing(list: TrendSymbol[]): [string, TrendSymbol[]][] {
  const groups = new Map<string, TrendSymbol[]>();
  for (const s of list) groups.set(s.drawing_name, [...(groups.get(s.drawing_name) ?? []), s]);
  return [...groups.entries()]
    .sort(([a], [b]) => a.localeCompare(b, 'da'))
    .map(([d, l]) => [d, [...l].sort((a, b) => a.name.localeCompare(b.name, 'da', { numeric: true }))]);
}
