<script lang="ts">
  // Opsætning › Symboler (v6.11.0, PLAN.md › Symboler — symbolet i centrum; Jan: "vælg et symbol i biblioteket og lav derfra alle
  // operationer"): vælg et symbol én gang i listen, og gør alt på det i panelet — Redigér grafik, Omdøb, Slet, Flyt til sektion
  // og fanerne Tilslutningspunkter og Ind/ud og veje. "Organisér bibliotek …" samler det, der gælder hele biblioteket.
  // Adressen: #symbols/<tegning|ny|->/<type>/<punkter|veje> (genvejene fra Tegn virker som før).
  import { onDestroy, onMount } from 'svelte';
  import { get } from '../lib/api';
  import { ask } from '../lib/ask';
  import { setLeaveGuard } from '../lib/leaveGuard';
  import { CATEGORIES, type SymbolCategory } from '../lib/symbols';
  import SymbolLibrary from '../lib/SymbolLibrary.svelte';
  import SymbolFlowEditor from '../lib/SymbolFlowEditor.svelte';
  import PortsEditor from '../lib/PortsEditor.svelte';
  import { FLOW_DEFAULTS, mergeDefs, typePortMap, type FlowDef } from '../lib/symbolFlow';
  import { OWN_LABEL, OWN_SECTION, moveSymbol, sections, symbolsIn } from '../lib/library';
  import { defs, deleteOwn, library, loadLibrary, saveLayout, updateOwn } from '../lib/libraryStore.svelte';
  import { drawHref, panelHref, parseSymbolRoute, type SymbolTab } from '../lib/symbolRoute';
  import { editGraphic, isOwnSymbol } from '../lib/symbolActions';
  // @ts-expect-error — ren JS uden typer (deles med Tegn)
  import { symbolType } from '../../svgedit-host/symbolPorts.js';

  let { route = 'symbols' }: { route?: string } = $props();
  const from = $derived(parseSymbolRoute(route));
  let backName = $state('');

  type Pt = [number, number];
  let saved = $state<Record<string, Pt[]>>({});           // rettede punkter pr. type
  let savedFlow = $state<Record<string, FlowDef>>({});    // rettede ind/ud-definitioner pr. type (v4.13.0)
  let portsDirty = $state(false);
  let flowDirty = $state(false);
  const dirty = $derived(portsDirty || flowDirty);
  // svelte-ignore state_referenced_locally
  let tab = $state<SymbolTab>(parseSymbolRoute(route).tab ?? 'punkter');
  // svelte-ignore state_referenced_locally
  let organize = $state(route === 'symbols/organiser');
  let category = $state<SymbolCategory | typeof OWN_SECTION | 'alle'>('alle');
  let search = $state('');
  const all = $derived(defs());
  let selectedId = $state(defs()[0].id);
  let busy = $state(false);
  let error = $state('');
  let info = $state('');
  let renaming = $state(false);
  let renameText = $state('');
  let renameHint = $state('');

  const def = $derived(all.find((s) => s.id === selectedId) ?? all[0]);
  const type = $derived(symbolType(def.id) as string);
  const own = $derived(isOwnSymbol(def.id));
  const ownRow = $derived(library.own.find((s) => s.type === def.id));
  const secs = $derived(sections(library.layout));
  const secOf = $derived(secs.find((s) => symbolsIn(all, library.layout, s.id).some((d) => d.id === def.id))?.id ?? '');
  const list = $derived(all.filter((s) =>
    (category === 'alle' || s.category === category) && (!search.trim() || s.label.toLowerCase().includes(search.trim().toLowerCase()))));

  const removeLeaveGuard = setLeaveGuard(async () => !dirty || await ask('Du har ændringer, der ikke er gemt. Kassér dem og forlad siden?', { ok: 'Kassér og forlad', danger: true }));
  onDestroy(removeLeaveGuard);

  onMount(async () => {
    await loadLibrary();   // egne symboler kan også have rettede punkter
    try {
      saved = await get<Record<string, Pt[]>>('/api/symbol-ports');
    } catch (e) {
      error = `Kunne ikke hente de rettede punkter: ${(e as Error).message}`;
    }
    try {
      savedFlow = await get<Record<string, FlowDef>>('/api/symbol-flow');
    } catch (e) {
      console.error('De rettede ind/ud-definitioner kunne ikke hentes — standarderne vises', e);
    }
    // åbnet fra Tegn: vis tegningens navn på tilbage-knappen
    if (from.drawing) {
      try {
        backName = (await get<{ id: string; name: string }[]>('/api/drawings')).find((d) => d.id === from.drawing)?.name ?? '';
      } catch { /* knappen viser så bare "tegningen" */ }
    }
    const start = from.type ? defs().find((x) => symbolType(x.id) === from.type || x.id === from.type) : null;
    if (start) selectedId = start.id;
    if (!organize) syncHash();
  });

  // En ny adresse udefra (link fra Tegn, Tilbage i browseren): følg den. Siden skriver selv kun med replaceState, så dens egne
  // skift kommer ikke igennem her.
  let lastRoute = '';
  $effect(() => {
    const r = route;
    if (r === lastRoute) return;
    const first = lastRoute === '';
    lastRoute = r;
    if (first) return;          // første gang: onMount tager sig af det
    organize = r === 'symbols/organiser';
    const p = parseSymbolRoute(r);
    if (p.tab) tab = p.tab;
    const hit = p.type ? defs().find((x) => symbolType(x.id) === p.type || x.id === p.type) : null;
    if (hit) selectedId = hit.id;
    backName = '';
    if (p.drawing) {
      const want = p.drawing;
      get<{ id: string; name: string }[]>('/api/drawings')
        .then((ds) => { if (parseSymbolRoute(route).drawing === want) backName = ds.find((d) => d.id === want)?.name ?? ''; })
        .catch(() => { /* knappen viser så bare "tegningen" */ });
    }
  });

  /** Det valgte symbol og fanen står i adressen (kan bogmærkes, og Tilbage i browseren virker). */
  function syncHash(): void {
    const want = panelHref(from.drawing, from.fromDraw, type, tab);
    if (location.hash !== want) history.replaceState(null, '', want);
  }

  async function mayDiscard(): Promise<boolean> {
    if (!dirty) return true;
    if (!(await ask('Du har ændringer, der ikke er gemt. Kassér dem?', { ok: 'Kassér', danger: true }))) return false;
    portsDirty = flowDirty = false;
    return true;
  }
  async function choose(id: string): Promise<void> {
    if (id === selectedId || !(await mayDiscard())) return;
    selectedId = id;
    renaming = false;
    error = info = '';
    syncHash();
  }
  async function setTab(t: SymbolTab): Promise<void> {
    if (t === tab || !(await mayDiscard())) return;
    tab = t;
    syncHash();
  }
  async function setOrganize(on: boolean): Promise<void> {
    if (on && !(await mayDiscard())) return;
    organize = on;
    if (!on) syncHash();
  }

  async function back(): Promise<void> {
    if (!(await mayDiscard())) return;
    location.hash = drawHref(from.drawing);
  }

  async function run(f: () => Promise<void>): Promise<void> {
    busy = true;
    error = info = '';
    try {
      await f();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }
  const doEdit = () => run(async () => {
    if (!(await mayDiscard())) return;
    await editGraphic(def.id, def.label);
  });
  const saveName = () => run(async () => {
    await updateOwn(def.id, renameText.trim(), renameHint.trim());
    renaming = false;
    info = 'Navnet er gemt';
  });
  const remove = () => run(async () => {
    if (!(await ask(`Slet "${def.label}" fra biblioteket? Tegninger, der bruger det, beholder deres kopi.`, { ok: 'Slet symbol', danger: true }))) return;
    const label = def.label;
    const used = await deleteOwn(def.id);
    selectedId = defs()[0].id;
    syncHash();
    info = `"${label}" er slettet.${used.length ? ` Det står stadig i ${used.length} tegning${used.length === 1 ? '' : 'er'} — som en kopi.` : ''}`;
  });
  const moveTo = (section: string) => run(async () => {
    try {
      await saveLayout(moveSymbol(all, library.layout, def.id, section, 100000));
      info = `Flyttet til ${secs.find((s) => s.id === section)?.label ?? section}`;
    } catch (e) {
      await loadLibrary();      // samtidig ændring: hent biblioteket igen
      throw e;
    }
  });

  /** Forhåndsvisningen tilpasses symbolets egen størrelse (getBBox). */
  function fit(node: SVGSVGElement, _svg: string) {
    const go = () => {
      try {
        const b = (node.firstElementChild as SVGGraphicsElement).getBBox();
        const pad = Math.max(b.width, b.height) * 0.08 + 2, size = Math.max(b.width, b.height) + 2 * pad;
        node.setAttribute('viewBox', `${b.x + b.width / 2 - size / 2} ${b.y + b.height / 2 - size / 2} ${size} ${size}`);
      } catch { /* ikke tegnet endnu — standardvinduet bruges */ }
    };
    go();
    return { update: go };
  }
</script>

<div class="row title">
  <h2>Symboler</h2>
  {#if organize}
    <button onclick={() => setOrganize(false)}>← Til symbolerne</button>
  {:else}
    <button onclick={() => setOrganize(true)} title="Sektioner, rækkefølge, flere symboler ad gangen, import og eksport">Organisér bibliotek …</button>
  {/if}
  {#if from.fromDraw}<button class="back" onclick={back}>← Tilbage til {backName ? `"${backName}"` : 'tegningen'}</button>{/if}
</div>

{#if organize}
  <p class="muted small">Organisér symbolbiblioteket, som det vises i <a href="#draw">Tegn</a>: egne sektioner, rækkefølge og hvilke symboler der står
    hvor. Egne symboler kan omdøbes og slettes, og SVG-filer og bibliotekspakker kan importeres.</p>
  <div class="org"><SymbolLibrary onopen={(id) => { selectedId = id; organize = false; syncHash(); }} /></div>
{:else}
<div class="layout">
  <aside class="panel">
    <input placeholder="Søg symbol" bind:value={search} aria-label="Søg symbol" />
    <select bind:value={category} aria-label="Kategori">
      <option value="alle">Alle kategorier</option>
      {#each CATEGORIES as c}<option value={c.id}>{c.label}</option>{/each}
      <option value={OWN_SECTION}>{OWN_LABEL}</option>
    </select>
    <ul class="list">
      {#each list as s (s.id)}
        {@const t = symbolType(s.id) as string}
        <li>
          <button class:on={s.id === selectedId} onclick={() => choose(s.id)}>
            <span class="nm">{s.label}</span>
            <span class="tags">
              {#if isOwnSymbol(s.id)}<span class="tag own" title="Eget symbol">eget</span>{/if}
              {#if saved[t]}<span class="tag" title="Tilslutningspunkterne er rettet">punkter</span>{/if}
              {#if savedFlow[t]}<span class="tag" title="Ind/ud og veje er rettet">ind/ud</span>{:else if FLOW_DEFAULTS[t]}<span class="tag std" title="Har en standard-definition af ind/ud">ind/ud</span>{/if}
            </span>
          </button>
        </li>
      {/each}
    </ul>
  </aside>

  <section class="panel edit">
    <div class="head">
      <svg class="pv" viewBox="0 0 100 100" aria-hidden="true" use:fit={def.svg}>{@html def.svg}</svg>
      <div class="who">
        {#if renaming}
          <input bind:value={renameText} maxlength="40" aria-label="Symbolets navn" />
          <input bind:value={renameHint} maxlength="200" placeholder="Forklaring" aria-label="Forklaring" />
          <div class="row acts"><button class="primary" onclick={saveName} disabled={busy || !renameText.trim()}>Gem</button>
            <button onclick={() => (renaming = false)}>Annullér</button></div>
        {:else}
          <h3>{def.label} {#if own && ownRow}<span class="tag own">eget · v{ownRow.version}</span>{/if}</h3>
          <div class="muted small">{def.hint}</div>
          <div class="row acts">
            <button onclick={doEdit} disabled={busy} title={own ? 'Ret grafikken i Tegn og gem den som ny version' : 'Indbygget: ret en kopi i Tegn og gem den som eget symbol'}>Redigér grafik</button>
            {#if own && ownRow}
              <button onclick={() => { renaming = true; renameText = ownRow.label; renameHint = ownRow.hint; }} disabled={busy}>Omdøb</button>
              <button class="danger" onclick={remove} disabled={busy}>Slet</button>
            {/if}
            <select aria-label="Flyt {def.label} til sektion" disabled={busy || !secs.length} value={secOf}
                    onchange={(e) => moveTo(e.currentTarget.value)} title="Hvilken sektion symbolet står i, i Tegns bibliotek">
              {#each secs as s (s.id)}<option value={s.id}>{s.id === secOf ? `Sektion: ${s.label}` : `Flyt til ${s.label}`}</option>{/each}
            </select>
          </div>
        {/if}
      </div>
    </div>
    {#if error}<p class="error" role="alert">{error}</p>{/if}
    {#if info}<p class="notice">{info}</p>{/if}

    <div class="tabs" role="tablist">
      <button role="tab" aria-selected={tab === 'punkter'} class:on={tab === 'punkter'} onclick={() => setTab('punkter')}>Tilslutningspunkter</button>
      <button role="tab" aria-selected={tab === 'veje'} class:on={tab === 'veje'} onclick={() => setTab('veje')}
              title="Ind/ud, navne og veje på punkterne, tilstande og flow-rolle">Ind/ud og veje</button>
    </div>
    <div class="tabbody">
      {#key def.id + tab}
        {#if tab === 'punkter'}
          <PortsEditor {def} bind:saved typePorts={typePortMap(mergeDefs(savedFlow))[type] ?? []} ondirty={(d) => (portsDirty = d)} />
        {:else}
          <SymbolFlowEditor svg={def.svg} label={def.label} {type} custom={savedFlow[type]} ondirty={(d) => (flowDirty = d)}
            onsaved={(t, d) => { if (d) savedFlow = { ...savedFlow, [t]: d }; else { const { [t]: _g, ...rest } = savedFlow; savedFlow = rest; } }} />
        {/if}
      {/key}
    </div>
  </section>
</div>
{/if}

<style>
  .title { align-items: center; gap: 1rem; flex-wrap: wrap; }
  .title h2 { margin: 0; }
  .back { margin-left: auto; }
  /* v6.11.0 (Jan: "knapperne er helt yderst i view-boksen"): listen og panelet har en fast bredde — knapperne står ved det, de hører til */
  .layout { display: grid; grid-template-columns: 18rem minmax(0, 62rem); gap: 1rem; align-items: start; justify-content: start; }
  @media (max-width: 800px) { .layout { grid-template-columns: 1fr; } }
  .org { max-width: 80rem; }
  aside { display: flex; flex-direction: column; gap: .4rem; max-height: 78vh; }
  .list { list-style: none; margin: 0; padding: 0; overflow-y: auto; }
  .list button { width: 100%; text-align: left; border: 0; background: transparent; padding: 4px 6px; border-radius: 4px; display: flex; justify-content: space-between; gap: .5rem; align-items: center; }
  .list button:hover { background: #eef2f8; }
  .list button.on { background: #dbe8ff; }
  .list .nm { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .tags { display: inline-flex; gap: 3px; flex: none; }
  .tag { font-size: .7rem; padding: 0 6px; border-radius: 8px; background: #e7f3e8; color: #2e7d32; border: 1px solid #a9d3ab; }
  .tag.std { background: #eceff1; color: #546e7a; border-color: #cfd8dc; }
  .tag.own { background: #ede7f6; color: #4527a0; border-color: #c5b6e8; }
  .head { display: flex; gap: .8rem; align-items: flex-start; margin-bottom: .4rem; }
  .pv { width: 84px; height: 84px; flex: none; background: #f6f6f6; border: 1px solid var(--line); border-radius: 6px; }
  .who { display: flex; flex-direction: column; gap: .25rem; min-width: 0; }
  .who h3 { margin: 0; }
  .who input { max-width: 26rem; }
  .acts { gap: .4rem; flex-wrap: wrap; align-items: center; }
  .acts select { width: auto; }
  .tabs { display: flex; gap: 2px; margin-top: .6rem; border-bottom: 1px solid var(--line); }
  .tabs button { border-radius: 6px 6px 0 0; border-bottom: 0; }
  .tabs button.on { background: #dbe8ff; font-weight: 600; }
  .tabbody { padding-top: .5rem; }
</style>
