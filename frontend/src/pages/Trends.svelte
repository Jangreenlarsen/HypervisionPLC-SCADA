<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { get, patch } from '../lib/api';
  import TrendChart, { type ChartSeries } from '../lib/TrendChart.svelte';
  import { align, assignColors, groupByUnit, MAX_SERIES, RANGES, SERIES_COLORS, type Point } from '../lib/trendData';

  let { canEdit = false }: { canEdit?: boolean } = $props();

  interface InfoTag { name: string; unit: string; description: string; plc: string; trend: boolean;
    trend_interval_s: number; samples: number; oldest: number | null; is_bool: boolean }
  interface Info { retention_days: number; db_size: number; tags: InfoTag[] }
  interface DataResp { start: number; end: number; series: Record<string, Point[]>;
    meta: Record<string, { unit: string; description: string; decimals: number | null }> }

  let info = $state<Info | null>(null);
  let selected = $state<string[]>(loadSelection());
  let colors = $state<Record<string, number>>({});
  let range = $state('1h');
  let customFrom = $state('');
  let customTo = $state('');
  let live = $state(true);
  let filter = $state('');
  let error = $state('');
  let loading = $state(false);
  let resp = $state<DataResp | null>(null);
  let timer: ReturnType<typeof setInterval> | null = null;
  let enabling = $state('');

  function loadSelection(): string[] {
    try {
      return JSON.parse(localStorage.getItem('trend.selected') ?? '[]');
    } catch {
      return []; // privat vindue / blokeret lager — start blot uden valg
    }
  }

  function saveSelection(): void {
    try {
      localStorage.setItem('trend.selected', JSON.stringify(selected));
    } catch {
      // Valget huskes bare ikke — ingen funktionalitet afhænger af det.
    }
  }

  function period(): { start: number; end: number } {
    if (range === 'custom') {
      const start = Date.parse(customFrom) / 1000;
      const end = Date.parse(customTo) / 1000;
      if (!Number.isFinite(start) || !Number.isFinite(end)) throw new Error('Vælg både fra- og til-tidspunkt');
      return { start, end };
    }
    const r = RANGES.find((x) => x.id === range)!;
    const end = Date.now() / 1000;
    return { start: end - r.seconds, end };
  }

  async function load(): Promise<void> {
    if (!selected.length) {
      resp = null;
      return;
    }
    error = '';
    loading = true;
    try {
      const { start, end } = period();
      const width = Math.min(1600, Math.max(300, window.innerWidth - 100));
      resp = await get<DataResp>(`/api/trends/data?tags=${selected.map(encodeURIComponent).join(',')}` +
        `&start=${start}&end=${end}&points=${Math.round(width / 2)}`);
    } catch (e) {
      error = (e as Error).message;
    } finally {
      loading = false;
    }
  }

  function toggle(name: string): void {
    if (selected.includes(name)) selected = selected.filter((n) => n !== name);
    else if (selected.length >= MAX_SERIES) {
      error = `Højst ${MAX_SERIES} tags ad gangen — fravælg et først`;
      return;
    } else selected = [...selected, name];
    colors = assignColors(selected, colors);
    saveSelection();
    load();
  }

  function setRange(id: string): void {
    range = id;
    if (id === 'custom') {
      const now = new Date();
      const pad = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
      customTo ||= pad(now);
      customFrom ||= pad(new Date(now.getTime() - 86400000));
      live = false;
    }
    restartTimer();
    load();
  }

  function restartTimer(): void {
    if (timer) clearInterval(timer);
    timer = null;
    const r = RANGES.find((x) => x.id === range);
    // Live-opdatering kun for korte perioder — lange perioder ændrer sig ikke synligt på 5 s
    if (live && r && r.seconds <= 86400) timer = setInterval(load, 5000);
  }

  /** Tekniker/admin: slå historik til direkte herfra og vælg tagget — kurven fyldes op fra nu af. */
  async function enableTrend(t: InfoTag): Promise<void> {
    error = '';
    enabling = t.name;
    try {
      await patch(`/api/tags/${encodeURIComponent(t.name)}`, { trend: true });
      t.trend = true;
      if (!selected.includes(t.name)) toggle(t.name);
    } catch (e) {
      error = (e as Error).message;
    } finally {
      enabling = '';
    }
  }

  const noHistory = $derived(!!info && info.tags.length > 0 && !info.tags.some((t) => t.trend || t.samples));

  const exportUrl = $derived.by(() => {
    try {
      const { start, end } = period();
      return `/api/trends/export?tags=${selected.map(encodeURIComponent).join(',')}&start=${start}&end=${end}`;
    } catch {
      return '';
    }
  });

  const tagInfo = $derived(new Map((info?.tags ?? []).map((t) => [t.name, t])));
  const groups = $derived(groupByUnit(selected.filter((n) => tagInfo.has(n)).map((n) => ({
    name: n, unit: tagInfo.get(n)!.unit, isBool: tagInfo.get(n)!.is_bool,
  }))));
  const shown = $derived((info?.tags ?? []).filter((t) => !filter || `${t.name} ${t.description}`.toLowerCase().includes(filter.toLowerCase())));

  function chartFor(names: { name: string; isBool?: boolean }[]): { series: ChartSeries[]; data: ReturnType<typeof align> } {
    const series = names.map((t) => ({
      name: t.name,
      label: tagInfo.get(t.name)?.description || t.name,
      colorIndex: colors[t.name] ?? 0,
      isBool: Boolean(t.isBool),
      decimals: resp?.meta[t.name]?.decimals ?? null,
    }));
    return { series, data: align(names.map((t) => resp?.series[t.name] ?? []), names.map((t) => Boolean(t.isBool))) };
  }

  onMount(async () => {
    try {
      info = await get<Info>('/api/trends/info');
      selected = selected.filter((n) => info!.tags.some((t) => t.name === n));
      colors = assignColors(selected, {});
    } catch (e) {
      error = (e as Error).message;
    }
    restartTimer();
    load();
  });
  onDestroy(() => timer && clearInterval(timer));
