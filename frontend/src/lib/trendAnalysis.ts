// Analyse af trend-data (tilvalg): finder uregelmæssigheder i en tal-serie. Rene funktioner — testet i trendAnalysis.test.ts.
// Rådata ændres aldrig; `hideSpikes` returnerer en kopi hvor spikes er udfyldt ved interpolation.
import type { Point } from './trendData';

export type IssueKind = 'spike' | 'jump' | 'frozen' | 'gap';
export interface Issue { t: number; kind: IssueKind; note: string }

export const ISSUE_LABEL: Record<IssueKind, string> = {
  spike: 'Spike', jump: 'Urealistisk spring', frozen: 'Fastfrosset værdi', gap: 'Hul i data',
};
/** Kun enkeltstående spikes er sikre at fjerne; spring, fastfrosne værdier og huller markeres blot. */
export const HIDEABLE: IssueKind[] = ['spike'];

const MIN_POINTS = 8;
const FROZEN_RUN = 12;

const median = (v: number[]): number => {
  const s = [...v].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};
const quantile = (sorted: number[], q: number): number => sorted[Math.min(sorted.length - 1, Math.floor(q * (sorted.length - 1) + 0.5))];

/** Find uregelmæssigheder i én tal-serie (gennemsnitsværdierne). Til/fra-serier analyseres ikke. */
export function analyze(points: Point[]): Issue[] {
  const issues: Issue[] = [];

  // Huller: tidsafstand > 4 × den typiske afstand mellem punkter
  const dts: number[] = [];
  for (let i = 1; i < points.length; i++) dts.push(points[i][0] - points[i - 1][0]);
  if (dts.length >= MIN_POINTS) {
    const typical = median(dts);
    if (typical > 0) {
      for (let i = 1; i < points.length; i++) {
        const dt = points[i][0] - points[i - 1][0];
        if (dt > 4 * typical) issues.push({ t: points[i][0], kind: 'gap', note: `${Math.round(dt)} s uden data` });
      }
    }
  }

  // Resten arbejder på gyldige værdier
  const valid = points.filter((p): p is [number, number, number | null, number | null] => p[1] !== null && Number.isFinite(p[1]));
  if (valid.length < MIN_POINTS) return issues.sort((a, b) => a.t - b.t);
  const vs = valid.map((p) => p[1]);
  const sorted = [...vs].sort((a, b) => a - b);
  const spread = quantile(sorted, 0.95) - quantile(sorted, 0.05);
  if (!(spread > 0)) return issues.sort((a, b) => a.t - b.t);   // helt flad serie: intet at sammenligne med

  // Spikes: ét punkt langt fra sine naboer, mens punktet før og efter ligger tæt på hinanden
  const spikes = new Set<number>();
  for (let i = 1; i < vs.length - 1; i++) {
    const around = [...vs.slice(Math.max(0, i - 3), i), ...vs.slice(i + 1, i + 4)];
    const med = median(around);
    const mad = median(around.map((x) => Math.abs(x - med)));
    const thr = Math.max(6 * 1.4826 * mad, 0.2 * spread);
    if (Math.abs(vs[i] - med) > thr && Math.abs(vs[i - 1] - vs[i + 1]) <= thr / 2) {
      spikes.add(i);
      issues.push({ t: valid[i][0], kind: 'spike', note: `Værdi ${vs[i]} mod ca. ${Math.round(med * 1000) / 1000} omkring` });
    }
  }

  // Urealistiske spring: stort trin mellem to naboer, der IKKE er en spike (niveauet bliver ændret)
  for (let i = 1; i < vs.length; i++) {
    if (spikes.has(i) || spikes.has(i - 1)) continue;
    const d = Math.abs(vs[i] - vs[i - 1]);
    if (d > 0.6 * spread) issues.push({ t: valid[i][0], kind: 'jump', note: `Spring på ${Math.round(d * 1000) / 1000}` });
  }

  // Fastfrosne værdier: præcis samme værdi i mange punkter i træk, mens serien ellers varierer
  let run = 1;
  for (let i = 1; i <= vs.length; i++) {
    if (i < vs.length && vs[i] === vs[i - 1]) { run++; continue; }
    if (run >= FROZEN_RUN) issues.push({ t: valid[i - run][0], kind: 'frozen', note: `Uændret ${vs[i - 1]} i ${run} punkter` });
    run = 1;
  }

  return issues.sort((a, b) => a.t - b.t);
}

/** Kopi af serien hvor spikes er erstattet med lineært interpolerede værdier mellem nærmeste gode naboer — rådata er uændrede. */
export function hideSpikes(points: Point[], issues: Issue[]): Point[] {
  const bad = new Set(issues.filter((i) => HIDEABLE.includes(i.kind)).map((i) => i.t));
  if (!bad.size) return points;
  const good = (i: number): boolean => i >= 0 && i < points.length && !bad.has(points[i][0]) && points[i][1] !== null;
  return points.map((p, i): Point => {
    if (!bad.has(p[0])) return p;
    let a = i - 1; while (a >= 0 && !good(a)) a--;
    let b = i + 1; while (b < points.length && !good(b)) b++;
    const ga = good(a), gb = good(b);
    let v: number;
    if (ga && gb) {
      const pa = points[a], pb = points[b];
      v = (pa[1] as number) + ((pb[1] as number) - (pa[1] as number)) * ((p[0] - pa[0]) / (pb[0] - pa[0]));
    } else if (ga) v = points[a][1] as number;
    else if (gb) v = points[b][1] as number;
    else return [p[0], null, null, null];
    return [p[0], v, v, v];
  });
}
