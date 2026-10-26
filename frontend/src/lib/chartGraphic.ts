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
  /** Forklaringen med tagenes navne og værdier (v0.93.0) — mangler i grafer gemt før. */
  legend?: 'top' | 'bottom' | 'none';
  font_scale?: number;
  bold?: boolean;
  values?: boolean;
  /** Middelkurve (v1.21.0): glidende middelværdi over de seneste `avg_h` timer (0/mangler = ingen); `both` = stiplet ved siden af kurven, `avg` = i stedet. */
  avg_h?: number;
  avg_mode?: 'both' | 'avg';
}

export const LEGEND_PLACES: { id: 'top' | 'bottom' | 'none'; label: string }[] = [
  { id: 'top', label: 'over grafen' }, { id: 'bottom', label: 'under grafen' }, { id: 'none', label: 'skjult' },
];
export const FONT_SCALES: { v: number; label: string }[] = [
  { v: 0.8, label: 'lille' }, { v: 1, label: 'normal' }, { v: 1.3, label: 'stor' }, { v: 1.7, label: 'meget stor' },
];

/** Forklaringens opsætning med standardværdier (også for grafer gemt før v0.93.0). */
export const legendOf = (c: Partial<ChartCfg>) => ({
  place: c.legend ?? 'top', scale: c.font_scale ?? 1, bold: c.bold ?? true, values: c.values ?? true,
});

export const CHART_RANGES: { s: number; label: string }[] = [
  { s: 900, label: '15 min' }, { s: 3600, label: '1 time' }, { s: 8 * 3600, label: '8 timer' },
  { s: 86400, label: '24 timer' }, { s: 7 * 86400, label: '7 dage' },
];
export const MAX_CHART_TAGS = 4;

export const defaultChart = (): ChartCfg => ({ tags: [], range_s: 3600, style: 'line', bars: 24, y_min: null, y_max: null, title: '',
  legend: 'top', font_scale: 1, bold: true, values: true });

/**
 * Antal punkter at hente: én pr. søjle; en kurve får ét punkt pr. 2 enheder af plottets bredde (60–600) — en større
 * graf i tegningen får dermed en finere kurve (v0.95.0).
 */
export const chartPoints = (c: Pick<ChartCfg, 'style' | 'bars'>, plotW = 240): number =>
  c.style === 'bar' ? c.bars : Math.max(60, Math.min(600, Math.round(plotW / 2)));

/** Hvor ofte grafen hentes igen (sekunder): ét nyt punkt ad gangen, men mellem 5 og 60 s. */
export const refreshSeconds = (c: Pick<ChartCfg, 'style' | 'bars' | 'range_s'>, plotW = 240): number =>
  Math.max(5, Math.min(60, Math.round(c.range_s / chartPoints(c, plotW))));

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
  /** Skriftstørrelsen til akserne. */
  font: number;
  /** Forklaringen: skriftstørrelse og linjer (grundlinje + hvilke tags) — tom liste = skjult. */
  legendFont: number;
  legendLines: { y: number; items: number[] }[];
  /** Diagramlinjer med tekst: vandrette (værdier) og lodrette (tider). */
  yTicks: { y: number; label: string }[];
  xTicks: { x: number; label: string }[];
}

const r1 = (n: number) => Math.round(n * 10) / 10;

/** Skriftstørrelse efter grafens højde: vokser langsommere end grafen, så en større graf får mere plads til kurven. */
export const chartFont = (h: number): number => r1(Math.max(7, Math.min(28, 6 + 0.035 * h)));

/** Omtrentlig bredde af en tekst (proportional skrift, ~0,56 × skriftstørrelsen pr. tegn). */
export const textWidth = (s: string, font: number): number => s.length * font * 0.56;

/** Runde værdier til Y-aksen (1, 2, 2,5 eller 5 × 10^n), højst `max` stk., inden for [lo, hi]. */
export function niceTicks(lo: number, hi: number, max = 5): number[] {
  if (!(hi > lo)) return [lo];
  const raw = (hi - lo) / Math.max(1, max - 1);
  const p = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * p).find((s) => (hi - lo) / s <= max - 1 + 1e-9) ?? 10 * p;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step - 1e-9) * step; v <= hi + 1e-9; v += step) out.push(Math.round(v / step) * step);
  return out.map((v) => Math.round(v * 1e6) / 1e6 || 0);   // || 0: aldrig "-0"
}

/** Tidsinddelinger (sekunder) — runde tider i dansk tid (minutter, timer, døgn). */
const TIME_STEPS = [60, 120, 300, 600, 900, 1800, 3600, 7200, 10800, 21600, 43200, 86400, 2 * 86400];

