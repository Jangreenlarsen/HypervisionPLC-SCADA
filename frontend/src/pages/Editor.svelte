<script lang="ts">
  import { onDestroy, onMount, tick } from 'svelte';
  import { get, put, type Binding, type DrawingView, type LiveValue } from '../lib/api';
  import { ANIMS, emptyForm, fromForm, isClick, pickElement, toForm, toHex, type BindingForm } from '../lib/bindingForm';
  import { findElement, mountSvg, renderAll, renderBinding } from '../lib/canvas';
  import { LiveClient } from '../lib/live';

  let { route = 'editor' }: { route?: string } = $props();

  interface TagRow { name: string; source: string; unit: string; writable: boolean; plc: string; description: string }
  interface ElementInfo { id: string; type: string; label: string | null }
  interface Box { left: number; top: number; width: number; height: number }

  let drawings = $state<{ id: string; name: string }[]>([]);
  let drawingId = $state('');
  let view = $state<DrawingView | null>(null);
  let tags = $state<TagRow[]>([]);
  let elements = $state<ElementInfo[]>([]);
  let error = $state('');
  let info = $state('');
  let filter = $state('');
  let selected = $state<string | null>(null);
  let drafts = $state<BindingForm[]>([]);
  let explicitMode = $state(false); // true = elementet har (eller får) eksplicitte bindinger
  let dirty = $state(false);
  let draftError = $state('');
  let selBox = $state<Box | null>(null);
  let hoverBox = $state<Box | null>(null);
  let container: HTMLDivElement;
  let svgRoot: SVGSVGElement | null = null;

  const values: Record<string, LiveValue> = {};
  const live = new LiveClient((changes) => {
    Object.assign(values, changes);
    if (!container || !view) return;
    for (const b of effective()) if (b.tag in changes) renderBinding(container, b, values, view.tags);
  });

  const explicitFor = (id: string) => (view?.bindings ?? []).filter((b) => b.element === id && b.source === 'explicit');
  const autoFor = (id: string) => (view?.bindings ?? []).filter((b) => b.element === id && b.source === 'auto');

  /** Bindinger der vises lige nu: de gemte, men for det valgte element de (gyldige) kladder. */
  function effective(): Binding[] {
    const saved = view?.bindings ?? [];
    if (!selected || !explicitMode) return saved;
    const draft: Binding[] = [];
    for (const d of drafts) {
      try {
        draft.push({ element: selected, ...fromForm(d) } as Binding);
      } catch {
        // Ufærdig formular — vises ikke i forhåndsvisningen endnu; fejlen vises ved "Gem".
      }
    }
    return [...saved.filter((b) => b.element !== selected), ...draft];
  }

  function boxOf(id: string | null): Box | null {
    if (!id || !container) return null;
    const el = findElement(container, id);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const c = container.getBoundingClientRect();
    return { left: r.left - c.left, top: r.top - c.top, width: Math.max(r.width, 4), height: Math.max(r.height, 4) };
  }

  function redraw(): void {
    if (!container || !view) return;
    svgRoot = mountSvg(container, view.svg);
    const bindings = effective();
    renderAll(container, bindings, values, view.tags);
    live.subscribe([...new Set([...bindings.map((b) => b.tag), ...drafts.map((d) => d.tag).filter(Boolean)])]);
    selBox = boxOf(selected);
  }

  async function load(id: string, keepSelection = false): Promise<void> {
    error = '';
    if (!id) return;
    try {
      const [v, t] = await Promise.all([
        get<DrawingView>(`/api/drawings/${encodeURIComponent(id)}/view`),
        get<TagRow[]>('/api/tags'),
      ]);
      view = v;
      tags = t;
      if (location.hash !== `#editor/${id}`) history.replaceState(null, '', `#editor/${id}`);
      await tick();
      redraw();
      elements = svgRoot
        ? Array.from(svgRoot.querySelectorAll('[id]')).map((el) => ({
            id: el.id, type: el.tagName.toLowerCase(), label: el.getAttribute('inkscape:label'),
          }))
        : [];
      if (keepSelection && selected) select(selected, true);
      else clearSelection();
    } catch (e) {
      view = null;
      error = `Kunne ikke åbne tegningen: ${(e as Error).message}`;
    }
  }

  function clearSelection(): void {
    selected = null;
    drafts = [];
    explicitMode = false;
    dirty = false;
    selBox = null;
  }

  function select(id: string, force = false): void {
    if (!force && dirty && !confirm('Du har ændringer der ikke er gemt. Kassér dem?')) return;
    selected = id;
    const explicit = explicitFor(id);
    explicitMode = explicit.length > 0;
    drafts = explicit.map((b) => toForm(b));
    dirty = false;
    draftError = '';
    info = '';
    redraw();
    findElement(container, id)?.scrollIntoView?.({ block: 'nearest' });
  }

  function onCanvasClick(e: MouseEvent): void {
    if (!svgRoot) return;
    const el = pickElement(e.target as Element, svgRoot);
    if (el) select(el.id);
  }

  function onCanvasMove(e: MouseEvent): void {
    if (!svgRoot) return;
    const el = pickElement(e.target as Element, svgRoot);
    hoverBox = el && el.id !== selected ? boxOf(el.id) : null;
  }

  function changed(): void {
    dirty = true;
    draftError = '';
    redraw();
  }

  function addBinding(): void {
    const isText = elements.find((e) => e.id === selected)?.type === 'text';
    explicitMode = true;
    drafts = [...drafts, emptyForm('', isText ? 'text' : 'fill')];
    changed();
  }

  function makeExplicit(): void {
    explicitMode = true;
    drafts = autoFor(selected!).map((b) => toForm(b));
    changed();
  }

  function removeDraft(i: number): void {
    drafts = drafts.filter((_, j) => j !== i);
    changed();
  }

  async function save(): Promise<void> {
    if (!selected || !view) return;
    let items;
    try {
      items = drafts.map((d, i) => {
        try {
          return fromForm(d);
        } catch (e) {
          throw new Error(`Binding ${i + 1}: ${(e as Error).message}`);
        }
      });
    } catch (e) {
      draftError = (e as Error).message;
      return;
    }
    try {
      const element = selected;
      await put(`/api/drawings/${encodeURIComponent(view.id)}/bindings/${encodeURIComponent(element)}`, { bindings: items });
      dirty = false;
      await load(view.id, true); // vælger elementet igen (og nulstiller beskeder) — derfor sættes info bagefter
      info = items.length ? `Bindinger for "${element}" er gemt.` : `Bindinger for "${element}" er fjernet.`;
    } catch (e) {
      draftError = (e as Error).message;
    }
  }

  async function removeOrphan(element: string): Promise<void> {
    if (!view || !confirm(`Fjern bindingerne til det forsvundne element "${element}"?`)) return;
    try {
      await put(`/api/drawings/${encodeURIComponent(view.id)}/bindings/${encodeURIComponent(element)}`, { bindings: [] });
      await load(view.id, true);
    } catch (e) {
      error = (e as Error).message;
    }
  }

  function status(id: string): 'explicit' | 'auto' | '' {
    if (explicitFor(id).length) return 'explicit';
    if (autoFor(id).length) return 'auto';
    return '';
  }

  const shown = $derived(
    elements.filter((e) => !filter || e.id.toLowerCase().includes(filter.toLowerCase()) ||
      (e.label ?? '').toLowerCase().includes(filter.toLowerCase())),
  );
  const tagNames = $derived(new Set(tags.map((t) => t.name)));
  const writableTags = $derived(new Set(tags.filter((t) => t.writable).map((t) => t.name)));
  const tagGroups = $derived(groupByPlc(tags));

  function groupByPlc(rows: TagRow[]): [string, TagRow[]][] {
    const groups = new Map<string, TagRow[]>();
    for (const t of rows) groups.set(t.plc, [...(groups.get(t.plc) ?? []), t]);
    return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
  }

  function onAnimChange(d: BindingForm): void {
    // Nye standardværdier når typen skiftes (fx bekræftelse er standard for til/fra).
    if (d.anim === 'click:toggle') d.confirm = true;
    if (d.anim === 'click:pulse') d.confirm = false;
    changed();
  }
  const current = $derived(elements.find((e) => e.id === selected) ?? null);

  const onResize = () => (selBox = boxOf(selected));

  onMount(async () => {
    window.addEventListener('resize', onResize);
    try {
      drawings = await get<{ id: string; name: string }[]>('/api/drawings');
    } catch (e) {
      error = (e as Error).message;
      return;
    }
    const fromRoute = route.split('/')[1];
    drawingId = fromRoute && drawings.some((d) => d.id === fromRoute) ? fromRoute : drawings[0]?.id ?? '';
    await load(drawingId);
  });

  onDestroy(() => {
    live.close();
    window.removeEventListener('resize', onResize);
  });
