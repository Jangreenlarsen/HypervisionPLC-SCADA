<script lang="ts">
  // Flowet live i Tegn (v6.3.0, PLAN.md › Flow-model runde 2, Jan: "det vil være fint vi kan se det live i forbindelse med tegn"):
  // beregner flowet for tegningen, som den ser ud i editoren lige nu (også ugemt), og viser det som løbelys, pile og tal oven på
  // tegningen. "Live" bruger PLC'ens værdier; "Simulering" lader dig starte/stoppe pumper, sætte rate og restriktion (0,00–1,00)
  // og vælge ventilpositioner — uden at skrive noget til PLC'en. Kun til visning.
  import { onDestroy } from 'svelte';
  import { post } from './api';
  import { emptySim, fmt2, overlayData, previewBody, type Preview, type Sim } from './flowLive';

  let { drawingId, ready, getSvg, setOverlay }: {
    drawingId: string; ready: boolean;
    getSvg: () => string | null;
    setOverlay: (data: Record<string, unknown> | null) => void;
  } = $props();

  const KEY = 'draw.flowlive';
  const load = (): boolean => { try { return localStorage.getItem(KEY) === '1'; } catch { return false; } };
  let show = $state(load());
  let mode = $state<'live' | 'sim'>('live');
  let sim = $state<Sim>(emptySim());
  let data = $state<Preview | null>(null);
  let error = $state('');
  let busy = false;
  let timer: ReturnType<typeof setInterval> | undefined;
  let openRestricts = $state(false);

  async function refresh(): Promise<void> {
    if (!show || !ready || busy || document.hidden) return;   // skjult fane: ingen beregninger
    const svg = getSvg();
    if (!svg) return;
    busy = true;
    try {
      data = await post<Preview>(`/api/drawings/${encodeURIComponent(drawingId)}/flow/preview`,
        previewBody(svg, mode === 'sim' ? $state.snapshot(sim) as Sim : null));
      error = '';
      if (show) setOverlay(overlayData(data));
    } catch (e) {
      const msg = (e as Error).message;
      if (!/optaget/i.test(msg)) error = msg;      // optaget (429): prøv igen ved næste runde
    } finally {
      busy = false;
    }
  }

  $effect(() => {
    void drawingId; void ready;
    try { localStorage.setItem(KEY, show ? '1' : '0'); } catch { /* ingen localStorage */ }
    clearInterval(timer);
    if (show && ready) {
      void refresh();
      timer = setInterval(refresh, 2000);       // højst hvert 2. sekund (en Pi skal også passe resten)
    } else {
      setOverlay(null);
      data = null;
    }
  });
  onDestroy(() => { clearInterval(timer); setOverlay(null); });

  function setMode(m: 'live' | 'sim'): void {
    mode = m;
    if (m === 'sim' && data) {
      // start simuleringen fra det, der er nu
      sim = { rates: Object.fromEntries(data.pumps.map((p) => [p.id, (data!.flows[p.id] ?? 0) > 0 ? 1 : 0])),
        positions: Object.fromEntries(data.valves.filter((v) => v.pos !== null).map((v) => [v.id, v.pos as number])), restricts: {} };
    }
    void refresh();
  }
  const change = (f: () => void) => { f(); void refresh(); };
  const rateOf = (id: string): number => sim.rates[id] ?? 0;
</script>

