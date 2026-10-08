<script lang="ts">
  import { onDestroy, onMount, tick } from 'svelte';
  import { get, put, type Binding, type DrawingView, type LiveValue } from '../lib/api';
  import { ANIMS, flatten, fromForm, groupIds, isClick, nextBinding, pickElement, toDrafts, toForm, toHex, type BindingForm, type Draft } from '../lib/bindingForm';
  import { textFor } from '../lib/animate';
  import { findElement, mountSvg, renderAll, renderBinding } from '../lib/canvas';
  import { LiveClient } from '../lib/live';
  import TagSelect from '../lib/TagSelect.svelte';

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
  let drafts = $state<Draft[]>([]); // én binding = ét tag (gid) med en eller flere animationer
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
    for (const d of flatten(drafts)) {
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
    drafts = toDrafts(explicit.map((b) => toForm(b)));
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

  const isTextElement = () => ['text', 'tspan'].includes(elements.find((e) => e.id === selected)?.type ?? '');
  const nextGid = (list: Draft[]) => Math.max(-1, ...list.map((d) => d.gid)) + 1;
  const groupOf = (gid: number) => drafts.filter((d) => d.gid === gid);

  /** Ny binding (nyt tag). Er elementet bundet automatisk, tages den binding med — ellers forsvinder den ved gem. */
  function addBinding(): void {
    const base = explicitMode ? drafts : toDrafts(autoFor(selected!).map((b) => toForm(b)));
    explicitMode = true;
    drafts = [...base, { ...nextBinding([], isTextElement()), gid: nextGid(base) }];
    changed();
  }

  /** Endnu en animation på samme tag i bindingen (fx blink oven i tekst). */
  function addAnimation(gid: number): void {
    drafts = flatten([...drafts, { ...nextBinding(groupOf(gid), isTextElement()), gid }]);
    changed();
  }

  function setGroupTag(gid: number, tag: string): void {
    for (const d of drafts) if (d.gid === gid && d.anim !== 'click:goto') d.tag = tag;
    changed();
  }

  function makeExplicit(): void {
    explicitMode = true;
    drafts = toDrafts(autoFor(selected!).map((b) => toForm(b)));
    changed();
  }

  function removeDraft(d: Draft): void {
    drafts = drafts.filter((x) => x !== d);
    changed();
  }

  function removeGroup(gid: number): void {
    drafts = drafts.filter((d) => d.gid !== gid);
    changed();
  }

  async function save(): Promise<void> {
    if (!selected || !view) return;
    let items;
    try {
      const groups = groupIds(drafts);
      items = flatten(drafts).map((d) => {
        try {
          return fromForm(d);
        } catch (e) {
          const label = ANIMS.find((a) => a.id === d.anim)?.label ?? d.anim;
          throw new Error(`Binding ${groups.indexOf(d.gid) + 1} (${label}): ${(e as Error).message}`);
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

  /** Tekst-binding som den vil se ud — med tagets aktuelle værdi, ellers et eksempel. */
  function textPreview(d: BindingForm): string {
    try {
      const { params } = fromForm(d);
      return textFor(values[d.tag]?.value ?? 1002, view?.tags[d.tag], params);
    } catch {
      return ''; // ugyldig kladde — fejlen vises allerede ved feltet/Gem
    }
  }

  function onAnimChange(d: Draft): void {
    // Animationen hører til bindingens tag (også når den skiftes væk fra "gå til tegning")
    const lead = groupOf(d.gid).find((x) => x !== d && x.anim !== 'click:goto');
    if (d.anim !== 'click:goto' && lead) d.tag = lead.tag;
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
              Tryk <em>Tilpas</em> for at ændre den eller give den flere animationer (fx blink).
              <div class="row" style="margin-top:.4rem"><button onclick={makeExplicit}>Tilpas</button></div>
            </div>
          {:else}
            <p class="muted small">Ingen bindinger.</p>
          {/if}
        {/if}

        {#each groupIds(drafts) as gid, gi (gid)}
          {@const group = groupOf(gid)}
          {@const lead = group.find((x) => x.anim !== 'click:goto')}
          <div class="binding">
            <div class="row" style="justify-content: space-between">
              <strong>Binding {gi + 1}</strong>
              <button class="danger small" onclick={() => removeGroup(gid)}>Fjern binding</button>
            </div>
            {#if lead}
              <label class="field-row">Tag
                <TagSelect value={lead.tag} {tags} writableOnly={group.some((x) => isClick(x.anim) && x.anim !== 'click:goto')}
                  onchange={(v) => setGroupTag(gid, v)} />
              </label>
              {#if lead.tag && !tagNames.has(lead.tag)}<p class="small error">Ukendt tag!</p>{/if}
            {/if}

            {#each group as d, k (d)}
              <div class="anim">
                <div class="row" style="justify-content: space-between">
                  <label class="anim-select">Animation {group.length > 1 ? k + 1 : ''}
                    <select bind:value={d.anim} onchange={() => onAnimChange(d)}>
                      {#each ANIMS as a}<option value={a.id}>{a.label}</option>{/each}
                    </select>
                  </label>
                  {#if group.length > 1}<button class="small" title="Fjern denne animation" onclick={() => removeDraft(d)}>×</button>{/if}
                </div>
                <p class="small muted">{ANIMS.find((a) => a.id === d.anim)?.help}</p>
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
                    <label>Tekst før<input bind:value={d.prefix} oninput={changed} maxlength="40" placeholder="fx Tank : " /></label>
                    <label>Tekst efter<input bind:value={d.suffix} oninput={changed} maxlength="40" placeholder="fx  liter" /></label>
                    <label>Decimaler<input bind:value={d.decimals} oninput={changed} placeholder="tag-standard" inputmode="numeric" /></label>
                    <label>Tekst ved sand<input bind:value={d.true_text} oninput={changed} maxlength="40" /></label>
                    <label>Tekst ved falsk<input bind:value={d.false_text} oninput={changed} maxlength="40" /></label>
                    <label class="check"><input type="checkbox" bind:checked={d.show_unit} onchange={changed} /> Vis enhed</label>
                  </div>
                  <p class="muted small">Vises som: <code class="preview">{textPreview(d)}</code></p>
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
            <button class="small" onclick={() => addAnimation(gid)}>+ Animation</button>
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
  .anim { border-top: 1px dashed var(--line); padding: .5rem 0 .4rem; margin-top: .4rem; }
  .anim-select { display: flex; flex-direction: column; flex: 1; }
  .preview { white-space: pre; }
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
