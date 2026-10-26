// Hjælpefunktioner til trend-graferne (rene funktioner — testet i trendData.test.ts).

/** Kategoriske farver i fast rækkefølge (validerede mod lys flade). Rød er udeladt — den er reserveret til alarmer. */
export const SERIES_COLORS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7'];
/** Højst så mange kurver ad gangen. Ud over farverne (7) skelnes kurverne på stregtype (stiplet). */
export const MAX_SERIES = 12;

/** Farve for kurve nr. i (farverne genbruges efter nr. 7 — så er linjen stiplet, se `dashOf`). */
export const colorOf = (i: number): string => SERIES_COLORS[i % SERIES_COLORS.length];
export const dashOf = (i: number): number[] | undefined => (i >= SERIES_COLORS.length ? [7, 4] : undefined);

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
 * Indeks for værdier uden en gyldig nabo (fx kun ét punkt endnu, eller én måling mellem to huller).
 * En linje kræver to punkter, så de ville ellers være usynlige — de vises i stedet som en prik.
 * `undefined` (serien har ikke et punkt dér) springes over; `null` (hul) bryder linjen.
 */
export function isolatedPoints(ys: (number | null | undefined)[]): number[] {
  const defined: number[] = [];
  ys.forEach((y, i) => { if (y !== undefined) defined.push(i); });
  return defined.filter((i, k) => {
    if (ys[i] === null) return false;
    const prev = k > 0 ? ys[defined[k - 1]] : null;
    const next = k < defined.length - 1 ? ys[defined[k + 1]] : null;
    return prev === null && next === null;
  });
}

/**
 * Tildel farver så et tag BEHOLDER sin farve, mens det er valgt (farve følger tagget, ikke
 * rækkefølgen). Nye tags får første ledige plads. Returnerer null-pladser hvis der er fyldt op.
 */
export function assignColors(selected: string[], previous: Record<string, number>, max: number = MAX_SERIES): Record<string, number> {
  const next: Record<string, number> = {};
  for (const name of selected) if (name in previous) next[name] = previous[name];
  const used = new Set(Object.values(next));
  for (const name of selected) {
    if (name in next) continue;
    let free = 0;
    while (free < max && used.has(free)) free++;
    if (free >= max) continue;
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

/**
 * Gruppér tags i grafer. Et tag uden valg (Auto) kommer i grafen for sin enhed; et tag med et grafnummer lægges i
 * "Graf N" sammen med de andre tags med samme nummer (brugerens valg — blandede enheder deler y-akse).
 * Automatiske grafer står først, derefter de valgte i nummerorden.
 */
export function groupTags<T extends { name: string; unit: string; isBool?: boolean }>(
  tags: T[], assign: Record<string, number>,
): [string, T[]][] {
  const auto = groupByUnit(tags.filter((t) => !(assign[t.name] > 0)));
  const manual = new Map<number, T[]>();
  for (const t of tags) {
    const n = assign[t.name];
    if (n > 0) manual.set(n, [...(manual.get(n) ?? []), t]);
  }
  return [...auto, ...[...manual.entries()].sort((a, b) => a[0] - b[0]).map(([n, ts]): [string, T[]] => [`Graf ${n}`, ts])];
}

export type Divider = 'none' | 'hour' | 'day';

/**
 * Tidspunkter (sekunder) for hele timer eller dage (lokal tid) i [min, max] — til de stiplede skillelinjer i graferne.
 * Er der over MAX_DIVIDERS, tegnes ingen (linjerne ville blot blive en grå flade).
 */
export const MAX_DIVIDERS = 400;
export function dividerTimes(min: number, max: number, mode: Divider): number[] {
  if (mode === 'none' || !(max > min)) return [];
  const out: number[] = [];
  const d = new Date(min * 1000);
  if (mode === 'hour') d.setMinutes(0, 0, 0); else d.setHours(0, 0, 0, 0);
  while (d.getTime() / 1000 <= max) {
    const t = d.getTime() / 1000;
    if (t >= min) out.push(t);
    if (out.length > MAX_DIVIDERS) return [];
    if (mode === 'hour') d.setTime(d.getTime() + 3600_000); else d.setDate(d.getDate() + 1);
  }
  return out;
}

export const RANGES: { id: string; label: string; seconds: number }[] = [
  { id: '15m', label: '15 min', seconds: 900 },
  { id: '1h', label: '1 time', seconds: 3600 },
  { id: '8h', label: '8 timer', seconds: 8 * 3600 },
  { id: '24h', label: '24 timer', seconds: 86400 },
  { id: '7d', label: '7 dage', seconds: 7 * 86400 },
  { id: '30d', label: '30 dage', seconds: 30 * 86400 },
];

/**
 * Glidende middelværdi (bagudrettet): hvert punkt bliver gennemsnittet af de gyldige værdier de seneste `windowS` sekunder
 * (punkter med samme afstand, så de vægtes ens). Huller (null) tæller ikke med; et punkt uden en eneste gyldig værdi i vinduet forbliver et hul.
 * Min/max sættes til middelværdien, så kurven ikke viser spredning, der ikke længere hører til den.
 */
export function movingAverage(points: Point[], windowS: number): Point[] {
  if (windowS <= 0) return points;
  const out: Point[] = [];
  let lo = 0, sum = 0, n = 0;
  for (let i = 0; i < points.length; i++) {
    const v = points[i][1];
    if (v !== null) { sum += v; n++; }
    while (points[lo][0] <= points[i][0] - windowS) {
      const old = points[lo][1];
      if (old !== null) { sum -= old; n--; }
      lo++;
    }
    const m = n > 0 ? sum / n : null;
    out.push([points[i][0], m, m, m]);
  }
  return out;
}

/** Valg af middelværdi-tid (timer; 0 = ingen). */
export const AVERAGE_CHOICES: { hours: number; label: string }[] = [
  { hours: 0, label: 'Ingen' }, { hours: 0.25, label: '15 min' }, { hours: 1, label: '1 time' }, { hours: 8, label: '8 timer' },
  { hours: 24, label: '24 timer' }, { hours: 168, label: '7 dage' },
];
