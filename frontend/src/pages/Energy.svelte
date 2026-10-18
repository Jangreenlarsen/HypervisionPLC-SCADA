<script lang="ts">
  import { onMount } from 'svelte';
  import BackToDrawing from '../lib/BackToDrawing.svelte';
  import { get } from '../lib/api';
  import EnergyChart from '../lib/EnergyChart.svelte';
  import { fmtKwh } from '../lib/energyData';
  import { assignColors, SERIES_COLORS } from '../lib/trendData';

  let { canEdit = false }: { canEdit?: boolean } = $props();

  interface EnergyTag { name: string; description: string; unit: string; energy: 'counter' | 'power'; energy_factor: number; oldest: number | null }
  interface Report {
    period: string; unit: string;
    buckets: { start: number; end: number; label: string; current: boolean }[];
    series: Record<string, (number | null)[]>; totals: Record<string, number>;
    meta: Record<string, { description: string; kind: string }>;
  }
  const PERIODS = [{ id: 'day', label: 'Dag', hint: 'seneste 14 dage' }, { id: 'week', label: 'Uge', hint: 'seneste 12 uger' },
    { id: 'month', label: 'Måned', hint: 'seneste 12 måneder' }];

  let tags = $state<EnergyTag[]>([]);
  let energyDays = $state(0);
  let selected = $state<string[]>([]);
  let colors = $state<Record<string, number>>({});
  let period = $state('day');
  let rep = $state<Report | null>(null);
  let error = $state('');
  let loading = $state(false);

  const label = (n: string) => tags.find((t) => t.name === n)?.description || n;
  const query = $derived(`tags=${selected.map(encodeURIComponent).join(',')}&period=${period}`);

  async function load(): Promise<void> {
    if (!selected.length) {
      rep = null;
      return;
    }
    error = '';
    loading = true;
    try {
      rep = await get<Report>(`/api/energy/report?${query}`);
    } catch (e) {
      error = (e as Error).message;
    } finally {
      loading = false;
    }
  }

  function toggle(name: string): void {
    selected = selected.includes(name) ? selected.filter((n) => n !== name) : [...selected, name];
    colors = assignColors(selected, colors);
    load();
  }

  onMount(async () => {
    try {
      const r = await get<{ energy_days: number; tags: EnergyTag[] }>('/api/energy/tags');
      tags = r.tags;
      energyDays = r.energy_days;
      selected = tags.slice(0, 7).map((t) => t.name);
      colors = assignColors(selected, {});
      await load();
    } catch (e) {
      error = (e as Error).message;
    }
  });

  const chartSeries = $derived(rep ? selected.filter((n) => rep!.series[n]).map((n) => ({
    name: n, label: label(n), colorIndex: colors[n] ?? 0, values: rep!.series[n],
  })) : []);
</script>

<div class="row toolbar">
  <BackToDrawing />
  {#each PERIODS as p}
    <button class:primary={period === p.id} title={p.hint} onclick={() => { period = p.id; load(); }}>{p.label}</button>
  {/each}
  {#if rep && selected.length}<a class="btn" href={`/api/energy/export?${query}`} download>CSV</a>{/if}
  {#if loading}<span class="muted small">Beregner …</span>{/if}
</div>

{#if error}<div class="error">{error}</div>{/if}

{#if !tags.length}
  <div class="panel notice">
    <strong>Ingen energi-tags endnu.</strong>
    {#if canEdit}
      Under <a href="#tags">Tags</a> → Redigér: slå <em>historik</em> til og vælg <em>Energi</em> = tæller (fx kWh-måler) eller
      effekt (fx W/kW). Rapporten beregnes ud fra historikken — fra det øjeblik den er slået til.
    {:else}
      Bed en tekniker eller administrator om at markere energi-tags.
    {/if}
  </div>
{:else}
  <div class="layout">
    <aside class="panel">
      <h3>Energi-tags</h3>
      <ul>
        {#each tags as t (t.name)}
          <li>
            <label>
              <input type="checkbox" checked={selected.includes(t.name)} onchange={() => toggle(t.name)} />
              {#if selected.includes(t.name)}<span class="swatch" style="background:{SERIES_COLORS[colors[t.name] ?? 0]}"></span>{/if}
              <span class="name">{t.description || t.name}</span>
              <span class="muted small">{t.energy === 'counter' ? 'tæller' : 'effekt'}</span>
            </label>
          </li>
        {/each}
      </ul>
      <p class="muted small">Energi-tags gemmes i {energyDays} dage. Den igangværende periode er markeret og ikke afsluttet.</p>
    </aside>

    <section>
      {#if rep && chartSeries.length}
        <div class="panel"><EnergyChart buckets={rep.buckets} series={chartSeries} /></div>
        <div class="panel table-wrap">
          <table>
            <thead>
              <tr><th>Periode</th>{#each chartSeries as s}<th class="num"><span class="swatch" style="background:{SERIES_COLORS[s.colorIndex]}"></span>{s.label}</th>{/each}</tr>
            </thead>
            <tbody>
              {#each rep.buckets as b, i}
                <tr class:current={b.current}>
                  <td>{b.label}{b.current ? ' (igang)' : ''}</td>
                  {#each chartSeries as s}<td class="num">{fmtKwh(s.values[i])}</td>{/each}
                </tr>
              {/each}
            </tbody>
            <tfoot>
              <tr><th>I alt (kWh)</th>{#each chartSeries as s}<th class="num">{fmtKwh(rep.totals[s.name])}</th>{/each}</tr>
            </tfoot>
          </table>
        </div>
      {:else if !selected.length}
        <div class="panel muted">Vælg et eller flere energi-tags til venstre.</div>
      {/if}
    </section>
  </div>
{/if}

<style>
  .toolbar { margin-bottom: .75rem; }
  .layout { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 1rem; align-items: start; }
  @media (max-width: 800px) { .layout { grid-template-columns: minmax(0, 1fr); } }
  ul { list-style: none; padding: 0; margin: .5rem 0; }
  li label { display: flex; align-items: center; gap: .4rem; padding: .2rem 0; cursor: pointer; }
  .name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .swatch { display: inline-block; width: 12px; height: 4px; border-radius: 2px; margin-right: .3rem; vertical-align: middle; flex: none; }
  .num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
  tr.current td { background: #f2f1ec; }
  tfoot th { border-top: 2px solid var(--line); }
  .notice { border-left: 4px solid #2a78d6; }
</style>
