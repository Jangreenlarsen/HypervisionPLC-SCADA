<script lang="ts">
  // Én graf pr. enhed (én y-akse). uPlot: hurtig og let — vigtigt på en Raspberry Pi.
  import { onDestroy, onMount } from 'svelte';
  import uPlot from 'uplot';
  import 'uplot/dist/uPlot.min.css';
  import { colorOf, dashOf, dividerTimes, isolatedPoints, type Divider } from './trendData';
  import type { Issue } from './trendAnalysis';
  import { lastVisible, needsArrow, spreadLabels } from './lineLabels';

  export interface ChartSeries { name: string; label: string; colorIndex: number; isBool: boolean; decimals: number | null;
    /** Kunstige (interpolerede) tidspunkter — tegnes blinkende, så de ikke forveksles med målte data. */ synthetic?: Set<number>;
    /** Fundne uregelmæssigheder (tilvalg) — tegnes som ring om punktet. */ issues?: Issue[] }

  let { title, unit, series, data, xRange, height = 260, expanded = false, ondblclick, onclose, divider = 'none', linked = false, view = null, onview, resetTick = 0 }: {
    title: string;
    unit: string;
    series: ChartSeries[];
    data: [number[], ...(number | null | undefined)[][]];
    /** Den valgte periode [start, slut] — x-aksen viser altid hele perioden, også hvor der ingen data er. */
    xRange: [number, number];
    /** Plot-højde i px for tal-grafer (til/fra-grafer er altid lave) — sættes af siden ud fra skærmen. */
    height?: number;
    /** Fuld størrelse: også til/fra-grafer bruger `height`. */
    expanded?: boolean;
    /** Dobbeltklik på grafen (i stedet for at zoome ud — det gør *Nulstil visning*). */
    ondblclick?: () => void;
    /** Kryds i hjørnet: fjern grafen fra visningen. */
    onclose?: () => void;
    /** Stiplede skillelinjer ved hele timer eller dage. */
    divider?: Divider;
    /** Låst sammen: zoom/scroll i én graf flytter alle grafer til samme tidsudsnit. */
    linked?: boolean;
    /** Det fælles udsnit (når linked) — sættes af siden ud fra den graf brugeren sidst flyttede. */
    view?: [number, number] | null;
    onview?: (range: [number, number]) => void;
    /** Tælles op af siden for at nulstille visningen til hele perioden. */
    resetTick?: number;
  } = $props();

  let el: HTMLDivElement;
  let chart: uPlot | null = null;
  let observer: ResizeObserver | null = null;
  // Zoom aflæses af selve x-skalaen: afviger den fra den periode vi sidst viste, har brugeren zoomet.
  // (Et flag omkring vores egne kald virker ikke — uPlot kører sine hooks forsinket.)
  let full: [number, number] = [0, 0];
  let zoomed = false;

  const DA = {
    MMMM: ['januar', 'februar', 'marts', 'april', 'maj', 'juni', 'juli', 'august', 'september', 'oktober', 'november', 'december'],
    MMM: ['jan', 'feb', 'mar', 'apr', 'maj', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec'],
    WWWW: ['søndag', 'mandag', 'tirsdag', 'onsdag', 'torsdag', 'fredag', 'lørdag'],
    WWW: ['søn', 'man', 'tir', 'ons', 'tor', 'fre', 'lør'],
  };
  const fmtTooltip = uPlot.fmtDate('{DD}.{MM}.{YYYY} {HH}:{mm}:{ss}', DA);
  const fmtDay = uPlot.fmtDate('{DD}.{MM}', DA);
  const fmtDayYear = uPlot.fmtDate('{DD}.{MM}.{YYYY}', DA);
  const fmtMin = uPlot.fmtDate('{HH}:{mm}', DA);
  const fmtSec = uPlot.fmtDate('{HH}:{mm}:{ss}', DA);

  /** Dansk 24-timers tidsakse: dato vises ved første streg og når døgnet skifter. */
  function timeTicks(_u: uPlot, splits: number[], _ax: number, _space: number, incr: number): string[] {
    let lastDay = '';
    return splits.map((ts) => {
      const d = new Date(ts * 1000);
      const day = fmtDay(d);
      const time = incr >= 86400 ? '' : incr < 60 ? fmtSec(d) : fmtMin(d);
      const label = day !== lastDay ? (time ? `${day} ${time}` : day) : time;
      lastDay = day;
      return label;
    });
  }

  function format(v: number | null | undefined, s: ChartSeries): string {
    if (v === null || v === undefined) return '—';
    if (s.isBool) return v >= 0.5 ? 'Til' : 'Fra';
    return (s.decimals !== null ? v.toFixed(s.decimals) : String(Math.round(v * 1000) / 1000)) + (unit ? ` ${unit}` : '');
  }

  /** Stiplede lodrette linjer ved hele timer/dage — tegnes bag kurverne. */
  function drawDividers(u: uPlot): void {
    if (divider === 'none') return;
    const min = u.scales.x.min, max = u.scales.x.max;
    if (min == null || max == null) return;
    const { top, height: h } = u.bbox;
    const ctx = u.ctx, dpr = devicePixelRatio;
    ctx.save();
    ctx.strokeStyle = divider === 'day' ? '#6b6a66' : '#9a9993';
    ctx.lineWidth = (divider === 'day' ? 1.5 : 1) * dpr;
    ctx.setLineDash([5 * dpr, 4 * dpr]);
    ctx.beginPath();
    for (const t of dividerTimes(min, max, divider)) {
      const x = Math.round(u.valToPos(t, 'x', true)) + 0.5;
      ctx.moveTo(x, top); ctx.lineTo(x, top + h);
    }
    ctx.stroke();
    ctx.restore();
  }

  /** Dato ved hvert døgnskift (midnat) i det viste udsnit — altid, også uden skillelinjer. */
  function drawDayLabels(u: uPlot): void {
    const min = u.scales.x.min, max = u.scales.x.max;
    if (min == null || max == null) return;
    const days = dividerTimes(min, max, 'day');
    if (!days.length) return;
    const { left, top, width } = u.bbox;
    const ctx = u.ctx, dpr = devicePixelRatio;
    ctx.save();
    ctx.font = `600 ${11 * dpr}px system-ui, sans-serif`;
    ctx.textBaseline = 'top';
    ctx.textAlign = 'left';
    ctx.fillStyle = '#3b3a37';
    ctx.strokeStyle = '#3b3a37';
    ctx.lineWidth = 1.5 * dpr;
    let lastRight = -Infinity;
    for (const t of days) {
      const x = Math.round(u.valToPos(t, 'x', true));
      if (x < left || x > left + width) continue;
      const text = fmtDayYear(new Date(t * 1000));
      const w = ctx.measureText(text).width;
      if (x + 4 * dpr < lastRight) continue;   // ikke oven i forrige dato
      ctx.beginPath(); ctx.moveTo(x + 0.5, top); ctx.lineTo(x + 0.5, top + 14 * dpr); ctx.stroke();
      ctx.fillText(text, Math.min(x + 4 * dpr, left + width - w - 2 * dpr), top + 2 * dpr);
      lastRight = x + 4 * dpr + w + 6 * dpr;
    }
    ctx.restore();
  }

  // Blink: kunstige punkter skifter mellem synlige og skjulte
  let blinkOn = true;
  let blinkTimer: ReturnType<typeof setInterval> | null = null;
  const hasSynthetic = () => series.some((s) => s.synthetic && s.synthetic.size > 0);

  /** De interpolerede strækninger tegnes tykke og stiplede og blinker — det ses tydeligt, at de ikke er målt. */
  function drawFilled(u: uPlot): void {
    if (!hasSynthetic()) return;
    const xs = u.data[0] as number[];
    const ctx = u.ctx, dpr = devicePixelRatio;
    const { left, top, width, height: h } = u.bbox;
    ctx.save();
    ctx.beginPath(); ctx.rect(left, top, width, h); ctx.clip();
    ctx.lineCap = 'round';
    series.forEach((s, k) => {
      const syn = s.synthetic;
      if (!syn || !syn.size || s.isBool) return;
      const ys = u.data[k + 1] as (number | null | undefined)[];
      const scale = u.series[k + 1].scale ?? 'y';
      ctx.beginPath();
      let prev = -1;
      for (let i = 0; i < xs.length; i++) {
        const v = ys[i];
        if (v === undefined) continue;
        if (v !== null && prev >= 0 && ys[prev] !== null && (syn.has(xs[prev]) || syn.has(xs[i]))) {
          ctx.moveTo(u.valToPos(xs[prev], 'x', true), u.valToPos(ys[prev] as number, scale, true));
          ctx.lineTo(u.valToPos(xs[i], 'x', true), u.valToPos(v, scale, true));
        }
        prev = i;
      }
      if (blinkOn) {
        ctx.strokeStyle = colorOf(s.colorIndex); ctx.lineWidth = 3.5 * dpr; ctx.setLineDash([6 * dpr, 5 * dpr]);
      } else {
        ctx.strokeStyle = '#fcfcfb'; ctx.lineWidth = 5 * dpr; ctx.setLineDash([]);   // dækker linjen: strækningen forsvinder
      }
      ctx.stroke();
    });
    ctx.restore();
  }

  function syncBlink(): void {
    if (hasSynthetic() && !blinkTimer) {
      blinkTimer = setInterval(() => { blinkOn = !blinkOn; chart?.redraw(false); }, 700);
    } else if (!hasSynthetic() && blinkTimer) {
      clearInterval(blinkTimer); blinkTimer = null; blinkOn = true;
    }
  }

  /** Ring om punkter med uregelmæssigheder (spike, spring, fastfrosset, hul) — mørk ring, så den ses på alle farver. */
  function drawIssues(u: uPlot): void {
    const xs = u.data[0] as number[];
    const ctx = u.ctx;
    ctx.save();
    ctx.strokeStyle = '#1f1f1d';
    ctx.lineWidth = 2 * devicePixelRatio;
    series.forEach((s, k) => {
      const ys = u.data[k + 1] as (number | null | undefined)[];
      for (const issue of s.issues ?? []) {
        const i = xs.indexOf(issue.t);
        if (i < 0) continue;
        const x = Math.round(u.valToPos(issue.t, 'x', true));
        const v = ys[i];
        // Skjulte spikes har ingen værdi (hul) og tegnes ikke
        if (v === null || v === undefined) continue;
        const y = Math.round(u.valToPos(v, u.series[k + 1].scale ?? 'y', true));
        ctx.beginPath();
        if (issue.kind === 'gap') { ctx.moveTo(x, y - 9 * devicePixelRatio); ctx.lineTo(x, y + 9 * devicePixelRatio); }
        else ctx.arc(x, y, 7 * devicePixelRatio, 0, 2 * Math.PI);
        ctx.stroke();
      }
    });
    ctx.restore();
  }

  const LABEL_MAX = 150;   // px (CSS)
  let column = 0;          // bredden af navnekolonnen, sat når grafen bygges

  /** Pladsen til kurvenavnene ved højre kant: det længste navn, højst LABEL_MAX og en tredjedel af grafens bredde. */
  function labelColumn(width: number): number {
    const ctx = document.createElement('canvas').getContext('2d');
    if (!ctx) return 0;
    ctx.font = '12px system-ui, sans-serif';
    const longest = Math.max(0, ...series.map((s) => ctx.measureText(s.label).width));
    return Math.ceil(Math.min(LABEL_MAX, width / 3, longest + 22));
  }

  /** Kort tekst med "…" hvis den er for lang til kolonnen. */
  function fit(ctx: CanvasRenderingContext2D, text: string, maxW: number): string {
    if (ctx.measureText(text).width <= maxW) return text;
    let t = text;
    while (t.length > 1 && ctx.measureText(t + '…').width > maxW) t = t.slice(0, -1);
    return t + '…';
  }

  /**
   * Kurvenes navne ved højre kant, ud for kurvens sidste synlige punkt. Ligger kurverne så tæt, at navnene ville
   * overlappe, spredes de, og et navn der er flyttet væk fra sin kurve får en pil til kurvens punkt.
   */
  function drawLabels(u: uPlot): void {
    const xs = u.data[0] as number[];
    const dpr = devicePixelRatio;
    const { left, top, width, height: h } = u.bbox;
    const min = u.scales.x.min ?? -Infinity, max = u.scales.x.max ?? Infinity;
    const items: { s: ChartSeries; x: number; y: number }[] = [];
    series.forEach((s, k) => {
      const ys = u.data[k + 1] as (number | null | undefined)[];
      const i = lastVisible(xs, ys, min, max);
      if (i < 0) return;
      const y = u.valToPos(ys[i] as number, u.series[k + 1].scale ?? 'y', true);
      items.push({ s, x: u.valToPos(xs[i], 'x', true), y: Math.min(top + h, Math.max(top, y)) });
    });
    if (!items.length) return;
    const labelX = left + width + 10 * dpr;
    const textW = Math.max(20, column - 22) * dpr;
    const ly = spreadLabels(items.map((it) => it.y), top + 6 * dpr, top + h - 6 * dpr, 14 * dpr);
    const ctx = u.ctx;
    ctx.save();
    ctx.font = `${12 * dpr}px system-ui, sans-serif`;
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'left';   // uPlot lader aksernes højrejustering stå
    items.forEach((it, n) => {
      const color = colorOf(it.s.colorIndex), y = ly[n];
      if (needsArrow(it.y / dpr, y / dpr)) {
        // pil fra navnet til kurvens punkt (pilespidsen ved kurven)
        const fromX = labelX - 3 * dpr;
        ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 1.25 * dpr;
        ctx.beginPath(); ctx.moveTo(fromX, y); ctx.lineTo(it.x, it.y); ctx.stroke();
        const a = Math.atan2(it.y - y, it.x - fromX), sz = 6 * dpr;
        ctx.beginPath();
        ctx.moveTo(it.x, it.y);
        ctx.lineTo(it.x - sz * Math.cos(a - 0.45), it.y - sz * Math.sin(a - 0.45));
        ctx.lineTo(it.x - sz * Math.cos(a + 0.45), it.y - sz * Math.sin(a + 0.45));
        ctx.closePath();
        ctx.fill();
      }
      ctx.fillStyle = color;
      ctx.fillRect(labelX, y - 1.5 * dpr, 8 * dpr, 3 * dpr);   // farveprik, så navnet hører til kurven
      ctx.fillStyle = '#1f1f1d';
      ctx.fillText(fit(ctx, it.s.label, textW), labelX + 12 * dpr, y);
    });
    ctx.restore();
  }

  function options(width: number): uPlot.Options {
    const isBool = series.every((s) => s.isBool);
    return {
      width,
      height: isBool && !expanded ? 160 : height,
      padding: [null, (column = labelColumn(width)), null, null],   // plads til kurvenavnene ved højre kant
      cursor: {
        sync: { key: 'trend' },
        drag: { x: true, y: false },
        // Dobbeltklik: åbn/luk fuld størrelse (siden afgør det); udzoom til hele perioden sker med *Nulstil visning*
        bind: { dblclick: () => () => { if (ondblclick) ondblclick(); else showFull(); return null; } },
      },
      hooks: {
        drawAxes: [drawDividers],
        draw: [drawFilled, drawDayLabels, drawIssues, drawLabels],
        setScale: [(u: uPlot, key: string) => {
          if (key !== 'x') return;
          const lo = u.scales.x.min ?? 0, hi = u.scales.x.max ?? 0;
          zoomed = Math.abs(lo - full[0]) > 0.5 || Math.abs(hi - full[1]) > 0.5;
          if (linked) onview?.([lo, hi]);
        }],
      },
      legend: { live: true },
      scales: { x: { time: true }, y: isBool ? { range: [-0.1, 1.1] } : {} },
      axes: [
        { stroke: '#52514e', grid: { stroke: '#e5e4e0', width: 1 }, ticks: { stroke: '#d6d5d0' }, space: 80, values: timeTicks },
        {
          stroke: '#52514e',
          grid: { stroke: '#e5e4e0', width: 1 },
          ticks: { stroke: '#d6d5d0' },
          size: 56,
          ...(isBool ? { splits: () => [0, 1], values: (_: uPlot, v: number[]) => v.map((x) => (x >= 0.5 ? 'Til' : 'Fra')) } : {}),
        },
      ],
      series: [
        { label: 'Tid', value: (_u, v) => (v === null ? '—' : fmtTooltip(new Date(v * 1000))) },
        ...series.map((s) => ({
          label: s.label,
          stroke: colorOf(s.colorIndex),
          width: 2,
          dash: dashOf(s.colorIndex),
          spanGaps: false, // null = rigtigt hul → brud i linjen
          // Kun prikker hvor en linje ikke kan tegnes (enkeltstående værdier)
          points: { show: true, size: 8, fill: colorOf(s.colorIndex),
            filter: (u: uPlot, si: number) => isolatedPoints(u.data[si] as (number | null | undefined)[]) },
          paths: s.isBool ? uPlot.paths.stepped!({ align: 1 }) : undefined,
          value: (_u: uPlot, v: number | null) => format(v, s),
        })),
      ],
    };
  }

  function showFull(): void {
    if (!chart) return;
    full = [xRange[0], xRange[1]];
    zoomed = false;
    chart.setScale('x', { min: full[0], max: full[1] });
  }

  /** Flyt det zoomede udsnit (sekunder) uden at forlade den valgte periode. */
  function panBy(dt: number): void {
    if (!chart) return;
    const min = chart.scales.x.min ?? full[0], max = chart.scales.x.max ?? full[1];
    const span = max - min;
    const lo = Math.min(Math.max(min + dt, xRange[0]), Math.max(xRange[0], xRange[1] - span));
    chart.setScale('x', { min: lo, max: lo + span });
  }

  /** Scroll (hjul, eller træk med Shift nede) når der er zoomet ind. */
  function bindPan(over: HTMLElement): void {
    const secPerPx = () => {
      const u = chart!;
      return ((u.scales.x.max ?? 0) - (u.scales.x.min ?? 0)) / Math.max(1, over.clientWidth);
    };
    over.addEventListener('wheel', (e) => {
      if (!zoomed || !chart) return;
      e.preventDefault();
      const d = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
      panBy(Math.sign(d) * Math.min(Math.abs(d), 200) * secPerPx());
    }, { passive: false });
    over.addEventListener('mousedown', (e) => {
      if (!e.shiftKey || !zoomed || !chart) return;
      e.preventDefault();
      e.stopImmediatePropagation();   // ingen zoom-markering
      let lastX = e.clientX;
      const move = (m: MouseEvent) => { panBy(-(m.clientX - lastX) * secPerPx()); lastX = m.clientX; };
      const up = () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up); };
      window.addEventListener('mousemove', move);
      window.addEventListener('mouseup', up);
    }, true);
  }

  /** Bredden grafen skal have; 0 (beholderen er endnu ikke målt/vist) giver en usynlig graf, som først rettes ved næste ændring. */
  const widthNow = (): number => el.clientWidth || chart?.width || 600;

  /** Tilpas til beholderens faktiske størrelse, når layoutet er faldet på plads (grafer, der oprettes sammen med en ny visning, måles før de er lagt ud). */
  function settle(): void {
    requestAnimationFrame(() => {
      if (!chart || !el.clientWidth) return;
      if (Math.abs(chart.width - el.clientWidth) > 1) chart.setSize({ width: el.clientWidth, height: chart.height });
      chart.redraw();
    });
  }

  function build(): void {
    chart?.destroy();
    chart = new uPlot(options(widthNow()), data as uPlot.AlignedData, el);
    bindPan(chart.over);
    showFull();
    settle();
  }

  onMount(() => {
    build();
    observer = new ResizeObserver(() => {
      if (el.clientWidth) chart?.setSize({ width: el.clientWidth, height: chart.height });
    });
    observer.observe(el);
  });

  // Ny data med samme serier → kun data opdateres (ingen genopbygning — hurtigt ved live-opdatering)
  let signature = '';
  let span = 0;
  $effect(() => {
    const sig = series.map((s) => `${s.name}:${s.colorIndex}`).join('|') + unit;
    void series.map((s) => s.synthetic?.size);   // udfyldning slået til/fra → tegn om og start/stop blink
    syncBlink();
    void xRange; // ny periode → effekten skal også køre
    if (!chart) return;
    const wanted = series.every((s) => s.isBool) && !expanded ? 160 : height;
    if (chart.height !== wanted) chart.setSize({ width: widthNow(), height: wanted });
    if (sig !== signature) {
      signature = sig;
      build();
    } else {
      chart.setData(data as uPlot.AlignedData, false);
      // Anden periodelængde valgt → zoom ud; samme periode (live-opdatering) → behold evt. zoom
      if (!zoomed || Math.abs(xRange[1] - xRange[0] - span) > 1) showFull();
      settle();
    }
    span = xRange[1] - xRange[0];
  });

  // Låst sammen: følg det fælles udsnit fra den graf brugeren flyttede
  $effect(() => {
    const v = view;
    if (!chart || !linked || !v) return;
    const cur = chart.scales.x;
    if (Math.abs((cur.min ?? 0) - v[0]) > 0.5 || Math.abs((cur.max ?? 0) - v[1]) > 0.5) chart.setScale('x', { min: v[0], max: v[1] });
  });

  // Skift af skillelinjer: tegn om
  $effect(() => {
    void divider;
    chart?.redraw();
  });

  // Nulstil visning: hele den valgte periode
  let seenReset = 0;
  $effect(() => {
    const n = resetTick;
    if (!chart || n === seenReset) return;
    seenReset = n;
    showFull();
  });

  onDestroy(() => {
    if (blinkTimer) clearInterval(blinkTimer);
    observer?.disconnect();
    chart?.destroy();
  });
