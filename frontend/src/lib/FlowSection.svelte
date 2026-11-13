<script lang="ts">
  // Flow i symbol-guiden (v6.1.0, PLAN.md › Flow-model): symbolets rolle i flowberegningen — pumpe (kapacitet og flow-rate),
  // restriktion (0,00 = blokeret … 1,00 = ingen) og, for en ventil med positioner, hvilke veje der er åbne i hver position. Serveren
  // beregner flowet gennem de forbundne symboler (services/flow_calc.py); resultatet kan vises på forbindelserne
  // (Tegn › Flow) og bruges som kilden "symbolets flow".
  // v6.3.0: typens flow-profil som standard, restriktionen som et tal 0,00–1,00 (Jan: ikke en bit), flowmåler, portfarver ud fra
  // de åbne veje, og en påmindelse, når symbolet ikke er bundet til tegningens forbindelser. Flowet er kun til visning.
  import { onMount } from 'svelte';
  import { get } from './api';
  import TagSelect, { type TagOption } from './TagSelect.svelte';
  import { FLOW_DEFAULTS, describeState, kindOf, mergeDefs, stateOf, unitOf, waysOf, wayKey, wayLabel, type FlowDefs } from './symbolFlow';
  import { DEFAULT_PORT_COLORS, defaultFlow, flowLevel, flowSourceMode, type FlowCfg, type FlowSource } from './symbolConfig';

  let { flow = $bindable(), type, positions, tags, linked = null, posStates = [] }: {
    flow: FlowCfg | null | undefined;
    type: string;
    positions: string[];
    tags: TagOption[];
    /** Er symbolet bundet til tegningens forbindelser? null = ukendt (guiden er ikke åbnet fra Tegn) */
    linked?: boolean | null;
    /** Positionernes tilstande fra trin 3 (v6.7.0, design B) — så følger de åbne veje dem, og tabellen her er kun til visning */
    posStates?: (string | null | undefined)[];
  } = $props();
  const byStates = $derived(posStates.some(Boolean));

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
  const unit = $derived(unitOf(defs, type) || 'enheder');
  const kind = $derived(kindOf(defs, type));
  const parts = $derived((def?.ports ?? []).filter((p) => p.part));

  /** Avanceret med tilstande: tabellen starter med de veje, tilstandene giver (en position uden tilstand: alle veje). */
  function openAdvanced(): void {
    if (flow && !flow.open) {
      flow.open = positions.map((_, j) => {
        const st = states.find((s) => s.name === posStates[j]);
        return st ? [...st.open] : ways.map(wayKey);
      });
    }
    advanced = true;
  }
  function enable(on: boolean): void {
    flow = on ? defaultFlow(type, positions, ways.map(wayKey), def) : null;
    if (flow && byStates) flow.open = null;     // de åbne veje følger positionernes tilstande (trin 3)
  }
  // v6.4.0 (Jan): rate og restriktion er faste værdier for symbolet (dets fysik) — tallet står altid fremme; et tag er et tilvalg
  const fixedOf = (s: FlowSource): number => (flowSourceMode(s) === 'val' ? valOf(s) : 1);
  function useTag(s: FlowSource, on: boolean): void {
    s.src = on ? (tags[0]?.name ?? '') : '@val:1';
  }
  const valOf = (s: FlowSource): number => { const n = Number(s.src.slice(5)); return Number.isFinite(n) ? n : 0; };
  const setVal = (s: FlowSource, v: number): void => { s.src = `@val:${Math.round(Math.min(1, Math.max(0, v)) * 100) / 100}`; };
  // et til/fra-tag giver kun 0 eller 1 — restriktionen skal være et tal 0,00–1,00 (fx ventilens åbning i %)
  const BIT = /:(coil|di|discrete|bit|bool)\b|\.\d{1,2}$/i;
  const isBit = (name: string): boolean => BIT.test(tags.find((t) => t.name === name)?.source ?? '');
  function toggleWay(j: number, key: string, on: boolean): void {
    if (!flow) return;
    const open = (flow.open ?? positions.map(() => ways.map(wayKey))).map((x) => [...x]);
    while (open.length < positions.length) open.push([]);
    open[j] = on ? [...new Set([...open[j], key])] : open[j].filter((k) => k !== key);
    flow.open = open;
  }
  const isOpen = (j: number, key: string): boolean => !flow?.open || (flow.open[j] ?? []).includes(key);
  // v6.6.0 (Jan): tilstande — vælg pr. position, hvad ventilen gør (fx "A → AB" = A igennem AB, B blokeret)
  const states = $derived(def?.states ?? []);
  let advanced = $state(false);
  const openAt = (j: number): string[] => flow?.open?.[j] ?? ways.map(wayKey);
  function setState(j: number, v: string): void {
    if (!flow || v === '') return;
    const open = (flow.open ?? positions.map(() => ways.map(wayKey))).map((x) => [...x]);
    while (open.length < positions.length) open.push([]);
    open[j] = [...states[Number(v)].open];
    flow.open = open;
  }
  const fmt2 = (v: number): string => v.toFixed(2).replace('.', ',');
