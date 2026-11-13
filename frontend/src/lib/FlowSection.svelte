<script lang="ts">
  // Flow i symbol-guiden (v6.1.0, PLAN.md › Flow-model): symbolets rolle i flowberegningen — pumpe (kapacitet og flow-rate),
  // restriktion (0 = blokeret, 1 = ingen) og, for en ventil med positioner, hvilke veje der er åbne i hver position. Serveren
  // beregner flowet gennem de forbundne symboler (services/flow_calc.py); resultatet kan vises på forbindelserne
  // (Tegn › Flow) og bruges som kilden "symbolets flow".
  import { onMount } from 'svelte';
  import { get } from './api';
  import TagSelect, { type TagOption } from './TagSelect.svelte';
  import { FLOW_DEFAULTS, mergeDefs, waysOf, wayKey, wayLabel, type FlowDefs } from './symbolFlow';
  import { defaultFlow, flowSourceMode, type FlowCfg, type FlowSource } from './symbolConfig';

  let { flow = $bindable(), type, positions, tags }: {
    flow: FlowCfg | null | undefined;
    type: string;
    positions: string[];
    tags: TagOption[];
  } = $props();

  let defs = $state<FlowDefs>(mergeDefs(null));
  onMount(async () => {
    try {
      defs = mergeDefs(await get<FlowDefs>('/api/symbol-flow'));
    } catch {
      defs = { ...FLOW_DEFAULTS };      // uden rettede definitioner bruges standarderne
    }
  });
  const def = $derived(defs[type]);
  const ways = $derived(waysOf(def));
  const ports = $derived(def?.ports.map((p) => `${p.name} (${p.role === 'in' ? 'ind' : p.role === 'out' ? 'ud' : 'begge'})`).join(', ') ?? '');

  function enable(on: boolean): void {
    flow = on ? defaultFlow(type, positions, ways.map(wayKey)) : null;
  }
  function setMode(s: FlowSource, mode: string): void {
    s.src = mode === 'val' ? '@val:1' : mode === 'tag' ? (tags[0]?.name ?? '') : '';
  }
  const valOf = (s: FlowSource): number => Number(s.src.slice(5)) || 0;
  function toggleWay(j: number, key: string, on: boolean): void {
    if (!flow) return;
    const open = (flow.open ?? positions.map(() => ways.map(wayKey))).map((x) => [...x]);
    while (open.length < positions.length) open.push([]);
    open[j] = on ? [...new Set([...open[j], key])] : open[j].filter((k) => k !== key);
    flow.open = open;
  }
  const isOpen = (j: number, key: string): boolean => !flow?.open || (flow.open[j] ?? []).includes(key);
</script>

{#snippet source(label: string, s: FlowSource, hint: string)}
  <div class="row wrap src">
    <span class="lbl">{label}</span>
    <select value={flowSourceMode(s)} onchange={(e) => setMode(s, e.currentTarget.value)} aria-label="{label}: kilde">
      <option value="none">fuld (1)</option><option value="tag">et tag</option><option value="val">en fast værdi</option>
    </select>
    {#if flowSourceMode(s) === 'tag'}
      <TagSelect value={s.src} {tags} onchange={(v) => (s.src = v)} />
      <label class="small">fuld ved <input type="number" min="0.001" step="any" bind:value={s.max} aria-label="{label}: værdi ved fuld" /></label>
    {:else if flowSourceMode(s) === 'val'}
      <input type="number" min="0" max="1" step="0.05" value={valOf(s)} oninput={(e) => (s.src = `@val:${e.currentTarget.value || 0}`)} aria-label="{label}: fast værdi" />
    {/if}
    <span class="small muted">{hint}</span>
  </div>
{/snippet}

<section class="flow">
  <h4>Flow</h4>
  <label class="opt"><input type="checkbox" checked={!!flow} onchange={(e) => enable(e.currentTarget.checked)} />
    Med i flowberegningen</label>
  {#if !flow}
    <p class="small muted">Symbolet regnes som en forbruger uden restriktion, hvis det er forbundet (Tegn › Bind forbindelser).
      Slå til for at gøre det til en pumpe, give det en restriktion eller vælge åbne veje pr. position.</p>
  {:else}
    {#if def}<p class="small muted">Punkter: {ports}{ways.length ? ` · veje: ${ways.map(wayLabel).join(', ')}` : ''} (Opsætning › Symboler › Ind/ud og veje).</p>
    {:else}<p class="small muted">Symboltypen har ingen ind/ud-definition: flowet kan gå mellem alle dets forbundne punkter.</p>{/if}
    <label class="opt"><input type="checkbox" bind:checked={flow.pump} /> Pumpe — giver flow fra IND til UD</label>
    {#if flow.pump}
      <label class="field-row">Kapacitet <input type="number" min="0" max="65535" step="1" bind:value={flow.capacity} aria-label="Kapacitet" /> l/min ved fuld rate</label>
      {@render source('Flow-rate', flow.rate, '0 = stop, 1 = fuld rate (fx frekvens eller Til/Fra)')}
    {/if}
    {@render source('Restriktion', flow.restrict, '0 = blokeret, 1 = ingen restriktion (fx ventilens åbning)')}
    {#if positions.length && ways.length}
      <table class="ways">
        <thead><tr><th>Position</th>{#each ways as w}<th>{wayLabel(w)}</th>{/each}</tr></thead>
        <tbody>
          {#each positions as p, j (j)}
            <tr><td>{p || `Position ${j + 1}`}</td>
              {#each ways as w}<td><input type="checkbox" checked={isOpen(j, wayKey(w))} aria-label="{p}: {wayLabel(w)} åben"
                onchange={(e) => toggleWay(j, wayKey(w), e.currentTarget.checked)} /></td>{/each}</tr>
          {/each}
        </tbody>
      </table>
      <p class="small muted">Sæt hak ved de veje, der er åbne i hver position (fx <em>AB → A</em> i position A). Ukendt position = lukket.</p>
    {/if}
  {/if}
</section>

<style>
  .flow { border-top: 1px solid var(--line); margin-top: .6rem; padding-top: .3rem; }
  .src { gap: .4rem; align-items: center; margin: .25rem 0; }
  .lbl { min-width: 6.5rem; }
  .src input[type='number'] { width: 6rem; }
  .field-row input { width: 7rem; }
  .ways { border-collapse: collapse; margin: .3rem 0; }
  .ways th, .ways td { border: 1px solid var(--line); padding: .15rem .45rem; text-align: center; }
  .ways td:first-child { text-align: left; }
</style>
