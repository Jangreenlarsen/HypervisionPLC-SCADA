// Trendgraf i tegningen (v0.91.0): opsætning og geometri for en kurve eller et søjlediagram inde i symbolets ramme.
// Ren logik (testet i chartGraphic.test.ts) — Overview tegner SVG-elementerne ud fra resultatet.

export interface ChartCfg {
  tags: string[];
  range_s: number;
  style: 'line' | 'bar';
  bars: number;
  y_min: number | null;
  y_max: number | null;
  title: string;
}

export const CHART_RANGES: { s: number; label: string }[] = [
  { s: 900, label: '15 min' }, { s: 3600, label: '1 time' }, { s: 8 * 3600, label: '8 timer' },
  { s: 86400, label: '24 timer' }, { s: 7 * 86400, label: '7 dage' },
];
export const MAX_CHART_TAGS = 4;

export const defaultChart = (): ChartCfg => ({ tags: [], range_s: 3600, style: 'line', bars: 24, y_min: null, y_max: null, title: '' });

/** Antal punkter at hente: én pr. søjle, ellers nok til en jævn kurve. */
export const chartPoints = (c: Pick<ChartCfg, 'style' | 'bars'>): number => (c.style === 'bar' ? c.bars : 120);

/** Hvor ofte grafen hentes igen (sekunder): ét nyt punkt ad gangen, men mellem 5 og 60 s. */
export const refreshSeconds = (c: Pick<ChartCfg, 'style' | 'bars' | 'range_s'>): number =>
  Math.max(5, Math.min(60, Math.round(c.range_s / chartPoints(c))));

export interface Box { x: number; y: number; w: number; h: number }
/** Et punkt fra /api/trends/data: [tid, gennemsnit, min, max] — gennemsnittet er null i et hul. */
export type Point = [number, number | null, ...unknown[]];

export interface ChartLayout {
  plot: Box;
  yMin: number;
  yMax: number;
  /** Pr. serie: sammenhængende stykker (et hul afbryder kurven) som "x,y x,y …". */
  lines: string[][];
  /** Søjler: serie-nummer og rektangel. */
  bars: { series: number; x: number; y: number; w: number; h: number }[];
  font: number;
}

const r1 = (n: number) => Math.round(n * 10) / 10;

/** Y-aksen: den valgte, ellers fra data (søjler altid med 0); et fladt forløb får lidt luft. */
export function yRange(series: Point[][], cfg: Pick<ChartCfg, 'style' | 'y_min' | 'y_max'>): [number, number] {
  const vals = series.flat().map((p) => p[1]).filter((v): v is number => v !== null && Number.isFinite(v));
  let lo = cfg.y_min ?? (vals.length ? Math.min(...vals) : 0);
  let hi = cfg.y_max ?? (vals.length ? Math.max(...vals) : 1);
  if (cfg.style === 'bar') {
    if (cfg.y_min === null) lo = Math.min(lo, 0);
    if (cfg.y_max === null) hi = Math.max(hi, 0);
  }
  if (hi <= lo) {
    const pad = Math.abs(hi) * 0.1 || 1;
    if (cfg.y_min === null) lo -= pad;
    if (cfg.y_max === null || hi <= lo) hi = lo + 2 * pad;
  } else if (cfg.y_min === null || cfg.y_max === null) {
    const pad = (hi - lo) * 0.05;
    if (cfg.y_min === null && !(cfg.style === 'bar' && lo === 0)) lo -= pad;
    if (cfg.y_max === null) hi += pad;
  }
  return [lo, hi];
}

/** Geometrien inde i rammen `box` for tidsrummet [start, end]. */
export function chartLayout(box: Box, series: Point[][], start: number, end: number, cfg: ChartCfg): ChartLayout {
  const font = Math.max(6, Math.min(11, box.h / 11));
  // plads til titel/forklaring foroven, tal til venstre og tider forneden
  const plot: Box = { x: box.x + font * 3.2, y: box.y + font * 1.9, w: Math.max(10, box.w - font * 3.8), h: Math.max(10, box.h - font * 3.6) };
  const [yMin, yMax] = yRange(series, cfg);
  const span = Math.max(1e-9, end - start);
  const X = (t: number) => r1(plot.x + ((Math.min(end, Math.max(start, t)) - start) / span) * plot.w);
  const Y = (v: number) => r1(plot.y + plot.h - ((Math.min(yMax, Math.max(yMin, v)) - yMin) / (yMax - yMin)) * plot.h);
  const lines: string[][] = [];
  const bars: ChartLayout['bars'] = [];
  if (cfg.style === 'line') {
    for (const pts of series) {
      const parts: string[] = [];
      let cur: string[] = [];
      for (const p of pts) {
        if (p[1] === null || !Number.isFinite(p[1])) { if (cur.length) parts.push(cur.join(' ')); cur = []; continue; }
        cur.push(`${X(p[0])},${Y(p[1])}`);
      }
      if (cur.length) parts.push(cur.join(' '));
      lines.push(parts);
    }
  } else {
    const n = Math.max(1, series.length);
    const step = span / cfg.bars;
    const slot = plot.w / cfg.bars;
    const bw = (slot * 0.8) / n;
    const zero = Y(Math.min(yMax, Math.max(yMin, 0)));
    series.forEach((pts, s) => {
      for (const p of pts) {
        if (p[1] === null || !Number.isFinite(p[1]) || p[0] <= start) continue;   // første punkt er værdien FØR perioden
        const b = Math.min(cfg.bars - 1, Math.floor((p[0] - start) / step));
        const y = Y(p[1]);
        bars.push({ series: s, x: r1(plot.x + b * slot + slot * 0.1 + s * bw), y: Math.min(y, zero), w: r1(bw), h: r1(Math.max(0.5, Math.abs(zero - y))) });
      }
    });
  }
  return { plot, yMin, yMax, lines, bars, font: r1(font) };
}

/** Tal på Y-aksen: højst 3 betydende cifre efter kommaet, dansk komma. */
export function axisNumber(v: number): string {
  const a = Math.abs(v);
  const d = a >= 100 ? 0 : a >= 10 ? 1 : 2;
  return (Math.round(v * 10 ** d) / 10 ** d).toString().replace('.', ',');
}

/** Tidspunkt på X-aksen: klokkeslæt — med dato når perioden er over et døgn. */
export function axisTime(t: number, range_s: number): string {
  const d = new Date(t * 1000);
  const hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  return range_s > 86400 ? `${d.getDate()}/${d.getMonth() + 1} ${hm}` : hm;
}