</script>

<div class="row toolbar">
  {#each RANGES as r}
    <button class:primary={range === r.id} onclick={() => setRange(r.id)}>{r.label}</button>
  {/each}
  <button class:primary={range === 'custom'} onclick={() => setRange('custom')}>Vælg periode</button>
  {#if range === 'custom'}
    <input type="datetime-local" bind:value={customFrom} onchange={load} aria-label="Fra" />
    <input type="datetime-local" bind:value={customTo} onchange={load} aria-label="Til" />
  {:else}
    <label class="row small"><input type="checkbox" bind:checked={live} onchange={restartTimer} /> Live</label>
  {/if}
  {#if selected.length && exportUrl}<a class="btn" href={exportUrl} download>CSV</a>{/if}
  {#if loading}<span class="muted small">Henter …</span>{/if}
</div>

{#if error}<div class="error">{error}</div>{/if}

<div class="layout">
  <aside class="panel">
    <h3>Tags</h3>
    <input bind:value={filter} placeholder="Søg" style="width:100%" />
    <ul>
      {#each shown as t (t.name)}
        <li>
          <label class:off={!t.trend && !t.samples} title={!t.trend ? 'Historik er ikke slået til for dette tag' : ''}>
            <input type="checkbox" checked={selected.includes(t.name)} disabled={!t.trend && !t.samples} onchange={() => toggle(t.name)} />
            {#if selected.includes(t.name)}<span class="swatch" style="background:{SERIES_COLORS[colors[t.name] ?? 0]}"></span>{/if}
            <span class="name">{t.description || t.name}</span>
            <span class="muted small">{t.unit}</span>
          </label>
          {#if !t.trend && !t.samples && canEdit}
            <button class="small enable" disabled={enabling === t.name} onclick={() => enableTrend(t)}
              title="Begynd at gemme historik for {t.name}">Gem historik</button>
          {/if}
        </li>
      {/each}
    </ul>
    {#if info}
      <p class="muted small">
        Historik gemmes i {info.retention_days} dage · {Math.round(info.db_size / 1024 / 1024 * 10) / 10} MB.
        {#if canEdit}Slå historik til pr. tag under <a href="#tags">Tags</a>.{/if}
      </p>
    {/if}
  </aside>

  <section class="charts">
    {#if noHistory}
      <div class="panel notice">
        <strong>Ingen tags gemmer historik endnu</strong> — derfor er de grå.
        {#if canEdit}
          Tryk <em>Gem historik</em> ud for et tag til venstre; så gemmer serveren dets værdier fra nu af, og kurven fyldes op.
          Interval og andre indstillinger findes under <a href="#tags">Tags</a>.
        {:else}
          Bed en tekniker eller administrator om at slå historik til for de tags, du vil se.
        {/if}
      </div>
    {:else if !selected.length}
      <div class="panel muted">Vælg et eller flere tags til venstre.</div>
    {:else if resp}
      {#each groups as [unit, tags] (unit + tags.map((t) => t.name).join(','))}
        {@const c = chartFor(tags)}
        <TrendChart title={unit} unit={unit === 'Til/fra' || unit === 'Uden enhed' ? '' : unit} series={c.series} data={c.data} xRange={[resp.start, resp.end]} />
      {/each}
      <p class="muted small">Træk vandret i en graf for at zoome; dobbeltklik for at zoome ud. Brud i linjen = ingen gyldig værdi (fx PLC uden forbindelse).</p>
    {/if}
  </section>
</div>

<style>
  .toolbar { margin-bottom: .75rem; }
  .layout { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 1rem; align-items: start; }
  @media (max-width: 800px) { .layout { grid-template-columns: minmax(0, 1fr); } }
  ul { list-style: none; padding: 0; margin: .5rem 0; max-height: 60vh; overflow-y: auto; }
  li { display: flex; align-items: center; gap: .4rem; }
  li label { flex: 1; min-width: 0; display: flex; align-items: center; gap: .4rem; padding: .2rem 0; cursor: pointer; }
  li label.off { opacity: .5; cursor: default; }
  .name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .enable { flex: none; padding: .1rem .45rem; font-size: .75rem; }
  .notice { border-left: 4px solid #2a78d6; }
  .swatch { width: 12px; height: 4px; border-radius: 2px; flex: none; }
</style>
