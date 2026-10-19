// Trendgraf i tegningen (v0.91.0): tegner grafen inde i symbolets ramme på Overview og henter historikken igen løbende.
// Geometrien kommer fra chartGraphic.ts (ren og testet); her er kun DOM og hentning.
import { get } from './api';
import { axisNumber, axisTime, chartLayout, chartPoints, legendOf, refreshSeconds, type ChartCfg, type Point } from './chartGraphic';
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

/**
 * Tegn graferne for tegningens symboler med en `chart`-opsætning. → stop-funktion (stopper opdateringen).
 * Fejl ved hentning vises i grafen (serverens tekst), ikke som en fejl på hele siden.
 */
export function mountCharts(root: SVGSVGElement | null, symbols: Record<string, { chart?: ChartCfg | null }>, meta: Meta): () => void {
  const timers: ReturnType<typeof setInterval>[] = [];
  let stopped = false;
  if (!root) return () => {};
  for (const [element, s] of Object.entries(symbols)) {
    const cfg = s.chart;
    if (!cfg || !cfg.tags.length) continue;
    const sym = root.querySelector(`#${CSS.escape(element)}`) as SVGGraphicsElement | null;
    if (!sym) continue;
    const frame = (sym.querySelector('[data-hv-pid="ramme"]') ?? sym.querySelector('rect') ?? sym) as SVGGraphicsElement;
    let box: { x: number; y: number; w: number; h: number };
    try {
      const b = frame.getBBox();
      box = { x: b.x, y: b.y, w: b.width, h: b.height };
    } catch {
      continue;   // ikke synlig (fx skjult lag) — intet at tegne i
    }
    if (box.w < 20 || box.h < 20) continue;
    sym.querySelectorAll('[data-hv-pid="eksempel"],[data-hv-pid="titel"]').forEach((n) => ((n as SVGElement).style.display = 'none'));
    const g = el('g', { class: 'hv-chart', 'pointer-events': 'none' });
    (frame === sym ? sym : frame.parentNode ?? sym).appendChild(g);

    const label = (t: string) => meta[t]?.description || t;
    const render = (data: DataResp | null, message = '') => {
      if (stopped) return;
      g.replaceChildren();
      const series = cfg.tags.map((t) => data?.series[t] ?? []);
      const start = data?.start ?? Date.now() / 1000 - cfg.range_s, end = data?.end ?? Date.now() / 1000;
      const l = chartLayout(box, series, start, end, cfg);
      const f = l.font, p = l.plot;
      // titel / forklaring: hvert tag i sin farve (evt. med seneste værdi) — over, under eller skjult (v0.93.0)
      const lg = legendOf(cfg);
      if (l.legendY !== null) {
        const lf = l.legendFont;
        const title = el('text', { x: box.x + box.w / 2, y: l.legendY, 'text-anchor': 'middle', 'font-size': lf, 'font-weight': lg.bold ? 600 : 400, fill: '#333' });
        if (cfg.title) title.appendChild(el('tspan', {}, cfg.title));
        cfg.tags.forEach((t, i) => {
          const v = latest(series[i]);
          const unit = meta[t]?.unit ? ` ${meta[t]!.unit}` : '';
          const name = cfg.title && cfg.tags.length === 1 ? '' : label(t);
          const value = lg.values ? (v === null ? '—' : axisNumber(v) + unit) : '';
          // mellemrum med dx — SVG slår flere mellemrum sammen til ét
          title.appendChild(el('tspan', { fill: SERIES_COLORS[i % SERIES_COLORS.length], ...(i || cfg.title ? { dx: lf * 0.9 } : {}) },
            [name, value].filter(Boolean).join(' ') || label(t)));
        });
        g.appendChild(title);
      }
      // akser
      g.appendChild(el('path', { d: `M${p.x} ${p.y} V${p.y + p.h} H${p.x + p.w}`, fill: 'none', stroke: '#9a9a9a', 'stroke-width': 1 }));
      const small = { 'font-size': f * 0.85, fill: '#555' };
      g.appendChild(el('text', { x: p.x - 2, y: p.y + f * 0.6, 'text-anchor': 'end', ...small }, axisNumber(l.yMax)));
      g.appendChild(el('text', { x: p.x - 2, y: p.y + p.h, 'text-anchor': 'end', ...small }, axisNumber(l.yMin)));
      g.appendChild(el('text', { x: p.x, y: p.y + p.h + f * 1.1, 'text-anchor': 'start', ...small }, axisTime(start, cfg.range_s)));
      g.appendChild(el('text', { x: p.x + p.w, y: p.y + p.h + f * 1.1, 'text-anchor': 'end', ...small }, 'nu'));
      // data
      l.lines.forEach((parts, i) => parts.forEach((pts) => {
        g.appendChild(el(pts.includes(' ') ? 'polyline' : 'circle', pts.includes(' ')
          ? { points: pts, fill: 'none', stroke: SERIES_COLORS[i % SERIES_COLORS.length], 'stroke-width': Math.max(1, f / 5), 'stroke-linejoin': 'round' }
          : { cx: pts.split(',')[0], cy: pts.split(',')[1], r: Math.max(1, f / 5), fill: SERIES_COLORS[i % SERIES_COLORS.length] }));
      }));
      for (const b of l.bars) g.appendChild(el('rect', { x: b.x, y: b.y, width: b.w, height: b.h, fill: SERIES_COLORS[b.series % SERIES_COLORS.length] }));
      const empty = !series.some((s2) => s2.some((pt) => pt[1] !== null));
      if (message || empty) {
        g.appendChild(el('text', { x: p.x + p.w / 2, y: p.y + p.h / 2, 'text-anchor': 'middle', 'font-size': f * 0.9, fill: message ? '#c62828' : '#777' },
          message || 'Ingen historik i perioden'));
      }
    };
    const load = async () => {
      const end = Date.now() / 1000, start = end - cfg.range_s;
      try {
        const data = await get<DataResp>(`/api/trends/data?tags=${cfg.tags.map(encodeURIComponent).join(',')}` +
          `&start=${start}&end=${end}&points=${chartPoints(cfg)}`);
        render(data);
      } catch (e) {
        render(null, (e as Error).message);   // fx ingen adgang til tagget, eller serveren svarer ikke
      }
    };
    render(null);
    void load();
    timers.push(setInterval(load, refreshSeconds(cfg) * 1000));
  }
  return () => {
    stopped = true;
    timers.forEach(clearInterval);
  };
}
