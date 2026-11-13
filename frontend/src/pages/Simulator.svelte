<script lang="ts">
  // Simulator (v6.5.0, PLAN.md › Simulator, Jan: "et simulationspanel, der arbejder med alle de variabler, en tegning gør brug af,
  // så vi kan indskyde værdier og se, hvad det resulterer i af display-output"). Til venstre tegningen, tegnet med Overview-motoren
  // ud fra de simulerede værdier; til højre panelet med tegningens variabler. Serveren regner logik, positioner og flow med den
  // samme kode som driften. Intet skrives til PLC'en.
  import { onDestroy, onMount, tick } from 'svelte';
  import { del, get, post, put, type DrawingView } from '../lib/api';
  import { ask } from '../lib/ask';
  import { fitSvg, mountSvg, onLayoutChange, renderAll } from '../lib/canvas';
  import { clearOverlays, drawOverlay, markPassive } from '../lib/symbolOverlay';
  import { showsBadge, type SymbolState } from '../lib/symbolUi';
  import {
    emptyState, fromLive, isSimulated, liveText, matches, startValue, stepFor, toLive,
    type SimResult, type SimScenario, type SimState, type SimTag, type SimVariables,
  } from '../lib/simulator';

  let { route }: { route: string } = $props();

  let drawings = $state<{ id: string; name: string }[]>([]);
  let drawingId = $state('');
  let view = $state<DrawingView | null>(null);
  let vars = $state<SimVariables | null>(null);
  let sim = $state<SimState>(emptyState());
  let result = $state<SimResult | null>(null);
  let scenarios = $state<SimScenario[]>([]);
  let scenarioId = $state<number | ''>('');
  let error = $state('');       // indlæsning og simulering
  let sError = $state('');      // scenarierne (overskrives ikke af den løbende simulering)
  let info = $state('');
  let search = $state('');
  let onlySim = $state(false);
  let container = $state<HTMLElement>();
  let svgRoot: SVGSVGElement | null = null;
  let busy = false;
  let pending = false;
  let gen = 0;                  // tegningsskift: svar for en anden tegning end den viste droppes
  let hlTimer: ReturnType<typeof setTimeout> | undefined;
  let timer: ReturnType<typeof setInterval> | undefined;
  let debounce: ReturnType<typeof setTimeout> | undefined;
  let stopLayout: () => void = () => {};
  const base = $derived(`/api/drawings/${encodeURIComponent(drawingId)}`);

  onMount(async () => {
    try {
      drawings = await get<{ id: string; name: string }[]>('/api/drawings');
      const want = route.split('/')[1] || drawings[0]?.id || '';
      if (want) await open(want);
    } catch (e) {
      error = (e as Error).message;
    }
    timer = setInterval(() => { if (!document.hidden) void run(); }, 3000);   // de live variabler følger med
  });
  onDestroy(() => { clearInterval(timer); clearTimeout(debounce); clearTimeout(hlTimer); stopLayout(); });

  async function open(id: string): Promise<void> {
    error = sError = info = '';
    const my = ++gen;
    view = null;
    result = null;
    drawingId = id;
    if (location.hash !== `#simulator/${id}`) history.replaceState(null, '', `#simulator/${id}`);
    try {
      const [v, vs, sc] = await Promise.all([
        get<DrawingView>(`/api/drawings/${encodeURIComponent(id)}/view`),
        get<SimVariables>(`/api/drawings/${encodeURIComponent(id)}/simulator`),
        get<SimScenario[]>(`/api/drawings/${encodeURIComponent(id)}/sim-scenarios`),
      ]);
      if (my !== gen) return;      // en nyere tegning er valgt imens
      [view, vars, scenarios] = [v, vs, sc];
      sim = emptyState();
      scenarioId = '';
      await tick();
      if (!container) return;
      svgRoot = mountSvg(container, view.svg, view.symbols);
      stopLayout();
      stopLayout = onLayoutChange(() => fitSvg(svgRoot, container ?? null), container);
      fitSvg(svgRoot, container);
      for (const [el, s] of Object.entries(view.symbol_config ?? {})) if (s.passive && svgRoot) markPassive(svgRoot, el);
      await run();
    } catch (e) {
      error = (e as Error).message;
    }
  }

  /** Regn tegningen med de simulerede værdier og tegn den. */
  async function run(): Promise<void> {
    if (!drawingId || !view) return;
    if (busy) { pending = true; return; }
    busy = true;
    const my = gen;
    try {
      const r = await post<SimResult>(`${base}/simulate`, $state.snapshot(sim));
      if (my !== gen) return;      // svaret hører til en tegning, der ikke vises mere
      result = r;
      refreshLive(r);
      paint();
      error = '';
    } catch (e) {
      const msg = (e as Error).message;
      if (!/optaget/i.test(msg)) error = msg;
    } finally {
      busy = false;
      if (pending) { pending = false; void run(); }
    }
  }
  const changed = (): void => { clearTimeout(debounce); debounce = setTimeout(() => void run(), 200); };

  /** Panelets live-værdier følger PLC'en: de variabler, der ikke er simulerede, har deres live værdi i svaret. */
  function refreshLive(r: SimResult): void {
    if (!vars) return;
    for (const t of [...vars.tags, ...vars.alarms]) if (!isSimulated(sim, t.name) && r.values[t.name]) t.live = r.values[t.name];
    for (const p of vars.positions) {
      const v = r.values[`sym:${drawingId}:${p.element}:pos`]?.value;
      if (!(p.element in sim.positions)) p.live = typeof v === 'number' ? v : null;
    }
  }

  function paint(): void {
    if (!container || !view || !result || !svgRoot) return;
    const values = toLive(result);
    renderAll(container, view.bindings, values, view.tags);
    clearOverlays(svgRoot);
    for (const [el, s] of Object.entries(view.symbol_config ?? {})) {
      if (s.op !== 'positions' || !s.pseudo) continue;
      const remote = values[s.pseudo.remote]?.value;
      drawOverlay(svgRoot, el, {
        state: ((values[s.pseudo.state]?.value as SymbolState) ?? 'unknown'), badge: showsBadge(s),
        remoteLabel: typeof remote === 'number' ? s.labels[remote] ?? null : null,
        locked: values[s.pseudo.locked]?.value === true, lockedLabels: s.labels.filter((_, j) => s.lock_positions[j]),
      });
    }
  }

  // ---- variablerne
  function setSim(name: string, on: boolean, t?: SimTag): void {
    if (on) sim.values[name] = t ? startValue(t) : false;
    else delete sim.values[name];
    changed();
  }
  function setValue(name: string, v: unknown): void { sim.values[name] = v; changed(); }
  function setPos(el: string, v: string): void {
    if (v === '') delete sim.positions[el];
    else sim.positions[el] = Number(v);
    changed();
  }
  function allLive(): void { sim = emptyState(); scenarioId = ''; changed(); }
  function startFromLive(): void { if (vars) { sim = fromLive(vars); changed(); info = 'Alle variabler med en live værdi er nu simulerede med den værdi.'; } }

  // ---- markér, hvor en variabel bruges
  function highlight(ids: string[]): void {
    if (!svgRoot) return;
    for (const el of svgRoot.querySelectorAll('.hv-sim-hl')) el.classList.remove('hv-sim-hl');
    for (const id of ids) svgRoot.querySelector(`#${CSS.escape(id)}`)?.classList.add('hv-sim-hl');
    clearTimeout(hlTimer);
    hlTimer = setTimeout(() => { for (const el of svgRoot?.querySelectorAll('.hv-sim-hl') ?? []) el.classList.remove('hv-sim-hl'); }, 2500);
  }

  // ---- scenarier
  function load(id: number | ''): void {
    scenarioId = id;
    const s = scenarios.find((x) => x.id === id);
    if (!s) return;
    sim = { values: { ...s.values }, positions: { ...s.positions } };
    info = `Scenariet "${s.name}" er hentet.`;
    changed();
  }
  async function saveAs(): Promise<void> {
    const name = window.prompt('Scenariets navn (fx "Pumpe 2 fejl")')?.trim();
    if (!name) return;
    try {
      const s = await post<SimScenario>(`${base}/sim-scenarios`, { name, ...$state.snapshot(sim) });
      scenarios = await get<SimScenario[]>(`${base}/sim-scenarios`);
      scenarioId = s.id;
      info = `Scenariet "${s.name}" er gemt.`;
      sError = '';
    } catch (e) {
      sError = (e as Error).message;
    }
  }
  async function saveCurrent(): Promise<void> {
    const s = scenarios.find((x) => x.id === scenarioId);
    if (!s) return;
    try {
      await put(`${base}/sim-scenarios/${s.id}`, { name: s.name, ...$state.snapshot(sim) });
      scenarios = await get<SimScenario[]>(`${base}/sim-scenarios`);
      info = `Scenariet "${s.name}" er opdateret.`;
      sError = '';
    } catch (e) {
      sError = (e as Error).message;
    }
  }
  async function removeScenario(): Promise<void> {
    const s = scenarios.find((x) => x.id === scenarioId);
    if (!s || !(await ask(`Slet scenariet "${s.name}"?`, { ok: 'Slet', danger: true }))) return;
    try {
      await del(`${base}/sim-scenarios/${s.id}`);
      scenarios = await get<SimScenario[]>(`${base}/sim-scenarios`);
      scenarioId = '';
      info = `Scenariet "${s.name}" er slettet.`;
      sError = '';
    } catch (e) {
      sError = (e as Error).message;
    }
  }

  const nSim = $derived(Object.keys(sim.values).length + Object.keys(sim.positions).length);
  const shownTags = $derived((vars?.tags ?? []).filter((t) => matches(t, search, isSimulated(sim, t.name), onlySim)));
  const shownAlarms = $derived((vars?.alarms ?? []).filter((t) => matches({ ...t, description: t.tag }, search, isSimulated(sim, t.name), onlySim)));
  const shownPos = $derived((vars?.positions ?? []).filter((p) => matches({ name: p.name, used: p.labels }, search, p.element in sim.positions, onlySim)));
  const num = (v: string): number => Number(v.replace(',', '.'));
