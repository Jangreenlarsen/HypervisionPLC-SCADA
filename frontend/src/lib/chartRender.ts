// Trendgraf i tegningen (v0.91.0): tegner grafen i symbolets ramme på Overview og henter historikken igen løbende.
// Geometrien kommer fra chartGraphic.ts (ren og testet); her er kun DOM og hentning.
// v0.95.0: grafen tegnes i tegningens egne koordinater (oven på symbolet) — ikke inde i symbolet — så den ikke blot
// forstørres eller strækkes, når symbolet skaleres: en større ramme giver flere punkter, flere diagramlinjer og mere tekst.
import { get } from './api';
import { axisNumber, axisTime, chartLayout, chartPoints, legendOf, refreshSeconds, type Box, type ChartCfg, type Point } from './chartGraphic';
import { SERIES_COLORS } from './trendData';

const NS = 'http://www.w3.org/2000/svg';

interface DataResp { start: number; end: number; series: Record<string, Point[]> }
type Meta = Record<string, { description?: string; unit?: string }>;

function el(tag: string, attrs: Record<string, string | number>, text?: string): SVGElement {
  const e = document.createElementNS(NS, tag) as SVGElement;
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
  if (text !== undefined) e.textContent = text;
  return e;
}

/** Sidste gyldige værdi i en serie (til forklaringen). */
const latest = (pts: Point[]): number | null => {
  for (let i = pts.length - 1; i >= 0; i--) if (pts[i][1] !== null && Number.isFinite(pts[i][1])) return pts[i][1];
  return null;
};

/** Rammens boks i tegningens (rodens) koordinater — med symbolets egen flytning, skalering og drejning. */
function boxInRoot(root: SVGSVGElement, frame: SVGGraphicsElement): Box | null {
  const b = frame.getBBox();
  const rm = root.getScreenCTM(), fm = frame.getScreenCTM();
  if (!rm || !fm) return null;
  const m = rm.inverse().multiply(fm);
  const pts = [[b.x, b.y], [b.x + b.width, b.y], [b.x, b.y + b.height], [b.x + b.width, b.y + b.height]]
    .map(([x, y]) => new DOMPoint(x, y).matrixTransform(m));
  const xs = pts.map((q) => q.x), ys = pts.map((q) => q.y);
  return { x: Math.min(...xs), y: Math.min(...ys), w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) };
}

/**
 * Tegn graferne for tegningens symboler med en `chart`-opsætning. → stop-funktion (stopper opdateringen og fjerner dem).
 * Fejl ved hentning vises i grafen (serverens tekst), ikke som en fejl på hele siden.
 */
export function mountCharts(root: SVGSVGElement | null, symbols: Record<string, { chart?: ChartCfg | null }>, meta: Meta): () => void {
  const stops: (() => void)[] = [];
  if (!root) return () => {};
  for (const [element, s] of Object.entries(symbols)) {
    const cfg = s.chart;
    if (!cfg || !cfg.tags.length) continue;
    const sym = root.querySelector(`#${CSS.escape(element)}`) as SVGGraphicsElement | null;
    if (!sym) continue;
    const frame = (sym.querySelector('[data-hv-pid="ramme"]') ?? sym.querySelector('rect') ?? sym) as SVGGraphicsElement;
    let found: Box | null;
    try {
      found = boxInRoot(root, frame);
    } catch {
      found = null;   // ikke synlig (fx skjult lag) — intet at tegne i
    }
    if (!found || found.w < 20 || found.h < 20) continue;
    const box = found;
    sym.querySelectorAll('[data-hv-pid="eksempel"],[data-hv-pid="titel"]').forEach((n) => ((n as SVGElement).style.display = 'none'));
    stops.push(mountChartIn(root, box, cfg, meta, element));

  }
  return () => stops.forEach((stop) => stop());
}

/**
 * Tegn ÉN graf i `box` (rodens koordinater) og hent historikken løbende (v1.15.0: også brugt af den store visning, ChartBig.svelte).
 * En større boks giver flere punkter, diagramlinjer og tekst — grafen strækkes ikke. → stop-funktion.
 */