</script>

<div class="row toolbar">
  <select bind:value={drawingId} onchange={() => load(drawingId)} aria-label="Vælg tegning">
    {#each drawings as d}<option value={d.id}>{d.name}</option>{/each}
  </select>
  {#if view}<a href={'#overview/' + view.id}>Vis i Overview</a>{/if}
  <span class="muted small">Klik på et element i tegningen for at binde det til et tag.</span>
</div>

{#if error}<div class="error">{error}</div>{/if}
{#if !drawings.length && !error}<div class="panel">Ingen tegninger endnu — <a href="#drawings">upload en</a>.</div>{/if}

<div class="editor">
  <div class="canvas-wrap">
    <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
    <div class="canvas" bind:this={container} onclick={onCanvasClick} onmousemove={onCanvasMove} onmouseleave={() => (hoverBox = null)}></div>
    {#if hoverBox}<div class="box hover" style="left:{hoverBox.left}px;top:{hoverBox.top}px;width:{hoverBox.width}px;height:{hoverBox.height}px"></div>{/if}
    {#if selBox}<div class="box sel" style="left:{selBox.left}px;top:{selBox.top}px;width:{selBox.width}px;height:{selBox.height}px"></div>{/if}
  </div>

  <aside>
    {#if view?.orphaned_bindings.length}
      <section class="panel">
        <h3>Forsvundne elementer</h3>
        <p class="small muted">Disse elementer har bindinger, men findes ikke i den aktive version af tegningen.</p>
        {#each view.orphaned_bindings as o}
          <div class="row"><code>{o}</code><button class="danger" onclick={() => removeOrphan(o)}>Fjern bindinger</button></div>
        {/each}
      </section>
    {/if}

    <section class="panel">
      {#if !current}
        <h3>Intet element valgt</h3>
        <p class="muted small">Vælg et element i tegningen eller i listen nedenfor.</p>
      {:else}
        <h3>{current.id} <span class="muted small">&lt;{current.type}&gt;{current.label ? ` · label "${current.label}"` : ''}</span></h3>
        {#if info}<div class="notice">{info}</div>{/if}

        {#if !explicitMode}
          {#if autoFor(current.id).length}
            <div class="notice">
              Bundet automatisk fordi {current.label && tagNames.has(current.label) ? 'label' : 'id'} er lig tagget
              <code>{autoFor(current.id)[0].tag}</code> ({autoFor(current.id)[0].anim}).
              <div class="row" style="margin-top:.4rem"><button onclick={makeExplicit}>Tilpas</button></div>
            </div>
          {:else}
            <p class="muted small">Ingen bindinger.</p>
          {/if}
        {/if}

        {#each drafts as d, i}
          <div class="binding">
            <div class="row" style="justify-content: space-between">
              <strong>Binding {i + 1}</strong>
              <button class="danger small" onclick={() => removeDraft(i)}>Fjern</button>
            </div>
            <div class="grid-form">
              {#if d.anim !== 'click:goto'}
                <label>Tag
                  <select bind:value={d.tag} onchange={changed}>
                    <option value="">— vælg tag —</option>
                    {#if d.tag && !tagNames.has(d.tag)}<option value={d.tag}>{d.tag} (findes ikke)</option>{/if}
                    {#each tagGroups as [plc, rows]}
                      <optgroup label={plc}>
                        {#each rows as t}
                          <option value={t.name} disabled={isClick(d.anim) && !t.writable && t.name !== d.tag}>
                            {t.name} · {t.source}{t.unit ? ` [${t.unit}]` : ''}{isClick(d.anim) && !t.writable ? ' (ikke skrivbar)' : ''}
                          </option>
                        {/each}
                      </optgroup>
                    {/each}
                  </select>
                </label>
              {/if}
              <label>Animation
                <select bind:value={d.anim} onchange={() => onAnimChange(d)}>
                  {#each ANIMS as a}<option value={a.id}>{a.label}</option>{/each}
                </select>
              </label>
            </div>
            <p class="small muted">{ANIMS.find((a) => a.id === d.anim)?.help}{d.anim !== 'click:goto' && d.tag && !tagNames.has(d.tag) ? ' — ukendt tag!' : ''}</p>
            {#if isClick(d.anim) && d.anim !== 'click:goto' && d.tag && tagNames.has(d.tag) && !writableTags.has(d.tag)}
              <p class="small error">Tagget er ikke markeret skrivbart — ret det under <a href="#tags">Tags</a>.</p>
            {/if}

            {#if d.anim === 'click:goto'}
              <label class="field-row">Tegning
                <select bind:value={d.drawing} onchange={changed}>
                  <option value="">— vælg —</option>
                  {#each drawings.filter((x) => x.id !== view?.id) as x}<option value={x.id}>{x.name}</option>{/each}
                </select>
              </label>
            {:else if d.anim === 'click:write'}
              <label class="field-row">Titel i dialogen (valgfri)<input bind:value={d.title} oninput={changed} maxlength="60" placeholder="tag-beskrivelsen" /></label>
            {:else if d.anim === 'click:toggle'}
              <label class="check"><input type="checkbox" bind:checked={d.confirm} onchange={changed} /> Bed om bekræftelse</label>
            {:else if d.anim === 'click:pulse'}
              <div class="grid-form">
                <label>Pulslængde (ms)<input bind:value={d.ms} oninput={changed} inputmode="numeric" /></label>
                <label class="check"><input type="checkbox" bind:checked={d.confirm} onchange={changed} /> Bed om bekræftelse</label>
              </div>
            {:else if d.anim === 'text'}
              <div class="grid-form">
                <label>Decimaler<input bind:value={d.decimals} oninput={changed} placeholder="tag-standard" inputmode="numeric" /></label>
                <label>Tekst ved sand<input bind:value={d.true_text} oninput={changed} maxlength="40" /></label>
                <label>Tekst ved falsk<input bind:value={d.false_text} oninput={changed} maxlength="40" /></label>
                <label class="check"><input type="checkbox" bind:checked={d.show_unit} onchange={changed} /> Vis enhed</label>
              </div>
            {:else if d.anim === 'fill' || d.anim === 'stroke'}
              <div class="grid-form">
                <label>Farve ved sand
                  <span class="row"><input type="color" value={toHex(d.on)} oninput={(e) => { d.on = e.currentTarget.value; changed(); }} /><input bind:value={d.on} oninput={changed} /></span>
                </label>
                <label>Farve ved falsk / under tærskler
                  <span class="row"><input type="color" value={toHex(d.off)} oninput={(e) => { d.off = e.currentTarget.value; changed(); }} /><input bind:value={d.off} oninput={changed} /></span>
                </label>
              </div>
              <p class="small muted">Tærskler (for tal): farven skifter når værdien er ≥ tærsklen.</p>
              {#each d.thresholds as t, j}
                <div class="row">
                  <input class="num" bind:value={t.value} oninput={changed} placeholder="værdi" inputmode="decimal" />
                  <input type="color" value={toHex(t.color)} oninput={(e) => { t.color = e.currentTarget.value; changed(); }} />
                  <input bind:value={t.color} oninput={changed} />
                  <button onclick={() => { d.thresholds = d.thresholds.filter((_, k) => k !== j); changed(); }}>×</button>
                </div>
              {/each}
              <button onclick={() => { d.thresholds = [...d.thresholds, { value: '', color: '#b26a00' }]; changed(); }}>+ Tærskel</button>
            {:else if d.anim === 'visible' || d.anim === 'blink'}
              <label class="check"><input type="checkbox" bind:checked={d.invert} onchange={changed} /> Omvendt (aktiv når værdien er falsk)</label>
            {:else}
              <div class="grid-form">
                <label>Min<input bind:value={d.min} oninput={changed} inputmode="decimal" /></label>
                <label>Max<input bind:value={d.max} oninput={changed} inputmode="decimal" /></label>
                {#if d.anim === 'level'}
                  <label>Retning
                    <select bind:value={d.direction} onchange={changed}>
                      <option value="up">Opad</option><option value="down">Nedad</option>
                      <option value="right">Mod højre</option><option value="left">Mod venstre</option>
                    </select>
                  </label>
                {:else if d.anim === 'rotate'}
                  <label>Vinkel ved min (°)<input bind:value={d.angle_min} oninput={changed} inputmode="decimal" /></label>
                  <label>Vinkel ved max (°)<input bind:value={d.angle_max} oninput={changed} inputmode="decimal" /></label>
                {/if}
              </div>
              {#if d.anim === 'level' && current.type !== 'rect'}
                <p class="small error">Niveau virker kun på et &lt;rect&gt;-element — dette er &lt;{current.type}&gt;.</p>
              {/if}
            {/if}
          </div>
        {/each}

        {#if draftError}<div class="error">{draftError}</div>{/if}
        <div class="row" style="margin-top:.6rem">
          <button onclick={addBinding}>+ Tilføj binding</button>
          {#if explicitMode}
            <button class="primary" onclick={save} disabled={!dirty}>Gem</button>
            <button onclick={() => select(current.id, true)} disabled={!dirty}>Fortryd</button>
          {/if}
        </div>
        {#if explicitMode && drafts.length === 0 && autoFor(current.id).length === 0 && explicitFor(current.id).length}
          <p class="small muted">Gem for at fjerne alle bindinger fra elementet.</p>
        {/if}
      {/if}
    </section>

    <section class="panel">
      <h3>Elementer ({elements.length})</h3>
      <input bind:value={filter} placeholder="Søg id eller label" style="width:100%" />
      <ul class="elements">
        {#each shown as e (e.id)}
          <li>
            <button class:active={e.id === selected} onclick={() => select(e.id)}>
              <span class="mono">{e.id}</span>
              <span class="muted small">&lt;{e.type}&gt;</span>
              {#if status(e.id)}<span class="badge {status(e.id) === 'explicit' ? 'ok' : ''}">{status(e.id) === 'explicit' ? 'bundet' : 'auto'}</span>{/if}
            </button>
          </li>
        {/each}
      </ul>
    </section>
  </aside>
</div>


<style>
  .toolbar { margin-bottom: .75rem; }
  .editor {
    display: grid;
    grid-template-columns: minmax(0, 2fr) minmax(300px, 1fr);
    gap: 1rem;
    align-items: start;
  }
  @media (max-width: 900px) { .editor { grid-template-columns: minmax(0, 1fr); } }
  .canvas-wrap { position: relative; }
  .canvas {
    background: var(--panel-2);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    padding: .5rem;
    min-height: 200px;
    cursor: crosshair;
  }
  .canvas :global(svg) { display: block; width: 100%; height: auto; }
  .box { position: absolute; pointer-events: none; border-radius: 2px; }
  .box.sel { outline: 2px solid var(--accent); outline-offset: 2px; background: rgba(31, 95, 153, .08); }
  .box.hover { outline: 1px dashed var(--accent); outline-offset: 2px; }
  aside { display: flex; flex-direction: column; gap: 0; min-width: 0; }
  .binding { border-top: 1px solid var(--line); padding-top: .6rem; margin-top: .6rem; }
  .check { flex-direction: row !important; align-items: center; gap: .4rem !important; }
  .num { width: 6rem; }
  .field-row { display: flex; flex-direction: column; gap: .2rem; font-size: .85rem; color: var(--muted); margin-bottom: .4rem; }
  input[type='color'] { width: 2.4rem; padding: 0 .1rem; height: 1.9rem; }
  .elements { list-style: none; margin: .5rem 0 0; padding: 0; max-height: 40vh; overflow-y: auto; }
  .elements button {
    width: 100%;
    text-align: left;
    display: flex;
    gap: .4rem;
    align-items: center;
    border: none;
    border-bottom: 1px solid var(--line);
    border-radius: 0;
    background: transparent;
  }
  .elements button.active { background: #dbe7f3; }
  .elements .mono { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; min-width: 0; }
</style>