</script>

<div class="simbar" role="status"><strong>SIMULERING</strong> — intet skrives til PLC'en. Værdier, du sætter her, ses kun på denne side.</div>

<div class="row head">
  <select value={drawingId} onchange={(e) => open(e.currentTarget.value)} aria-label="Tegning">
    {#each drawings as d (d.id)}<option value={d.id}>{d.name}</option>{/each}
  </select>
  <button onclick={startFromLive} disabled={!vars} title="Kopiér PLC'ens værdier ind som simulerede værdier">Start fra live</button>
  <button onclick={allLive} disabled={!nSim} title="Alle variabler følger PLC'en igen">Alt til live</button>
  <span class="sep"></span>
  <label class="opt">Scenarie
    <select value={scenarioId} onchange={(e) => load(e.currentTarget.value === '' ? '' : Number(e.currentTarget.value))} aria-label="Scenarie">
      <option value="">— intet —</option>
      {#each scenarios as s (s.id)}<option value={s.id}>{s.name}</option>{/each}
    </select></label>
  <button onclick={saveCurrent} disabled={scenarioId === ''} title="Gem de simulerede værdier i det valgte scenarie">Gem</button>
  <button onclick={saveAs} disabled={!drawingId}>Gem som …</button>
  <button class="danger" onclick={removeScenario} disabled={scenarioId === ''}>Slet</button>
  <span class="grow"></span>
  {#if result}<span class="small muted">{nSim} simuleret · beregnet på {result.ms} ms</span>{/if}
  <a class="btn" href={'#overview/' + drawingId}>Overview</a>
</div>
{#if error}<p class="msg err">{error}</p>{/if}
{#if sError}<p class="msg err">{sError}</p>{/if}
{#if info}<p class="msg ok">{info}</p>{/if}
{#each result?.notes ?? [] as n}<p class="msg">{n}</p>{/each}

<div class="layout">
  <div class="drawing" bind:this={container}></div>

  <aside class="panel-sim" aria-label="Tegningens variabler">
    <div class="row">
      <input type="search" placeholder="Søg variabel eller symbol" bind:value={search} aria-label="Søg" />
      <label class="opt small"><input type="checkbox" bind:checked={onlySim} /> kun simulerede</label>
    </div>
    {#if vars}
      {#if vars.positions.length}
        <h4>Symbolernes position</h4>
        {#each shownPos as p (p.element)}
          <div class="var" class:on={p.element in sim.positions}>
            <span class="nm" title={p.element}>{p.name}</span>
            <select value={sim.positions[p.element] ?? ''} onchange={(e) => setPos(p.element, e.currentTarget.value)} aria-label="{p.name}: position">
              <option value="">Live{p.live !== null ? ` (${p.labels[p.live] ?? p.live})` : ''}</option>
              {#each p.labels as l, j (j)}<option value={j}>{l || `Position ${j + 1}`}</option>{/each}
            </select>
            <button class="small" onclick={() => highlight([p.element])} title="Vis symbolet på tegningen">Vis</button>
          </div>
        {/each}
      {/if}

      <h4>Tags fra PLC'en ({vars.tags.length})</h4>
      {#each shownTags as t (t.name)}
        {@const on = isSimulated(sim, t.name)}
        {@const v = sim.values[t.name]}
        <div class="var" class:on>
          <label class="opt sw" title={on ? 'Simuleret — tryk for at følge PLC\'en igen' : 'Følger PLC\'en — tryk for at simulere'}>
            <input type="checkbox" checked={on} onchange={(e) => setSim(t.name, e.currentTarget.checked, t)} aria-label="{t.name}: simulér" /></label>
          <span class="nm" title={[t.description, `PLC: ${t.plc}`, ...t.used].filter(Boolean).join('\n')}>{t.name}</span>
          {#if !on}
            <span class="live small muted">live: {liveText(t.live, t.unit)}</span>
          {:else if v === null}
            <span class="small err">komm.fejl</span>
            <button class="small" onclick={() => setValue(t.name, startValue(t))}>Værdi</button>
          {:else if t.kind === 'bool'}
            <label class="opt small"><input type="checkbox" checked={v === true} onchange={(e) => setValue(t.name, e.currentTarget.checked)} aria-label="{t.name}: Til" /> {v ? 'Til' : 'Fra'}</label>
          {:else}
            <input class="n" type="number" step={stepFor(t)} value={typeof v === 'number' ? v : 0} aria-label="{t.name}: værdi"
              oninput={(e) => e.currentTarget.value !== '' && setValue(t.name, num(e.currentTarget.value))} />
            {#if t.min !== null && t.max !== null && t.max > t.min}
              <input type="range" min={t.min} max={t.max} step={stepFor(t)} value={typeof v === 'number' ? v : t.min} aria-label="{t.name}: skyder"
                oninput={(e) => setValue(t.name, Number(e.currentTarget.value))} />
            {/if}
            {#if t.unit}<span class="small muted">{t.unit}</span>{/if}
          {/if}
          <span class="grow"></span>
          {#if on && v !== null}<button class="small" onclick={() => setValue(t.name, null)} title="Simulér en kommunikationsfejl på tagget">komm.fejl</button>{/if}
          <button class="small" onclick={() => highlight(t.elements)} disabled={!t.elements.length} title={t.used.join('\n')}>Vis</button>
        </div>
      {:else}<p class="small muted">Ingen tags{search || onlySim ? ' passer til søgningen' : ''}.</p>{/each}

      {#if vars.alarms.length}
        <h4>Alarmer</h4>
        {#each shownAlarms as a (a.name)}
          {@const on = isSimulated(sim, a.name)}
          <div class="var" class:on>
            <label class="opt sw"><input type="checkbox" checked={on} onchange={(e) => setSim(a.name, e.currentTarget.checked)} aria-label="{a.tag}: simulér alarm" /></label>
            <span class="nm" title={a.used.join('\n')}>{a.tag} <span class="muted small">({a.kind === 'unack' ? 'ikke kvitteret' : 'aktiv'})</span></span>
            {#if on}
              <label class="opt small"><input type="checkbox" checked={sim.values[a.name] === true} onchange={(e) => setValue(a.name, e.currentTarget.checked)} /> {sim.values[a.name] ? 'Ja' : 'Nej'}</label>
            {:else}<span class="live small muted">live: {liveText(a.live)}</span>{/if}
            <span class="grow"></span>
            <button class="small" onclick={() => highlight(a.elements)} disabled={!a.elements.length}>Vis</button>
          </div>
        {/each}
      {/if}
      <p class="small muted note">Logikblokke, symbolernes tilstand og flowet beregnes af serveren ud fra værdierne — med den samme kode som
        driften. En ny position vises som gyldig med det samme (tid og forløb simuleres ikke). Trendgrafer viser historikken.</p>
    {:else if !error}<p class="small muted">Henter …</p>{/if}
  </aside>
</div>

<style>
  .simbar { background: #6a1b9a; color: #fff; padding: .35rem .7rem; border-radius: 6px; margin-bottom: .4rem; font-size: .9rem; }
  .head { gap: .4rem; flex-wrap: wrap; margin-bottom: .4rem; align-items: center; }
  .sep { width: 1px; align-self: stretch; background: var(--line); margin: 0 .2rem; }
  .grow { flex: 1; }
  .layout { display: grid; grid-template-columns: minmax(0, 1fr) 380px; gap: .8rem; align-items: start; }
  @media (max-width: 1000px) { .layout { grid-template-columns: minmax(0, 1fr); } }
  .drawing { min-height: 60vh; border: 3px solid #6a1b9a; border-radius: 8px; background: var(--panel, #fff); overflow: hidden; }
  .panel-sim { max-height: calc(100vh - 11rem); overflow: auto; border: 1px solid var(--line); border-radius: 8px; padding: .5rem .6rem;
    background: var(--panel, #fff); display: flex; flex-direction: column; gap: .25rem; }
  .panel-sim h4 { margin: .6rem 0 .2rem; font-size: .8rem; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); }
  .var { display: flex; align-items: center; gap: .35rem; padding: .2rem .3rem; border-radius: 5px; flex-wrap: wrap; }
  .var.on { background: #f3e5f5; }
  .var .nm { min-width: 7rem; font-weight: 600; font-size: .88rem; overflow-wrap: anywhere; }
  .var .n { width: 5.5rem; }
  .var input[type='range'] { width: 7rem; }
  .sw { margin: 0; }
  .msg { padding: .3rem .5rem; background: #fff8e1; border: 1px solid #e0b062; border-radius: 6px; margin: .2rem 0; }
  .msg.err, .err { color: #b71c1c; }
  .msg.ok { background: #e8f5e9; border-color: #81c784; }
  .note { margin-top: .6rem; }
  .drawing :global(.hv-sim-hl) { outline: 3px solid #ff6f00; filter: drop-shadow(0 0 6px #ff6f00); }
</style>
