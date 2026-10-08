<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { get, patch, post } from '../lib/api';
  import { SYMBOLS } from '../lib/symbols';
  import TagSelect, { type TagOption } from '../lib/TagSelect.svelte';

  let { route = 'draw' }: { route?: string } = $props();

  interface Version { version: number; comment: string; created_at: number }
  interface Detail { id: string; name: string; active_version: number; versions: Version[] }
  interface Report { removed_elements: Record<string, number>; removed_attributes: Record<string, number>; element_count: number; orphaned_bindings?: string[] }
  interface Sel { id: string; tag: string }
  interface ScadaApi {
    ready: Promise<void>;
    load(svg: string): boolean;
    newDrawing(w: number, h: number): void;
    getSvg(): string;
    onSelection(fn: (sel: Sel[]) => void): void;
    onChange(fn: () => void): void;
    setSelectedId(id: string): string;
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

  function insert(symbolId: string): void {
    const s = SYMBOLS.find((x) => x.id === symbolId);
    if (!ed || !s) return;
    ed.insertSymbol(s.svg, s.id);
    dirty = true;
  }

  const onBeforeUnload = (e: BeforeUnloadEvent) => {
    if (dirty) e.preventDefault();
  };

  onMount(async () => {
    window.addEventListener('beforeunload', onBeforeUnload);
    try {
      [drawings, tags] = await Promise.all([
        get<{ id: string; name: string }[]>('/api/drawings'),
        get<TagOption[]>('/api/tags'),
      ]);
    } catch (e) {
      error = (e as Error).message;
    }
  });
  onDestroy(() => window.removeEventListener('beforeunload', onBeforeUnload));

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
          <TagSelect bind:value={tagChoice} {tags} placeholder="— vælg tag —" onchange={(v) => v && applyId(v)} />
        </label>
        <p class="small muted">Elementets id sættes til tag-navnet, så det bindes automatisk: tekst viser værdien, figurer farves efter til/fra. Andre animationer og klik-handlinger sættes under <strong>Bindinger</strong> efter gem.</p>
        <label class="field">Id
          <span class="row"><input bind:value={idInput} /><button onclick={() => applyId(idInput.trim())} disabled={!idInput.trim() || idInput === single.id}>Sæt</button></span>
        </label>
      {/if}
    </section>

    <section class="panel">
      <h3>Symboler</h3>
      <div class="symbols">
        {#each SYMBOLS as s}
          <button onclick={() => insert(s.id)} disabled={!ready} title={s.hint}>
            <svg viewBox="-4 -4 168 152" aria-hidden="true">{@html s.svg}</svg>
            <span>{s.label}</span>
          </button>
        {/each}
      </div>
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
    height: calc(100vh - 170px);
    min-height: 480px;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: #fff;
  }
  aside { min-width: 0; }
  .field { display: flex; flex-direction: column; gap: .25rem; font-size: .85rem; color: var(--muted); margin-bottom: .5rem; }
  .field :global(select), .field input { width: 100%; }
  .symbols { display: grid; grid-template-columns: repeat(3, 1fr); gap: .4rem; }
  .symbols button { display: flex; flex-direction: column; align-items: center; gap: .2rem; padding: .3rem; font-size: .75rem; }
  .symbols svg { width: 44px; height: 40px; }
</style>
