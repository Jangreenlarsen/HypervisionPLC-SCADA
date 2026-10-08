<script lang="ts">
  // Én graf pr. enhed (én y-akse). uPlot: hurtig og let — vigtigt på en Raspberry Pi.
  import { onDestroy, onMount } from 'svelte';
  import uPlot from 'uplot';
  import 'uplot/dist/uPlot.min.css';
  import { isolatedPoints, SERIES_COLORS } from './trendData';

  export interface ChartSeries { name: string; label: string; colorIndex: number; isBool: boolean; decimals: number | null }

  let { title, unit, series, data, xRange }: {
    title: string;
    unit: string;
    series: ChartSeries[];
    data: [number[], ...(number | null | undefined)[][]];
    /** Den valgte periode [start, slut] — x-aksen viser altid hele perioden, også hvor der ingen data er. */
    xRange: [number, number];
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

  function options(width: number): uPlot.Options {
    const isBool = series.every((s) => s.isBool);
    return {
      width,
      height: isBool ? 160 : 260,
      cursor: {
        sync: { key: 'trend' },
        drag: { x: true, y: false },
        // Dobbeltklik: tilbage til hele den valgte periode (uPlots egen udzoom går kun til dataenes yderpunkter)
        bind: { dblclick: () => () => { showFull(); return null; } },
      },
      hooks: {
        setScale: [(u: uPlot, key: string) => {
          if (key === 'x') zoomed = Math.abs((u.scales.x.min ?? 0) - full[0]) > 0.5 || Math.abs((u.scales.x.max ?? 0) - full[1]) > 0.5;
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
          stroke: SERIES_COLORS[s.colorIndex],
          width: 2,
          spanGaps: false, // null = rigtigt hul → brud i linjen
          // Kun prikker hvor en linje ikke kan tegnes (enkeltstående værdier)
          points: { show: true, size: 8, fill: SERIES_COLORS[s.colorIndex],
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

  function build(): void {
    chart?.destroy();
    chart = new uPlot(options(el.clientWidth || 600), data as uPlot.AlignedData, el);
    showFull();
  }

  onMount(() => {
    build();
    observer = new ResizeObserver(() => {
      chart?.setSize({ width: el.clientWidth, height: chart.height });
    });
    observer.observe(el);
  });

  // Ny data med samme serier → kun data opdateres (ingen genopbygning — hurtigt ved live-opdatering)
  let signature = '';
  let span = 0;
  $effect(() => {
    const sig = series.map((s) => `${s.name}:${s.colorIndex}`).join('|') + unit;
    void xRange; // ny periode → effekten skal også køre
    if (!chart) return;
    if (sig !== signature) {
      signature = sig;
      build();
    } else {
      chart.setData(data as uPlot.AlignedData, false);
      // Anden periodelængde valgt → zoom ud; samme periode (live-opdatering) → behold evt. zoom
      if (!zoomed || Math.abs(xRange[1] - xRange[0] - span) > 1) showFull();
    }
    span = xRange[1] - xRange[0];
  });

  onDestroy(() => {
    observer?.disconnect();
    chart?.destroy();
  });
</script>

<figure class="chart">
  <figcaption>{title}</figcaption>
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
  figcaption { font-weight: 600; font-size: .9rem; margin: 0 0 .25rem .25rem; }
  :global(.u-legend) { font-size: .85rem; }
</style>