export function mountChartIn(root: SVGSVGElement, box: Box, cfg: ChartCfg, meta: Meta, element = ''): () => void {
  let stopped = false;
  const timers: ReturnType<typeof setInterval>[] = [];
    const g = el('g', { class: 'hv-chart', 'pointer-events': 'none', 'data-hv-chart': element });
    root.appendChild(g);

    const label = (t: string) => meta[t]?.description || t;
    const lg = legendOf(cfg);
    const legendText = (series: Point[][]) => cfg.tags.map((t, i) => {
      const v = latest(series[i] ?? []);
      const unit = meta[t]?.unit ? ` ${meta[t]!.unit}` : '';
      const name = cfg.title && cfg.tags.length === 1 ? '' : label(t);
      const value = lg.values ? (v === null ? '—' : axisNumber(v) + unit) : '';
      return [i === 0 && cfg.title ? cfg.title : '', name, value].filter(Boolean).join(' ') || label(t);
    });

    const render = (data: DataResp | null, message = '') => {
      if (stopped) return;
      g.replaceChildren();
      const series = cfg.tags.map((t) => data?.series[t] ?? []);
      const start = data?.start ?? Date.now() / 1000 - cfg.range_s, end = data?.end ?? Date.now() / 1000;
      const texts = legendText(series);
      const l = chartLayout(box, series, start, end, cfg, texts);
      const f = l.font, p = l.plot;
      const small = { 'font-size': f * 0.85, fill: '#555' };
      const grid = { stroke: '#000', 'stroke-opacity': 0.12, 'stroke-width': Math.max(0.5, f / 12) };
      // diagramlinjer: vandrette ved runde værdier, lodrette ved runde tider
      for (const t of l.yTicks) {
        g.appendChild(el('line', { x1: p.x, y1: t.y, x2: p.x + p.w, y2: t.y, ...grid }));
        g.appendChild(el('text', { x: p.x - f * 0.35, y: t.y + f * 0.3, 'text-anchor': 'end', ...small }, t.label));
      }
      for (const t of l.xTicks) {
        g.appendChild(el('line', { x1: t.x, y1: p.y, x2: t.x, y2: p.y + p.h, ...grid }));
        g.appendChild(el('text', { x: t.x, y: p.y + p.h + f * 1.1, 'text-anchor': 'middle', ...small }, t.label));
      }
      g.appendChild(el('path', { d: `M${p.x} ${p.y} V${p.y + p.h} H${p.x + p.w}`, fill: 'none', stroke: '#9a9a9a', 'stroke-width': Math.max(0.8, f / 9) }));
      g.appendChild(el('text', { x: p.x + p.w, y: p.y + p.h + f * 1.1, 'text-anchor': 'end', ...small }, 'nu'));
      if (!l.xTicks.length) g.appendChild(el('text', { x: p.x, y: p.y + p.h + f * 1.1, 'text-anchor': 'start', ...small }, axisTime(start, cfg.range_s)));
      // data
      const sw = Math.max(1, f / 5);
      l.lines.forEach((parts, i) => parts.forEach((pts) => {
        g.appendChild(el(pts.includes(' ') ? 'polyline' : 'circle', pts.includes(' ')
          ? { points: pts, fill: 'none', stroke: SERIES_COLORS[i % SERIES_COLORS.length], 'stroke-width': sw, 'stroke-linejoin': 'round' }
          : { cx: pts.split(',')[0], cy: pts.split(',')[1], r: sw, fill: SERIES_COLORS[i % SERIES_COLORS.length] }));
      }));
      for (const b of l.bars) g.appendChild(el('rect', { x: b.x, y: b.y, width: b.w, height: b.h, fill: SERIES_COLORS[b.series % SERIES_COLORS.length] }));
      // forklaringen: hvert tag i sin farve, på højst to linjer inden for rammen
      for (const line of l.legendLines) {
        const t = el('text', { x: box.x + box.w / 2, y: line.y, 'text-anchor': 'middle', 'font-size': l.legendFont, 'font-weight': lg.bold ? 600 : 400, fill: '#333' });
        line.items.forEach((i, k) => t.appendChild(el('tspan', { fill: SERIES_COLORS[i % SERIES_COLORS.length], ...(k ? { dx: l.legendFont * 0.9 } : {}) }, texts[i])));
        g.appendChild(t);
      }
      const empty = !series.some((s2) => s2.some((pt) => pt[1] !== null));
      if (message || empty) {
        g.appendChild(el('text', { x: p.x + p.w / 2, y: p.y + p.h / 2, 'text-anchor': 'middle', 'font-size': f * 0.9, fill: message ? '#c62828' : '#777' },
          message || 'Ingen historik i perioden'));
      }
    };
    const plotW = chartLayout(box, [], 0, 1, cfg, legendText([])).plot.w;
    const load = async () => {
      const end = Date.now() / 1000, start = end - cfg.range_s;
      try {
        const data = await get<DataResp>(`/api/trends/data?tags=${cfg.tags.map(encodeURIComponent).join(',')}` +
          `&start=${start}&end=${end}&points=${chartPoints(cfg, plotW)}`);
        render(data);
      } catch (e) {
        render(null, (e as Error).message);   // fx ingen adgang til tagget, eller serveren svarer ikke
      }
    };
    render(null);
    void load();
    timers.push(setInterval(load, refreshSeconds(cfg, plotW) * 1000));
  return () => {
    stopped = true;
    timers.forEach(clearInterval);
    g.remove();
  };
}