</script>

{#snippet source(label: string, s: FlowSource, hint: string, fraction: boolean)}
  <div class="row wrap src">
    <span class="lbl">{label}</span>
    {#if flowSourceMode(s) === 'tag'}
      <TagSelect value={s.src} {tags} onchange={(v) => (s.src = v)} />
      <label class="small">1,00 ved <input type="number" min="0.001" step="any" bind:value={s.max} aria-label="{label}: værdi ved 1,00" /></label>
    {:else}
      <input type="number" min="0" max="1" step="0.01" value={fixedOf(s).toFixed(2)} oninput={(e) => setVal(s, Number(e.currentTarget.value || 0))} aria-label="{label}: værdi" />
      <input type="range" min="0" max="1" step="0.01" value={fixedOf(s)} oninput={(e) => setVal(s, Number(e.currentTarget.value))} aria-label="{label}: skyder" />
    {/if}
    <label class="small opt" title="Lad et tag i PLC'en styre værdien i stedet for den faste"><input type="checkbox" checked={flowSourceMode(s) === 'tag'}
      onchange={(e) => useTag(s, e.currentTarget.checked)} /> styret af et tag</label>
    <span class="small muted">{hint}</span>
    {#if fraction && flowSourceMode(s) === 'tag' && isBit(s.src)}
      <p class="small warn">'{s.src}' er et til/fra-signal og giver kun 0,00 eller 1,00. Vælg et tal-tag (fx ventilens åbning i %, med
        <em>1,00 ved</em> = 100) for en restriktion mellem 0,00 og 1,00.</p>
    {/if}
  </div>
{/snippet}

<section class="flow">
  <h4>Flow</h4>
  {#if linked === false}
    <p class="small warn">Symbolet er ikke bundet til tegningens forbindelser, så flowberegningen kan ikke se det. Luk guiden, og tryk
      <strong>Forbindelser › Bind forbindelser</strong> i Tegn (og gem tegningen).</p>
  {/if}
  <label class="opt"><input type="checkbox" checked={!!flow} onchange={(e) => enable(e.currentTarget.checked)} />
    Med i flowberegningen</label>
  {#if !flow}
    <p class="small muted">Uden egen opsætning gælder typens flow-rolle ({kind === 'pump' ? 'pumpe/kilde — står stille' : kind === 'piece' ? 'rørstykke' : 'forbruger'}{def?.restrict != null ? `, restriktion ${fmt2(def.restrict)}` : ''};
      Opsætning › Symboler › Ind/ud og veje). Slå til for at gøre det til en pumpe, give det en restriktion, en flowmåler eller vælge åbne veje pr. position.</p>
  {:else}
    {#if def?.ports.length}<p class="small muted">Punkter: {ports}{ways.length ? ` · veje: ${ways.map(wayLabel).join(', ')}` : ''} (Opsætning › Symboler › Ind/ud og veje).</p>
    {:else}<p class="small muted">Symboltypen har ingen ind/ud-definition: flowet kan gå mellem alle dets forbundne punkter.</p>{/if}
    <label class="opt"><input type="checkbox" bind:checked={flow.pump} /> Pumpe / kilde — giver flow fra IND til UD</label>
    {#if flow.pump}
      <label class="field-row">Kapacitet <input type="number" min="0" max="65535" step="1" bind:value={flow.capacity} aria-label="Kapacitet" /> {unit} ved fuld rate</label>
      {@render source('Flow-rate', flow.rate, '0,00 = stop … 1,00 = fuld rate (fx frekvens eller Til/Fra)', false)}
    {/if}
    {@render source('Restriktion', flow.restrict, '0,00 = blokeret … 1,00 = ingen restriktion (fx ventilens åbning)', true)}
    <div class="row wrap src">
      <span class="lbl">Målt flow</span>
      <TagSelect value={flow.measured?.src ?? ''} {tags} placeholder="— ingen flowmåler —"
        onchange={(v) => flow && (flow.measured = { low: 0, high: 100, ...(flow.measured ?? {}), src: v })} />
      <span class="small muted">en flowsensor ({unit}): pumperne gennem symbolet skaleres, så beregningen passer med målingen</span>
    </div>
    {#if flow.measured?.src}
      {@const m = flow.measured}
      <div class="row wrap src baseline">
        <span class="lbl">Baseline</span>
        <label class="small">lavt flow <input type="number" step="any" bind:value={m.low} aria-label="Lavt flow" /></label>
        <label class="small">højt flow <input type="number" step="any" bind:value={m.high} aria-label="Højt flow" /></label>
        <span class="small muted">{unit}</span>
        {#if !(m.high > m.low)}<p class="small warn">Lavt flow skal være mindre end højt flow.</p>
        {:else}
          <span class="small muted">→ <strong>symbolets flow-niveau</strong>: 0,00 ved {m.low} … 1,00 ved {m.high}
            (fx {fmt2((m.low + m.high) / 2)} → {fmt2(flowLevel((m.low + m.high) / 2, m.low, m.high) ?? 0)}). Brug det som kilde i
            animationerne ovenfor: løbelysets fart, blink ved lavt flow, farve ved et niveau.</span>
        {/if}
      </div>
    {/if}
    {#if positions.length && ways.length && byStates && !advanced}
      <table class="ways states">
        <thead><tr><th>Position</th><th>Tilstand</th><th>Betyder</th></tr></thead>
        <tbody>
          {#each positions as p, j (j)}
            {@const st = states.find((s) => s.name === posStates[j])}
            <tr><td>{p || `Position ${j + 1}`}</td><td>{st?.name ?? '— egen —'}</td>
              <td class="means">{describeState(def, flow?.open || !st ? openAt(j) : st.open)}</td></tr>
          {/each}
        </tbody>
      </table>
      <p class="small muted">Tilstandene vælges i trin 3; de åbne veje følger dem{flow?.open ? ' (her med vejene sat selv under Avanceret)' : ''}.</p>
      <div><button class="linkish small" onclick={openAdvanced}>▸ Avanceret: vælg vejene selv</button></div>
    {:else if byStates && advanced}
      <p class="small warn">Avanceret: vejene sættes selv nedenfor og styres ikke længere af tilstandene.
        <button class="linkish small" onclick={() => { if (flow) flow.open = null; advanced = false; }}>Lad tilstandene styre vejene igen</button>
        <button class="linkish small" onclick={() => (advanced = false)}>▾ Skjul</button></p>
    {:else if positions.length && ways.length && states.length && !byStates}
      <table class="ways states">
        <thead><tr><th>Position</th><th>Tilstand</th><th>Betyder</th></tr></thead>
        <tbody>
          {#each positions as p, j (j)}
            {@const si = stateOf(def, openAt(j))}
            <tr><td>{p || `Position ${j + 1}`}</td>
              <td><select value={si ?? ''} onchange={(e) => setState(j, e.currentTarget.value)} aria-label="{p || `Position ${j + 1}`}: tilstand">
                {#if si === null}<option value="">egen kombination</option>{/if}
                {#each states as st, k (k)}<option value={k}>{st.name}</option>{/each}
              </select></td>
              <td class="means">{describeState(def, openAt(j))}</td></tr>
          {/each}
        </tbody>
      </table>
      <p class="small muted">Vælg, hvad ventilen gør i hver position. Tilstandene er defineret pr. symboltype (Opsætning › Symboler › Ind/ud og
        veje › Tilstande). Ukendt position = alle porte blokeret.</p>
      <div><button class="linkish small" onclick={() => (advanced = !advanced)}>{advanced ? '▾' : '▸'} Avanceret: vælg vejene selv</button></div>
    {/if}
    {#if positions.length && ways.length && (!states.length || advanced)}
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
    {#if positions.length && ways.length}
      {#if parts.length}
        <label class="opt"><input type="checkbox" checked={!!flow.port_colors}
          onchange={(e) => flow && (flow.port_colors = e.currentTarget.checked ? { ...DEFAULT_PORT_COLORS } : null)} />
          Farv portene efter de åbne veje</label>
        {#if flow.port_colors}
          <div class="row wrap src">
            <label class="small">åben <input type="color" bind:value={flow.port_colors.open} /></label>
            <label class="small">lukket <input type="color" bind:value={flow.port_colors.closed} /></label>
            <select bind:value={flow.port_colors.anim} aria-label="Farv stregen eller fyldet"><option value="stroke">stregen</option><option value="fill">fyldet</option></select>
            <span class="small muted">Portene {parts.map((p) => p.name).join(', ')} farves i hver position: på en åben vej = <em>åben</em>, ellers <em>lukket</em>.
              En animation, du selv lægger på en port, går forud.</span>
          </div>
        {/if}
      {/if}
    {/if}
    <p class="small muted">Flowet er kun til visning — en illustration af, hvordan anlægget hænger sammen, ikke en simulering af det virkelige anlæg.</p>
  {/if}
</section>

<style>
  .flow { border-top: 1px solid var(--line); margin-top: .6rem; padding-top: .3rem; }
  .src { gap: .4rem; align-items: center; margin: .25rem 0; }
  .lbl { min-width: 6.5rem; }
  .src input[type='number'] { width: 6rem; }
  .baseline { padding-left: .6rem; border-left: 3px solid var(--line); }
  .src input[type='range'] { width: 9rem; }
  .field-row input { width: 7rem; }
  .ways { border-collapse: collapse; margin: .3rem 0; }
  .ways th, .ways td { border: 1px solid var(--line); padding: .15rem .45rem; text-align: center; }
  .ways td:first-child { text-align: left; }
  .states td.means { text-align: left; color: var(--muted); font-size: .85rem; }
  .linkish { background: none; border: none; color: var(--accent); cursor: pointer; padding: 0; font: inherit; text-align: left; }
  .warn { color: #8a5300; background: #fff8e1; border: 1px solid #e0b062; border-radius: 5px; padding: .25rem .45rem; margin: .2rem 0; flex-basis: 100%; }
</style>
