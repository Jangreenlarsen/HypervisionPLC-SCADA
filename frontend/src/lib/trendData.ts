// Hjælpefunktioner til trend-graferne (rene funktioner — testet i trendData.test.ts).

/** Kategoriske farver i fast rækkefølge (validerede mod lys flade). Rød er udeladt — den er reserveret til alarmer. */
export const SERIES_COLORS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7'];
export const MAX_SERIES = SERIES_COLORS.length;

/** [t, gennemsnit, min, max] — som backend leverer. */
export type Point = [number, number | null, number | null, number | null];

/**
 * Flet serier med forskellige tidspunkter til uPlots format: én fælles x-række.
 * `null` = rigtigt hul (ingen gyldig værdi → brud i linjen); `undefined` = serien har bare
 * ikke et punkt netop dér (uPlot forbinder hen over det).
 */
export function align(series: Point[][], useMax: boolean[] = []): [number[], ...(number | null | undefined)[][]] {
  const xs = [...new Set(series.flatMap((s) => s.map((p) => p[0])))].sort((a, b) => a - b);
  const index = new Map(xs.map((x, i) => [x, i]));
  const ys = series.map((s, i) => {
    const col: (number | null | undefined)[] = new Array(xs.length).fill(undefined);
    // Til/fra: max pr. tidsspand, så en kort puls stadig ses som "Til" når der er zoomet ud
    for (const [t, avg, , max] of s) col[index.get(t)!] = useMax[i] ? max : avg;
    return col;
  });
  return [xs, ...ys];
}

/**
 * Tildel farver så et tag BEHOLDER sin farve, mens det er valgt (farve følger tagget, ikke
 * rækkefølgen). Nye tags får første ledige plads. Returnerer null-pladser hvis der er fyldt op.
 */
export function assignColors(selected: string[], previous: Record<string, number>): Record<string, number> {
  const next: Record<string, number> = {};
  for (const name of selected) if (name in previous) next[name] = previous[name];
  const used = new Set(Object.values(next));
  for (const name of selected) {
    if (name in next) continue;
    const free = SERIES_COLORS.findIndex((_, i) => !used.has(i));
    if (free < 0) continue;
    next[name] = free;
    used.add(free);
  }
  return next;
}

/** Gruppér tags pr. enhed — én graf pr. enhed (aldrig to y-akser i samme graf). */
export function groupByUnit<T extends { name: string; unit: string; isBool?: boolean }>(tags: T[]): [string, T[]][] {
  const groups = new Map<string, T[]>();
  for (const t of tags) {
    const key = t.isBool ? 'Til/fra' : t.unit || 'Uden enhed';
    groups.set(key, [...(groups.get(key) ?? []), t]);
  }
  return [...groups.entries()];
}

export const RANGES: { id: string; label: string; seconds: number }[] = [
  { id: '15m', label: '15 min', seconds: 900 },
  { id: '1h', label: '1 time', seconds: 3600 },
  { id: '8h', label: '8 timer', seconds: 8 * 3600 },
  { id: '24h', label: '24 timer', seconds: 86400 },
  { id: '7d', label: '7 dage', seconds: 7 * 86400 },
  { id: '30d', label: '30 dage', seconds: 30 * 86400 },
];