<section class="fl">
  <label class="opt"><input type="checkbox" bind:checked={show} disabled={!ready} /> <strong>Vis flowet på tegningen</strong></label>
  {#if show}
    <div class="row">
      <label class="opt"><input type="radio" name="flmode" checked={mode === 'live'} onchange={() => setMode('live')} /> Live (PLC'ens værdier)</label>
      <label class="opt"><input type="radio" name="flmode" checked={mode === 'sim'} onchange={() => setMode('sim')} /> Simulering</label>
    </div>
    {#if error}<p class="msg err">{error}</p>{/if}
    {#if data}
      {#if !data.linked}<p class="msg">Tegningen har ingen bundne forbindelser: tryk <strong>Forbindelser › Bind forbindelser</strong>.</p>{/if}
      {#each data.notes as n}<p class="msg">{n}</p>{/each}
      <p class="small muted">{data.stats.pumping ?? 0} af {data.stats.pumps ?? 0} pumper giver flow · beregnet på {data.ms} ms
        {mode === 'sim' ? '· simuleret — intet skrives til PLC\'en' : '· tegningen, som den ser ud nu (også ugemt)'}</p>
      {#if mode === 'sim'}
        {#if data.pumps.length}
          <div class="blk"><span class="mhead">Pumper / kilder</span>
            {#each data.pumps as p (p.id)}
              <div class="row small">
                <label class="opt"><input type="checkbox" checked={rateOf(p.id) > 0}
                  onchange={(e) => change(() => (sim.rates[p.id] = e.currentTarget.checked ? 1 : 0))} /> {p.name || p.id}</label>
                <input type="range" min="0" max="1" step="0.01" value={rateOf(p.id)} aria-label="{p.name || p.id}: rate"
                  oninput={(e) => change(() => (sim.rates[p.id] = Number(e.currentTarget.value)))} />
                <span class="num">{fmt2(rateOf(p.id))}</span>
                <span class="muted">× {p.capacity}{p.configured ? '' : ' (typens standard)'}</span>
              </div>
            {/each}
          </div>
        {/if}
        {#if data.valves.length}
          <div class="blk"><span class="mhead">Ventiler</span>
            {#each data.valves as v (v.id)}
              <div class="row small"><span class="nm">{v.name || v.id}</span>
                <select value={sim.positions[v.id] ?? v.pos ?? ''} aria-label="{v.name || v.id}: position"
                  onchange={(e) => change(() => (sim.positions[v.id] = Number(e.currentTarget.value)))}>
                  {#if (sim.positions[v.id] ?? v.pos) == null}<option value="">— ukendt —</option>{/if}
                  {#each v.labels as l, j (j)}<option value={j}>{l || `Position ${j + 1}`}</option>{/each}
                </select></div>
            {/each}
          </div>
        {/if}
        {#if data.symbols.length}
          <div class="blk">
            <button class="linkish" onclick={() => (openRestricts = !openRestricts)}>{openRestricts ? '▾' : '▸'} Restriktion pr. symbol (0,00–1,00)</button>
            {#if openRestricts}
              {#each data.symbols as s (s.id)}
                {@const r = sim.restricts[s.id] ?? s.restrict}
                <div class="row small"><span class="nm">{s.name || s.id}</span>
                  <input type="range" min="0" max="1" step="0.01" value={r} aria-label="{s.name || s.id}: restriktion"
                    oninput={(e) => change(() => (sim.restricts[s.id] = Number(e.currentTarget.value)))} />
                  <span class="num">{fmt2(r)}</span></div>
              {/each}
            {/if}
          </div>
        {/if}
        <button class="small" onclick={() => change(() => (sim = emptySim()))}>Nulstil simuleringen</button>
      {/if}
    {:else if !error}<p class="small muted">Beregner …</p>{/if}
    <p class="small muted">Flowet er kun til visning: en illustration af, hvordan anlægget hænger sammen — ikke en simulering af det virkelige anlæg.</p>
  {/if}
</section>

<style>
  .fl { display: flex; flex-direction: column; gap: .35rem; border: 1px solid var(--line); border-radius: 6px; padding: .4rem .55rem; }
  .row { display: flex; align-items: center; gap: .4rem; flex-wrap: wrap; }
  .blk { display: flex; flex-direction: column; gap: .15rem; }
  .mhead { font-size: .72rem; text-transform: uppercase; letter-spacing: .04em; color: var(--muted, #666); }
  .nm { min-width: 7rem; }
  .num { font-variant-numeric: tabular-nums; min-width: 2.6rem; }
  input[type='range'] { width: 8rem; }
  .msg { padding: .3rem .5rem; background: #fff8e1; border: 1px solid #e0b062; border-radius: 6px; margin: 0; }
  .msg.err { color: #b71c1c; }
  .linkish { background: none; border: none; color: var(--accent); cursor: pointer; padding: 0; font: inherit; text-align: left; }
</style>
