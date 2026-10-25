<script lang="ts">
  // Trendgraf i stor udgave (v1.15.0): et tryk på et trend-symbol på Overview viser grafen stort, med valg af periode og en knap
  // tilbage til tegningen (også Esc og klik udenfor). Grafen tegnes af samme kode som i tegningen (chartRender.mountChartIn).
  import { onDestroy, onMount } from 'svelte';
  import { CHART_RANGES, type ChartCfg } from './chartGraphic';
  import { mountChartIn } from './chartRender';

  let { cfg, meta, title, onclose }: {
    cfg: ChartCfg; meta: Record<string, { description?: string; unit?: string }>; title: string; onclose: () => void;
  } = $props();

  let range = $state(0);
  let svg: SVGSVGElement | null = $state(null);
  let holder: HTMLDivElement | null = $state(null);
  let size = $state({ w: 1000, h: 560 });
  let stop: (() => void) | null = null;

  function draw(): void {
    stop?.();
    stop = null;
    if (!svg) return;
    stop = mountChartIn(svg, { x: 0, y: 0, w: size.w, h: size.h }, { ...cfg, range_s: range || cfg.range_s }, meta, 'stor');
  }
  onMount(() => {
    range = cfg.range_s;
    const r = holder?.getBoundingClientRect();
    if (r && r.width > 100 && r.height > 100) size = { w: Math.round(r.width), h: Math.round(r.height) };
    queueMicrotask(draw);
  });
  onDestroy(() => stop?.());
  function setRange(s: number): void { range = s; draw(); }
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && onclose()} />

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={onclose}>
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="panel big" role="dialog" aria-modal="true" aria-label={title} tabindex="-1" onclick={(e) => e.stopPropagation()}>
    <header class="row head">
      <button class="primary" onclick={onclose}>← Tilbage til tegningen</button>
      <h2>{title}</h2>
      <span class="spacer"></span>
      <span class="row ranges" role="group" aria-label="Periode">
        {#each CHART_RANGES as r (r.s)}
          <button class="small" class:active={range === r.s} aria-pressed={range === r.s} onclick={() => setRange(r.s)}>{r.label}</button>
        {/each}
      </span>
    </header>
    <div class="holder" bind:this={holder}>
      <svg bind:this={svg} viewBox="0 0 {size.w} {size.h}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Trendgraf {title}"></svg>
    </div>
    <p class="small muted">Grafen opdateres af sig selv. Esc eller et klik uden for vinduet går også tilbage til tegningen.</p>
  </div>
</div>

<style>
  .backdrop { position: fixed; inset: 0; background: rgba(0, 0, 0, .45); display: flex; align-items: center; justify-content: center; padding: 2vh 16px; z-index: 50; }
  .big { width: min(1200px, 96vw); height: min(780px, 92vh); display: flex; flex-direction: column; box-shadow: 0 8px 30px rgba(0, 0, 0, .3); }
  .head { gap: .6rem; align-items: center; flex-wrap: wrap; }
  .head h2 { margin: 0; font-size: 1.15rem; }
  .spacer { flex: 1; }
  .ranges { gap: .25rem; }
  .ranges button.active { background: var(--accent); color: #fff; border-color: var(--accent); }
  .holder { flex: 1; min-height: 200px; margin: .5rem 0; background: #fff; border: 1px solid var(--line); border-radius: var(--radius); }
  .holder svg { width: 100%; height: 100%; display: block; }
</style>
