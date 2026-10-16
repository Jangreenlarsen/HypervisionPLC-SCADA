<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { get, patch, post } from '../lib/api';
  import { availableHeight, onLayoutChange } from '../lib/canvas';
  import { deleteDrawingFlow } from '../lib/drawingDelete';
  import SymbolGuide from '../lib/SymbolGuide.svelte';
  import SymbolReplace, { type ReplaceOptions } from '../lib/SymbolReplace.svelte';
  import type { SelectionInfo } from '../lib/symbolSuggest';
  import { CATEGORIES, PIPE_IDS, previewViewBox, SYMBOLS, selectorSymbol, withName, type SymbolDef } from '../lib/symbols';

  let { route = 'draw' }: { route?: string } = $props();

  interface Version { version: number; comment: string; created_at: number }
  interface Detail { id: string; name: string; active_version: number; versions: Version[] }
  interface Report { removed_elements: Record<string, number>; removed_attributes: Record<string, number>; element_count: number; orphaned_bindings?: string[] }
  interface Sel { id: string; tag: string; interactive?: boolean; name?: string; desc?: string; children?: number }
  interface ScadaApi {
    ready: Promise<void>;
    load(svg: string): boolean;
    newDrawing(w: number, h: number): void;
    getSvg(): string;
    onSelection(fn: (sel: Sel[]) => void): void;
    onChange(fn: () => void): void;
    setSelectedId(id: string): string;
    setSelectedText(attr: 'data-hv-name' | 'data-hv-desc', value: string): string;
    uniqueName(base: string): string;
    insertSymbol(fragment: string, baseId: string): string;
    setGuides(opts: { grid: boolean; snapGrid: boolean; snapObjects: boolean; step: number }): void;
    describeSelection(): SelectionInfo | null;
    replaceSelected(fragment: string, baseId: string, opts: { name?: string; namePrefix?: string; keepId?: boolean; stretch?: boolean; useText?: boolean; similar?: false | 'same' | 'any'; protectIds?: string[]; apexNative?: number; mirror?: boolean }):
      { ok?: boolean; replaced?: number; skipped?: number; ids?: string[]; error?: string };
    ungroupSelected(): string;
  }

  let drawings = $state<{ id: string; name: string }[]>([]);
  let current = $state<Detail | null>(null); // null = ny, ikke gemt tegning
  let loadedVersion = $state<number | null>(null);
  let newName = $state('');
  let comment = $state('');
  let selection = $state<Sel[]>([]);
  let idInput = $state('');
  let nameInput = $state('');
  let dirty = $state(false);
  let busy = $state(false);
  let error = $state('');
  let info = $state('');
  let report = $state<Report | null>(null);
  let ready = $state(false);
  // Tegnehjælp: gitter, fang til gitter/objekter. Huskes pr. browser (ikke pr. tegning).
  const GUIDE_STEPS = [5, 10, 20, 25, 50];
  function loadGuides(): { grid: boolean; snapGrid: boolean; snapObjects: boolean; step: number } {
    const fallback = { grid: false, snapGrid: false, snapObjects: false, step: 10 };
    try {
      const raw = JSON.parse(localStorage.getItem('draw.guides') ?? '{}');
      return { grid: !!raw.grid, snapGrid: !!raw.snapGrid, snapObjects: !!raw.snapObjects, step: GUIDE_STEPS.includes(Number(raw.step)) ? Number(raw.step) : 10 };
    } catch {
      return fallback; // ingen eller ødelagt localStorage: standardværdier
    }
  }
  let guides = $state(loadGuides());
  $effect(() => {
    const g = $state.snapshot(guides);
    if (ready && ed) ed.setGuides(g);
    try {
      localStorage.setItem('draw.guides', JSON.stringify(g));
    } catch {
      // localStorage kan være blokeret (privat vindue): hjælpen virker stadig, den huskes bare ikke
    }
  });
  let guideFor = $state<{ id: string; name: string } | null>(null); // symbol-guiden (6 trin) er åben
  let tags = $state<{ name: string; source: string; unit: string; writable: boolean; plc: string }[]>([]);
  let iframe: HTMLIFrameElement;
  let ed: ScadaApi | null = null;

  async function connect(): Promise<void> {
    const win = iframe.contentWindow as (Window & { scada?: ScadaApi }) | null;
    // Vent på at værtssiden har lavet window.scada
    for (let i = 0; i < 200 && !win?.scada; i++) await new Promise((r) => setTimeout(r, 50));
    if (!win?.scada) {
      error = 'Tegne-editoren kunne ikke indlæses';
      return;
    }
    ed = win.scada;
    await ed.ready;
    ed.onSelection((sel) => {
      selection = sel;
      idInput = sel.length === 1 ? sel[0].id : '';
      nameInput = sel.length === 1 ? sel[0].name ?? '' : '';
    });
    ed.onChange(() => (dirty = true));
    ready = true;
    const fromRoute = route.split('/')[1];
    if (fromRoute && drawings.some((d) => d.id === fromRoute)) await open(fromRoute);
    else startNew(true);
  }

  function confirmDiscard(): boolean {
    return !dirty || confirm('Der er ændringer der ikke er gemt. Kassér dem?');
  }

  function startNew(force = false): void {
    if (!ed || (!force && !confirmDiscard())) return;
    ed.newDrawing(1200, 700);
    current = null;
    loadedVersion = null;
    newName = '';
    dirty = false;
    report = null;
    info = '';
    history.replaceState(null, '', '#draw');
  }

  async function open(id: string, version?: number): Promise<void> {
    if (!ed || !confirmDiscard()) return;
    error = info = '';
    report = null;
    try {
      const detail = await get<Detail>(`/api/drawings/${encodeURIComponent(id)}`);
      const v = version ?? detail.active_version;
      const resp = await fetch(`/api/drawings/${encodeURIComponent(id)}/svg?version=${v}`);
      if (!resp.ok) throw new Error(`Kunne ikke hente SVG (HTTP ${resp.status})`);
      if (!ed.load(await resp.text())) throw new Error('SVG-Edit kunne ikke læse tegningen');
      current = detail;
      loadedVersion = v;
      dirty = false;
      history.replaceState(null, '', `#draw/${id}`);
    } catch (e) {
      error = (e as Error).message;
    }
  }

  /**
   * Opsæt det valgte symbol med guiden (6 trin). Guiden arbejder på tegningens AKTIVE version, så tegningen
   * gemmes og udgives først, hvis den er ny eller har ændringer.
   */
  async function openGuide(): Promise<void> {
    const sel = selection.length === 1 ? selection[0] : null;
    if (!ed || !sel?.name) return;
    error = '';
    const published = current !== null && !dirty && loadedVersion === current.active_version;
    if (!published) {
      if (!current && !newName.trim()) {
        error = 'Giv tegningen et navn (nederst i panelet) — den skal gemmes, før symbolet kan opsættes';
        return;
      }
      if (!confirm('Tegningen gemmes og udgives først, så symbolet kan opsættes. Fortsæt?')) return;
      await save(true);
      if (error || dirty || !current) return; // save() har vist fejlen
    }
    try {
      if (!tags.length) tags = await get('/api/tags');
    } catch (e) {
      error = (e as Error).message;
      return;
    }
    guideFor = { id: sel.id, name: sel.name };
  }

  // ---- Erstat med symbol (tegnet del → bibliotekssymbol)
  let replaceInfo = $state<SelectionInfo | null>(null);
  let replaceLost = $state({ own: 0, similarBound: 0 });
  let boundIds: string[] = [];        // elementer med bindinger i den gemte version — lignende dele med dem springes over

  async function openReplace(): Promise<void> {
    if (!ed) return;
    error = info = '';
    const d = ed.describeSelection();
    if (!d) {
      error = 'Vælg mindst ét element at erstatte';
      return;
    }
    // Bindinger på delens underelementer følger ikke med (kun på selve delen, hvis id'et beholdes)
    let lost = { own: 0, similarBound: 0 };
    boundIds = [];
    if (current) {
      try {
        const view = await get<{ bindings: { element: string }[] }>(`/api/drawings/${encodeURIComponent(current.id)}/view`);
        const own = new Set(d.ids);
        const bound = new Set(view.bindings.map((b) => b.element));
        boundIds = [...bound];
        // selve delens id følger med (hvis id'et beholdes); alt andet — underelementer og tekster der fjernes — gør ikke
        lost = {
          own: view.bindings.filter((b) => own.has(b.element) && b.element !== d.id).length,
          similarBound: d.similarGroups.filter((ids) => ids.some((id) => bound.has(id))).length,
        };
      } catch (e) {
        error = `Bindinger kunne ikke kontrolleres: ${(e as Error).message}`;
      }
    }
    replaceLost = lost;
    replaceInfo = d;
  }

  function doReplace(o: ReplaceOptions): void {
    if (!ed) return;
    const res = ed.replaceSelected(withName(o.symbol.svg, o.name || o.symbol.label), o.symbol.id,
      { name: o.name || o.symbol.label, namePrefix: o.symbol.label, keepId: o.keepId, stretch: o.stretch, useText: o.useText, similar: o.similar, protectIds: boundIds, apexNative: o.apexNative, mirror: o.mirror });
    replaceInfo = null;
    if (res.error) {
      error = res.error;
      return;
    }
    dirty = true;
    const skipped = res.skipped ? ` ${res.skipped} lignende del${res.skipped === 1 ? '' : 'e'} med bindinger blev sprunget over — erstat dem enkeltvis, hvis de også skal erstattes.` : '';
    info = `${res.replaced} del${res.replaced === 1 ? '' : 'e'} er erstattet med «${o.symbol.label}».${skipped} Ctrl+Z fortryder det i ét trin. Tryk Gem kladde, når du er tilfreds — Overview viser først ændringen, når du udgiver versionen.`;
  }

  function ungroup(): void {
    if (!ed) return;
    const err = ed.ungroupSelected();
    if (err) error = err;
    else {
      error = '';
      dirty = true;
      info = 'Gruppen er opløst — dens dele kan nu vælges enkeltvis.';
    }
  }

  /** Slet den åbne tegning (alle versioner og bindinger) — efter en bekræftelse der viser hvad det rammer. */
  async function removeCurrent(): Promise<void> {
    if (!current) return;
    error = info = '';
    const { id, name } = current;
    try {
      if (!(await deleteDrawingFlow(id))) return;
      drawings = await get<{ id: string; name: string }[]>('/api/drawings');
      startNew(true); // tegningen findes ikke mere — tilbage til en tom, ny tegning
      info = `Tegningen "${name}" er slettet.`;
    } catch (e) {
      error = (e as Error).message;
    }
  }

  async function save(publish: boolean): Promise<void> {
    if (!ed) return;
    error = info = '';
    report = null;
    busy = true;
    try {
      const svg = ed.getSvg();
      if (!current) {
        if (!newName.trim()) throw new Error('Giv tegningen et navn');
        const res = await post<{ drawing: Detail; report: Report }>('/api/drawings', { name: newName.trim(), svg, comment });
        current = res.drawing;
        loadedVersion = res.drawing.active_version;
        report = res.report;
        info = `Tegningen "${res.drawing.name}" er oprettet og udgivet som version 1.`;
        history.replaceState(null, '', `#draw/${res.drawing.id}`);
      } else {
        const res = await post<{ drawing: Detail; version: number; report: Report }>(
          `/api/drawings/${encodeURIComponent(current.id)}/versions`, { svg, comment, activate: publish });
        current = res.drawing;
        loadedVersion = res.version;
        report = res.report;
        info = publish ? `Version ${res.version} er gemt og udgivet — Overview viser den nu.`
          : `Version ${res.version} er gemt som kladde. Overview viser stadig version ${res.drawing.active_version}.`;
      }
      comment = '';
      dirty = false;
      drawings = await get<{ id: string; name: string }[]>('/api/drawings');
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  async function publishLoaded(): Promise<void> {
    if (!current || loadedVersion === null) return;
    try {
      current = await patch<Detail>(`/api/drawings/${encodeURIComponent(current.id)}`, { active_version: loadedVersion });
      info = `Version ${loadedVersion} er nu udgivet.`;
    } catch (e) {
      error = (e as Error).message;
    }
  }

  function applyId(id: string): void {
    if (!ed || !id) return;
    const err = ed.setSelectedId(id);
    if (err) error = err;
    else {
      error = '';
      dirty = true;
    }
  }

  /** Navn på det valgte element — gemmes i tegningen og er symbolets identitet under Bindinger (resten konfigureres dér). */
  function applyText(attr: 'data-hv-name' | 'data-hv-desc', value: string): void {
    if (!ed) return;
    const err = ed.setSelectedText(attr, value);
    if (err) error = err;
    else {
      error = '';
      dirty = true;
    }
  }

  let symbolFilter = $state('');
  const symbolsIn = (cat: string): SymbolDef[] => {
    const q = symbolFilter.trim().toLowerCase();
    return SYMBOLS.filter((s) => s.category === cat && (!q || s.label.toLowerCase().includes(q) || s.hint.toLowerCase().includes(q)));
  };

  /** Forhåndsvisning: viewBox efter symbolets egen størrelse, så små og store symboler fylder knappen ens. */
  /** Rør og fittings vises i samme målestok, så rørtykkelsen ser ens ud på tværs af knapperne. */
  const fitPreview = (id: string) => (svg: SVGSVGElement): void => {
    try {
      const b = (svg.firstElementChild as SVGGraphicsElement).getBBox();
      svg.setAttribute('viewBox', previewViewBox(b, PIPE_IDS.has(id)));
    } catch {
      // getBBox kan fejle hvis knappen er skjult — standard-viewBox bruges så
    }
  };

  let selectorLabels = $state('Hånd, 0, Auto');
  let selectorError = $state('');

  /** Omskifter med de positioner brugeren har skrevet (2-8, adskilt med komma). */
  function insertSelector(): void {
    selectorError = '';
    try {
      const svg = selectorSymbol(selectorLabels.split(','));
      if (!ed) return;
      ed.insertSymbol(withName(svg, ed.uniqueName('Omskifter')), 'omskifter');
      dirty = true;
      info = 'Omskifteren er indsat — tryk "Opsæt symbol (6 trin)" i panelet til højre for at koble den til PLC\'en.';
    } catch (e) {
      selectorError = (e as Error).message;
    }
  }

  function insert(symbolId: string): void {
    const s = SYMBOLS.find((x) => x.id === symbolId);
    if (!ed || !s) return;
    ed.insertSymbol(withName(s.svg, ed.uniqueName(s.label)), s.id);
    dirty = true;
    info = 'Symbolet er indsat — tryk "Opsæt symbol (6 trin)" i panelet til højre for at sætte tag, positioner og animationer.';
  }

  const onBeforeUnload = (e: BeforeUnloadEvent) => {
    if (dirty) e.preventDefault();
  };

  // Tegne-editoren fylder højden ned til sidefoden (mindst 600 px, så hele SVG-Edits værktøjslinje ses — ellers scrolles siden)
  const fitFrame = () => {
    if (iframe) iframe.style.height = `${Math.max(600, availableHeight(iframe) - 2)}px`;
  };
  let stopLayout: (() => void) | null = null;

  onMount(async () => {
    window.addEventListener('beforeunload', onBeforeUnload);
    fitFrame();
    stopLayout = onLayoutChange(fitFrame);
    try {
      drawings = await get<{ id: string; name: string }[]>('/api/drawings');
    } catch (e) {
      error = (e as Error).message;
    }
  });
  onDestroy(() => {
    window.removeEventListener('beforeunload', onBeforeUnload);
    stopLayout?.();
  });

  const single = $derived(selection.length === 1 ? selection[0] : null);
  const isActive = $derived(current !== null && loadedVersion === current.active_version);
  const entries = (o: Record<string, number>) => Object.entries(o).map(([k, v]) => `${k} ×${v}`).join(', ');
</script>

<div class="row toolbar">
  <select value={current?.id ?? ''} onchange={(e) => { const v = (e.currentTarget as HTMLSelectElement).value; if (v) open(v); else startNew(); }} aria-label="Tegning" disabled={!ready}>
    <option value="">— Ny tegning —</option>
    {#each drawings as d}<option value={d.id}>{d.name}</option>{/each}
  </select>
  {#if current}
    <select value={loadedVersion} onchange={(e) => current && open(current.id, Number((e.currentTarget as HTMLSelectElement).value))} aria-label="Version">
      {#each current.versions as v}
        <option value={v.version}>v{v.version}{v.version === current.active_version ? ' (udgivet)' : ' (kladde)'}{v.comment ? ` — ${v.comment}` : ''}</option>
      {/each}
    </select>
    {#if !isActive}<button onclick={publishLoaded}>Udgiv denne version</button>{/if}
  {:else}
    <input bind:value={newName} placeholder="Navn på ny tegning" maxlength="80" />
  {/if}
  <input bind:value={comment} placeholder="Kommentar til versionen" maxlength="200" class="comment" />
  {#if current}
    <button onclick={() => save(false)} disabled={busy || !ready}>Gem kladde</button>
    <button class="primary" onclick={() => save(true)} disabled={busy || !ready}>Gem og udgiv</button>
    <a class="btn" href={'#editor/' + current.id}>Bindinger</a>
    <button class="danger" onclick={removeCurrent} disabled={busy || !ready} title="Slet tegningen med alle versioner og bindinger">Slet tegning</button>
  {:else}
    <button class="primary" onclick={() => save(true)} disabled={busy || !ready}>Opret tegning</button>
  {/if}
  {#if dirty}<span class="badge">ikke gemt</span>{/if}
</div>

<div class="row guides small" role="group" aria-label="Tegnehjælp">
  <strong>Tegnehjælp</strong>
  <label class="opt"><input type="checkbox" bind:checked={guides.grid} /> Vis gitter</label>
  <label class="opt"><input type="checkbox" bind:checked={guides.snapGrid} /> Fang til gitter</label>
  <label class="opt">Gitterafstand
    <select bind:value={guides.step} aria-label="Gitterafstand">{#each GUIDE_STEPS as s}<option value={s}>{s}</option>{/each}</select>
  </label>
  <label class="opt" title="Når du slipper et objekt, lægges det kant mod kant eller midte mod midte med nærmeste objekt, hvis det er tæt på"><input type="checkbox" bind:checked={guides.snapObjects} /> Fang til objekter</label>
  <span class="muted">Rotation sker i 15°-trin — hold <kbd>Shift</kbd> nede for fri rotation</span>
</div>

{#if error}<div class="error">{error}</div>{/if}
{#if info}
  <div class="notice">
    {info}
    {#if report && (Object.keys(report.removed_elements).length || Object.keys(report.removed_attributes).length)}
      <br /><span class="small muted">Renset ved gem: {entries(report.removed_elements)} {entries(report.removed_attributes)}</span>
    {/if}
    {#if report?.orphaned_bindings?.length}<br />Bindinger uden element nu: {report.orphaned_bindings.join(', ')}{/if}
  </div>
{/if}

<div class="layout">
  <iframe bind:this={iframe} src="/svgedit/scada-editor.html" title="Tegne-editor" onload={connect}></iframe>

  <aside>
    <section class="panel">
      <h3>Valgt element</h3>
      {#if !single}
        <p class="muted small">{selection.length > 1 ? `${selection.length} elementer valgt` : 'Vælg et element i tegningen.'}</p>
        {#if selection.length > 1}
          <div class="row"><button onclick={openReplace} disabled={!ready || busy} title="Erstat de valgte dele samlet med ét symbol — fx en ventil tegnet af flere løse figurer">Erstat markeringen med symbol …</button></div>
        {/if}
      {:else}
        <p class="small muted">&lt;{single.tag}&gt;</p>
        <label class="field">Navn
          <input bind:value={nameInput} maxlength="60" placeholder="fx Ventilator stue"
            onchange={() => applyText('data-hv-name', nameInput)} />
        </label>
        {#if single.name}
          <div class="row"><button class="primary" onclick={openGuide} disabled={busy || !ready}>Opsæt symbol (6 trin)</button></div>
          <p class="small muted">Tag, positioner, animationer og nøglelås sættes i guiden — samme guide findes under <strong>Bindinger</strong>.{!current || dirty ? ' Tegningen gemmes og udgives først.' : ''}</p>
        {:else}
          <p class="small muted">Giv elementet et <strong>navn</strong> for at gøre det til et symbol, der kan konfigureres under <strong>Bindinger</strong>. Uden navn er det kun tegning.</p>
        {/if}
        {#if single.tag === 'g' && !single.name && (single.children ?? 0) > 20}
          <p class="small notice">Denne gruppe har {single.children} dele. Opløs den for at vælge delene enkeltvis, så de kan erstattes med symboler.</p>
          <div class="row"><button onclick={ungroup} disabled={!ready}>Opløs gruppen</button></div>
        {/if}
        <div class="row"><button onclick={openReplace} disabled={!ready || busy} title="Erstat den tegnede del med et symbol fra biblioteket (samme placering, størrelse og drejning)">Erstat med symbol …</button></div>
        <details class="adv">
          <summary class="small">Avanceret</summary>
          <label class="field">Id (teknisk)
            <span class="row"><input bind:value={idInput} /><button onclick={() => applyId(idInput.trim())} disabled={!idInput.trim() || idInput === single.id}>Sæt</button></span>
          </label>
        </details>
      {/if}
    </section>

    <section class="panel">
      <h3>Symboler</h3>
      <input bind:value={symbolFilter} placeholder="Søg symbol (fx bøjning, kontaktor)" style="width:100%" />
      {#each CATEGORIES as cat (cat.id)}
        {@const list = symbolsIn(cat.id)}
        {#if list.length}
          <details open>
            <summary>{cat.label} <span class="muted small">({list.length})</span></summary>
            <div class="symbols">
              {#each list as s (s.id)}
                <button onclick={() => insert(s.id)} disabled={!ready} title={s.hint}>
                  <svg viewBox="-4 -4 168 152" aria-hidden="true" {@attach fitPreview(s.id)}>{@html s.svg}</svg>
                  <span>{s.label}</span>
                </button>
              {/each}
            </div>
            {#if cat.id === 'betjening'}
              <div class="selector-cfg">
                <label class="small">Omskifter med egne positioner (2-8, komma imellem)
                  <span class="row"><input bind:value={selectorLabels} placeholder="fx 1, 2, 3, 4" />
                    <button onclick={insertSelector} disabled={!ready}>Indsæt</button></span>
                </label>
                {#if selectorError}<p class="small error">{selectorError}</p>{/if}
                <p class="small muted">Værdierne bliver 0, 1, 2 … i rækkefølge — kan rettes under Bindinger.</p>
              </div>
            {/if}
          </details>
        {/if}
      {/each}
      {#if CATEGORIES.every((c) => !symbolsIn(c.id).length)}<p class="small muted">Ingen symboler matcher "{symbolFilter}".</p>{/if}
      <p class="small muted">Symbolerne er grå i normaltilstand (ISA-101). Farve og animation kommer fra bindingerne.</p>
    </section>
  </aside>
</div>

{#if replaceInfo}
  <SymbolReplace info={replaceInfo} lostBindings={replaceLost} onreplace={doReplace} onclose={() => (replaceInfo = null)} />
{/if}

{#if guideFor && current}
  <SymbolGuide drawingId={current.id} element={guideFor.id} name={guideFor.name} {tags}
    onclose={() => (guideFor = null)}
    onsaved={() => { info = `Symbolet "${guideFor?.name ?? ''}" er opsat.`; guideFor = null; }} />
{/if}

<style>
  .toolbar { margin-bottom: .35rem; }
  .guides { margin-bottom: .6rem; flex-wrap: wrap; gap: .3rem 1rem; align-items: center; }
  .guides kbd { border: 1px solid var(--line); border-bottom-width: 2px; border-radius: 3px; padding: 0 .3rem; background: var(--panel-2); font-size: .85em; }
  .comment { flex: 1; min-width: 12rem; }
  .layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 280px;
    gap: 1rem;
    align-items: start;
  }
  @media (max-width: 900px) { .layout { grid-template-columns: minmax(0, 1fr); } }
  iframe {
    width: 100%;
    height: 600px; /* sættes af fitFrame */
    display: block;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: #fff;
  }
  aside { min-width: 0; }
  .field { display: flex; flex-direction: column; gap: .25rem; font-size: .85rem; color: var(--muted); margin-bottom: .5rem; }
  .field :global(select), .field input { width: 100%; }
  /* minmax(0, 1fr): lange navne må ikke gøre en kolonne bredere end panelet */
  .symbols { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .4rem; }
  .symbols button { min-width: 0; }
  .symbols span { max-width: 100%; overflow-wrap: anywhere; hyphens: auto; text-align: center; }
  .symbols button { display: flex; flex-direction: column; align-items: center; gap: .2rem; padding: .3rem; font-size: .72rem; line-height: 1.15; }
  details { margin-top: .6rem; }
  .adv { margin-top: .8rem; }
  .selector-cfg { margin-top: .5rem; }
  .selector-cfg input { flex: 1; min-width: 0; }
  summary { cursor: pointer; font-weight: 600; font-size: .9rem; margin-bottom: .4rem; }
  .symbols svg { width: 44px; height: 40px; }
</style>
