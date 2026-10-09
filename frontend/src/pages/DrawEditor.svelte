<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { get, patch, post } from '../lib/api';
  import { availableHeight, onLayoutChange } from '../lib/canvas';
  import { CATEGORIES, SYMBOLS, selectorSymbol, withName, type SymbolDef } from '../lib/symbols';
  import TagSelect, { type TagOption } from '../lib/TagSelect.svelte';

  let { route = 'draw' }: { route?: string } = $props();

  interface Version { version: number; comment: string; created_at: number }
  interface Detail { id: string; name: string; active_version: number; versions: Version[] }
  interface Report { removed_elements: Record<string, number>; removed_attributes: Record<string, number>; element_count: number; orphaned_bindings?: string[] }
  interface Sel { id: string; tag: string; interactive?: boolean; name?: string; desc?: string }
  interface ScadaApi {
    ready: Promise<void>;
    load(svg: string): boolean;
    newDrawing(w: number, h: number): void;
    getSvg(): string;
    onSelection(fn: (sel: Sel[]) => void): void;
    onChange(fn: () => void): void;
    setSelectedId(id: string): string;
    setSelectedText(attr: 'data-hv-name' | 'data-hv-desc', value: string): string;
    insertSymbol(fragment: string, baseId: string): string;
  }

  let drawings = $state<{ id: string; name: string }[]>([]);
  let tags = $state<TagOption[]>([]);
  let current = $state<Detail | null>(null); // null = ny, ikke gemt tegning
  let loadedVersion = $state<number | null>(null);
  let newName = $state('');
  let comment = $state('');
  let selection = $state<Sel[]>([]);
  let idInput = $state('');
  let nameInput = $state('');
  let descInput = $state('');
  let tagChoice = $state('');
  let dirty = $state(false);
  let busy = $state(false);
  let error = $state('');
  let info = $state('');
  let report = $state<Report | null>(null);
  let ready = $state(false);
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
      descInput = sel.length === 1 ? sel[0].desc ?? '' : '';
      tagChoice = sel.length === 1 && tags.some((t) => t.name === sel[0].id) ? sel[0].id : '';
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

  /** Navn og forklaring på det valgte element — gemmes i tegningen og vises i Bindinger og som tooltip på Overview. */
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
  function fitPreview(svg: SVGSVGElement): void {
    try {
      const b = (svg.firstElementChild as SVGGraphicsElement).getBBox();
      const pad = 4 + Math.max(b.width, b.height) * 0.04;
      svg.setAttribute('viewBox', `${b.x - pad} ${b.y - pad} ${b.width + 2 * pad} ${b.height + 2 * pad}`);
    } catch {
      // getBBox kan fejle hvis knappen er skjult — standard-viewBox bruges så
    }
  }

  let selectorLabels = $state('Hånd, 0, Auto');
  let selectorError = $state('');

  /** Omskifter med de positioner brugeren har skrevet (2-8, adskilt med komma). */
  function insertSelector(): void {
    selectorError = '';
    try {
      const svg = selectorSymbol(selectorLabels.split(','));
      if (!ed) return;
      ed.insertSymbol(withName(svg, 'Omskifter'), 'omskifter');
      dirty = true;
    } catch (e) {
      selectorError = (e as Error).message;
    }
  }

  function insert(symbolId: string): void {
    const s = SYMBOLS.find((x) => x.id === symbolId);
    if (!ed || !s) return;
    ed.insertSymbol(withName(s.svg, s.label), s.id);
    dirty = true;
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
      [drawings, tags] = await Promise.all([
        get<{ id: string; name: string }[]>('/api/drawings'),
        get<TagOption[]>('/api/tags'),
      ]);
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
  {:else}
    <button class="primary" onclick={() => save(true)} disabled={busy || !ready}>Opret tegning</button>
  {/if}
  {#if dirty}<span class="badge">ikke gemt</span>{/if}
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
      {:else}
        <p class="small muted">&lt;{single.tag}&gt;</p>
        <label class="field">Tag
          <TagSelect bind:value={tagChoice} {tags} writableOnly={!!single.interactive} placeholder="— vælg tag —" onchange={(v) => v && applyId(v)} />
        </label>
        {#if single.interactive}
          <p class="small muted"><strong>Betjeningssymbol:</strong> vælg et skrivbart tag — så bindes klik-handlingen (skriver til PLC'en) og visningen (lampe, vippe, greb, tekst) automatisk, når tegningen er gemt. Ret detaljer under <strong>Bindinger</strong>.</p>
          {#if tagChoice && !tags.find((t) => t.name === tagChoice)?.writable}
            <p class="small error">Tagget er ikke skrivbart — symbolet viser kun værdien. Markér tagget skrivbart under <a href="#tags">Tags</a>.</p>
          {/if}
        {:else}
          <p class="small muted">Elementets id sættes til tag-navnet, så det bindes automatisk: tekst viser værdien, figurer farves efter til/fra. Andre animationer og klik-handlinger sættes under <strong>Bindinger</strong> efter gem.</p>
        {/if}
        <label class="field">Navn
          <input bind:value={nameInput} maxlength="60" placeholder="fx Ventilator stue — vises i Bindinger"
            onchange={() => applyText('data-hv-name', nameInput)} />
        </label>
        <label class="field">Forklaring
          <textarea bind:value={descInput} rows="3" maxlength="500" placeholder="Hvad gør symbolet, og hvem må betjene det? Vises som tooltip på Overview"
            onchange={() => applyText('data-hv-desc', descInput)}></textarea>
        </label>
        <label class="field">Id
          <span class="row"><input bind:value={idInput} /><button onclick={() => applyId(idInput.trim())} disabled={!idInput.trim() || idInput === single.id}>Sæt</button></span>
        </label>
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
                  <svg viewBox="-4 -4 168 152" aria-hidden="true" {@attach fitPreview}>{@html s.svg}</svg>
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

<style>
  .toolbar { margin-bottom: .6rem; }
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
  .selector-cfg { margin-top: .5rem; }
  .selector-cfg input { flex: 1; min-width: 0; }
  summary { cursor: pointer; font-weight: 600; font-size: .9rem; margin-bottom: .4rem; }
  .symbols svg { width: 44px; height: 40px; }
</style>
