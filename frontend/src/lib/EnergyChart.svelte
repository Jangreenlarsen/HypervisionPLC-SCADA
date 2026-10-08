<script lang="ts">
  // Grupperede søjler: én gruppe pr. periode, én søjle pr. tag (fast farve pr. tag som i Trends).
  import { fmtKwh, fmtTick, niceTicks } from './energyData';
  import { SERIES_COLORS } from './trendData';

  interface Bucket { label: string; current: boolean }
  let { buckets, series, height = 320 }: {
    buckets: Bucket[];
    series: { name: string; label: string; colorIndex: number; values: (number | null)[] }[];
    height?: number;
  } = $props();

  let width = $state(800);
  const PAD = { l: 56, r: 12, t: 12, b: 46 };
  const max = $derived(Math.max(0, ...series.flatMap((s) => s.values.map((v) => v ?? 0))));
  const ticks = $derived(niceTicks(max));
  const top = $derived(ticks[ticks.length - 1] || 1);
  const plotW = $derived(Math.max(10, width - PAD.l - PAD.r));
  const plotH = $derived(Math.max(10, height - PAD.t - PAD.b));
  const groupW = $derived(plotW / Math.max(1, buckets.length));
  const barW = $derived(Math.max(2, Math.min(28, (groupW * 0.8) / Math.max(1, series.length)) - 1));
  const y = (v: number) => PAD.t + plotH - (v / top) * plotH;
  // Vis højst ~12 etiketter på x-aksen
  const every = $derived(Math.max(1, Math.ceil(buckets.length / Math.max(1, Math.floor(plotW / 70)))));
</script>

<div class="chart" bind:clientWidth={width}>
  <svg {width} {height} role="img" aria-label="Energi pr. periode">
    {#each ticks as t}
      <line x1={PAD.l} x2={width - PAD.r} y1={y(t)} y2={y(t)} class="grid" />
      <text x={PAD.l - 6} y={y(t) + 4} class="axis" text-anchor="end">{fmtTick(t, ticks[1] - ticks[0])}</text>
    {/each}
    <text x={12} y={PAD.t + plotH / 2} class="axis" transform="rotate(-90 12 {PAD.t + plotH / 2})" text-anchor="middle">kWh</text>
    {#each buckets as b, i}
      {@const gx = PAD.l + i * groupW + (groupW - series.length * (barW + 1)) / 2}
      {#if b.current}<rect x={PAD.l + i * groupW} y={PAD.t} width={groupW} height={plotH} class="current" />{/if}
      {#each series as s, j}
        {@const v = s.values[i]}
        {#if v !== null && v !== undefined && v > 0}
          <rect x={gx + j * (barW + 1)} y={y(v)} width={barW} height={Math.max(1, PAD.t + plotH - y(v))}
            rx="2" fill={SERIES_COLORS[s.colorIndex]}>
            <title>{s.label} · {b.label}: {fmtKwh(v)} kWh{b.current ? ' (igangværende)' : ''}</title>
          </rect>
        {/if}
      {/each}
      {#if i % every === 0}
        <text x={PAD.l + (i + 0.5) * groupW} y={height - PAD.b + 18} class="axis" text-anchor="middle">{b.label}</text>
      {/if}
    {/each}
    <line x1={PAD.l} x2={width - PAD.r} y1={PAD.t + plotH} y2={PAD.t + plotH} class="base" />
  </svg>
</div>

<style>
  .chart { width: 100%; }
  svg { display: block; }
  .grid { stroke: #e5e4e0; }
  .base { stroke: #8a8984; }
  .axis { font-size: 11px; fill: #52514e; }
  .current { fill: #f2f1ec; }
</style>