</script>

<figure class="chart">
  <figcaption {title}>{title}</figcaption>
  {#if onclose}<button class="x" onclick={onclose} title="Fjern grafen fra visningen" aria-label="Fjern grafen: {title}">×</button>{/if}
  <div bind:this={el}></div>
</figure>

<style>
  .chart {
    margin: 0 0 1rem;
    background: #fcfcfb;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    padding: .5rem .5rem .25rem;
  }
  .chart { position: relative; }
  .x { position: absolute; top: .2rem; right: .35rem; z-index: 5; width: 1.6rem; height: 1.6rem; padding: 0; border: 0; background: transparent; font-size: 1.3rem; line-height: 1; color: #52514e; cursor: pointer; border-radius: 4px; }
  .x:hover { background: #e5e4e0; color: #1f1f1d; }
  figcaption { padding-right: 2rem; font-weight: 600; font-size: .9rem; margin: 0 0 .25rem .25rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  :global(.u-legend) { font-size: .85rem; }
  /* Fast udtryk: aflæsningerne må ikke skifte bredde/højde, når markøren flyttes (ellers hopper legend og graf) */
  :global(.u-legend .u-series) { white-space: nowrap; }
  :global(.u-legend .u-series > th) { white-space: nowrap; }
  :global(.u-legend .u-value) {
    display: inline-block;
    min-width: 11ch;
    text-align: right;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  :global(.u-legend .u-series:first-child .u-value) { min-width: 19ch; }   /* tidsstempel: DD.MM.ÅÅÅÅ TT:mm:ss */
</style>