/** Runde tidspunkter i [start, end] i lokal tid, højst `max` stk. `tzOffsetS`: lokal tid minus UTC (sekunder). */
export function timeTicks(start: number, end: number, max = 5, tzOffsetS = -new Date(start * 1000).getTimezoneOffset() * 60): number[] {
  const span = end - start;
  const step = TIME_STEPS.find((s) => span / s <= max) ?? TIME_STEPS[TIME_STEPS.length - 1];
  const out: number[] = [];
  for (let t = Math.ceil((start + tzOffsetS) / step) * step - tzOffsetS; t <= end; t += step) out.push(t);
  return out;
}

/**
 * Forklaringen fordelt på højst `maxLines` linjer inden for bredden; er det ikke nok, gøres skriften mindre (ned til 6) —
 * ved den mindste skrift må der blive flere linjer, men hver linje holder sig stadig inden for bredden.
 * → skriftstørrelse og linjerne som lister af tag-numre.
 */
export function wrapLegend(items: string[], font: number, maxW: number, maxLines = 2): { font: number; lines: number[][] } {
  let f = font;
  for (;;) {
    const gap = f * 0.9;
    const lines: number[][] = [];
    let cur: number[] = [], w = 0;
    items.forEach((s, i) => {
      const iw = textWidth(s, f);
      if (cur.length && w + gap + iw > maxW) { lines.push(cur); cur = []; w = 0; }
      w += (cur.length ? gap : 0) + iw;
      cur.push(i);
    });
    if (cur.length) lines.push(cur);
    const widest = Math.max(0, ...items.map((s) => textWidth(s, f)));
    if ((lines.length <= maxLines && widest <= maxW) || f <= 6) return { font: r1(f), lines };
    f = Math.max(6, f * 0.9);
  }
}

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

/** Geometrien inde i rammen `box` for tidsrummet [start, end]. `legend`: forklaringens tekst pr. tag. */
export function chartLayout(box: Box, series: Point[][], start: number, end: number, cfg: ChartCfg, legend: string[] = []): ChartLayout {
  const font = chartFont(box.h);
  const lg = legendOf(cfg);
  const pad = font * 0.5;
  const wrapped = lg.place === 'none' || !legend.length ? { font: r1(font * lg.scale), lines: [] as number[][] }
    : wrapLegend(legend, font * lg.scale, box.w - 2 * pad);
  const lf = wrapped.font;
  const legendH = wrapped.lines.length ? wrapped.lines.length * lf * 1.25 + lf * 0.35 : 0;
  const [yMin, yMax] = yRange(series, cfg);
  const yVals = niceTicks(yMin, yMax, Math.max(2, Math.min(8, Math.floor(box.h / (font * 3)))));
  const yLabels = yVals.map(axisNumber);
  const left = Math.max(...yLabels.map((s) => textWidth(s, font * 0.85)), font) + font * 0.7;
  const top = lg.place === 'top' ? legendH + font * 0.4 : font * 0.8;
  const bottom = font * 1.7 + (lg.place === 'bottom' ? legendH : 0);
  const plot: Box = { x: r1(box.x + left), y: r1(box.y + top), w: r1(Math.max(10, box.w - left - pad)), h: r1(Math.max(10, box.h - top - bottom)) };
  const legendTop = lg.place === 'top' ? box.y + lf * 1.05 : box.y + box.h - legendH + lf * 0.95;
  const legendLines = wrapped.lines.map((items, i) => ({ y: r1(legendTop + i * lf * 1.25), items }));
  const span = Math.max(1e-9, end - start);
  const X = (t: number) => r1(plot.x + ((Math.min(end, Math.max(start, t)) - start) / span) * plot.w);
  const Y = (v: number) => r1(plot.y + plot.h - ((Math.min(yMax, Math.max(yMin, v)) - yMin) / (yMax - yMin)) * plot.h);
  const yTicks = yVals.map((v, i) => ({ v, label: yLabels[i] })).filter((t) => t.v >= yMin && t.v <= yMax).map((t) => ({ y: Y(t.v), label: t.label }));
  // tider: så mange som der er plads til (en tekst er ca. 5-11 tegn bred)
  const room = Math.max(2, Math.min(8, Math.floor(plot.w / textWidth(cfg.range_s > 86400 ? '00/00 00:00' : '00:00', font * 0.85) / 1.6)));
  const xTicks = timeTicks(start, end, room).filter((t) => X(t) > plot.x + font && X(t) < plot.x + plot.w - font * 1.5)
    .map((t) => ({ x: X(t), label: axisTime(t, cfg.range_s) }));
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
  return { plot, yMin, yMax, lines, bars, font, legendFont: lf, legendLines, yTicks, xTicks };
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
