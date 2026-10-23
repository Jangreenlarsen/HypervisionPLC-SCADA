<script lang="ts">
  import { onDestroy, onMount, tick } from 'svelte';
  import { ask as askUser } from '../lib/ask';
  import { api, get, post, put, type Binding, type DrawingView, type LiveValue } from '../lib/api';
  import { ANIM_TXT, type AnimType } from '../lib/symbolConfig';
  import { ANIMS, flatten, fromForm, groupIds, isClick, nextBinding, pickElement, toDrafts, toForm, toHex, type BindingForm, type Draft } from '../lib/bindingForm';
  import { textFor } from '../lib/animate';
  import { expressionError } from '../lib/expression';
  import { ancestorsOf, buildElements, defaultExpanded, descendantCount, displayName, relevantElements, showsId, visibleRows, type ElementInfo } from '../lib/elementTree';
  import { bindingTags, findElement, fitSvg, mountSvg, onLayoutChange, renderAll, renderBinding } from '../lib/canvas';
  import { LiveClient } from '../lib/live';
  import { mergeMoved, orphanGroups } from '../lib/orphans';
  import TagSelect from '../lib/TagSelect.svelte';
  import SymbolGuide from '../lib/SymbolGuide.svelte';
  import { changeMembers, listGroups, moveMember, ofKind, type SymbolGroup } from '../lib/symbolGroups';
  import GroupAnims from '../lib/GroupAnims.svelte';

  let { route = 'editor' }: { route?: string } = $props();

  interface TagRow { name: string; source: string; unit: string; writable: boolean; plc: string; description: string }
  interface Box { left: number; top: number; width: number; height: number }

  let drawings = $state<{ id: string; name: string }[]>([]);
  let drawingId = $state('');
  let view = $state<DrawingView | null>(null);
  let tags = $state<TagRow[]>([]);
  let elements = $state<ElementInfo[]>([]);
  let error = $state('');
  let info = $state('');
  let filter = $state('');
  // Symbolgrupper (v0.130.0): vælg en gruppe for kun at se dens symboler i listen — bindinger sættes som ellers pr. symbol
  let groups = $state<SymbolGroup[]>([]);
  let groupId = $state('');
  let groupAnimsOpen = $state(false);
  let expanded = $state<Set<string>>(new Set()); // standard: rene grupper udfoldet, symboler sammenfoldet
  let showAll = $state(false);                   // standard: kun symboler (navngivne) og bundne elementer
  let descDraft = $state('');
  const current = $derived(elements.find((e) => e.id === selected) ?? null);
  let guideFor = $state<{ id: string; name: string } | null>(null); // symbol-guiden (symbolstandarden) er åben
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
    for (const b of effective()) if (bindingTags(b).some((t) => t in changes)) renderBinding(container, b, values, view.tags);
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
    svgRoot = mountSvg(container, view.svg, view.symbols);
    fitSvg(svgRoot, container);
    const bindings = effective();
    renderAll(container, bindings, values, view.tags);
    live.subscribe([...new Set([...bindings.flatMap((b) => bindingTags(b)), ...drafts.flatMap((d) => [d.tag, d.anim === 'flow' ? d.dir_tag : '']).filter(Boolean)])]);
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
      elements = svgRoot ? buildElements(svgRoot) : [];
      expanded = defaultExpanded(scope.elements);
      if (keepSelection && selected) select(selected, true);
      else clearSelection();
      await loadOrphans();
      groupId = '';
      listGroups(id).then((g) => (groups = g)).catch((e) => { groups = []; console.error('Symbolgrupper kunne ikke hentes:', e); });
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

  async function select(id: string, force = false): Promise<void> {
    if (!force && dirty && !await askUser('Du har ændringer der ikke er gemt. Kassér dem?')) return;
    selected = id;
    descDraft = descFor(elements.find((e) => e.id === id) ?? null);
    if (!filter) expanded = new Set([...expanded, ...ancestorsOf(elements, id)]); // vis hvor det valgte element ligger
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

  // ---------------------------------------------------------------- forsvundne elementer (v0.83.0)
  let orphanRows = $state<Record<string, Binding[]>>({});
  // Symbolopsætninger på forsvundne elementer (v0.88.0)
  interface OrphanCfg { element: string; type: string; op: string; anims: { part: string; type: AnimType; src: string }[]; has_pin: boolean }
  let orphanCfgs = $state<OrphanCfg[]>([]);
  const orphanCount = $derived((view?.orphaned_bindings.length ?? 0) + orphanCfgs.length);
  let orphanBusy = $state(false);
  const animName = (a: string) => ANIMS.find((x) => x.id === a)?.label ?? a;
  async function loadOrphans(): Promise<void> {
    orphanRows = {};
    orphanCfgs = [];
    if (!view) return;
    try {
      orphanCfgs = await get<OrphanCfg[]>(`/api/drawings/${encodeURIComponent(view.id)}/symbols-orphaned`);
    } catch (e) {
      error = `De forsvundne symbolopsætninger kunne ikke hentes: ${(e as Error).message}`;
    }
    if (!view.orphaned_bindings.length) return;
    try {
      orphanRows = orphanGroups(await get<Binding[]>(`/api/drawings/${encodeURIComponent(view.id)}/bindings`), view.orphaned_bindings);
    } catch (e) {
      error = `De forsvundne bindinger kunne ikke hentes: ${(e as Error).message}`;
    }
  }
  /** Er elementet (eller et symbol det ligger i) sat op med symbolguiden? Så bruges bindinger på det ikke. */
  function underSymbolConfig(id: string): boolean {
    const roots = new Set((view?.bindings ?? []).filter((b) => b.source === 'symbol').map((b) => (b as Binding & { symbol?: string }).symbol));
    return [id, ...ancestorsOf(elements, id)].some((x) => roots.has(x));
  }
  async function removeOrphans(list: string[], cfgs: string[] = []): Promise<void> {
    if (!view || !(list.length + cfgs.length)) return;
    const all = [...list, ...cfgs];
    const what = all.length === 1 ? `det forsvundne element "${all[0]}"` : `de ${all.length} forsvundne elementer (${all.join(', ')})`;
    const kinds = [list.length ? 'bindingerne' : '', cfgs.length ? 'symbolopsætningen' : ''].filter(Boolean).join(' og ');
    if (!await askUser(`Fjern ${kinds} på ${what}? Det kan ikke fortrydes.`, { ok: 'Fjern', danger: true })) return;
    orphanBusy = true;
    const base = `/api/drawings/${encodeURIComponent(view.id)}`;
    try {
      for (const element of list) {
        await put(`${base}/bindings/${encodeURIComponent(element)}`, { bindings: [] });
      }
      for (const element of cfgs) {
        await api('DELETE', `${base}/symbols/${encodeURIComponent(element)}/config`);
      }
    } catch (e) {
      error = (e as Error).message;   // stop ved første fejl; de fjernede er væk, resten står stadig i listen
    } finally {
      orphanBusy = false;
      await load(view.id, true);
    }
  }
  /** Flyt en forsvunden symbolopsætning til det valgte element (dele følger id'et; PIN flyttes med). */
  async function moveOrphanCfg(o: OrphanCfg): Promise<void> {
    if (!view || !selected) return;
    const target = selected;
    error = '';
    if (dirty) { error = 'Gem eller fortryd ændringerne på det valgte element først.'; return; }
    if (!await askUser(`Flyt symbolopsætningen fra det forsvundne "${o.element}" til "${target}"?`, { ok: 'Flyt' })) return;
    orphanBusy = true;
    let done = '';
    try {
      const r = await post<{ dropped: string[] }>(`/api/drawings/${encodeURIComponent(view.id)}/symbols/${encodeURIComponent(o.element)}/move`, { target });
      done = `Symbolopsætningen fra "${o.element}" er flyttet til "${target}".` +
        (r.dropped.length ? ` Animationer på dele, som "${target}" ikke har, er droppet: ${r.dropped.join(', ')} — sæt dem op igen i guiden.` : '');
    } catch (e) {
      error = (e as Error).message;   // fx målet har allerede en opsætning, eller animationerne passer ikke til målet
    } finally {
      orphanBusy = false;
      await load(view.id, true);
      if (done) info = done;   // efter load: at vælge elementet igen rydder beskeden
    }
  }

  /** Flyt et forsvundet elements bindinger til det valgte element (fx når elementet har fået et nyt id i Tegn). */
  async function moveOrphan(element: string): Promise<void> {
    if (!view || !selected) return;
    const target = selected;
    error = '';
    if (dirty) { error = 'Gem eller fortryd ændringerne på det valgte element først.'; return; }
    if (underSymbolConfig(target)) {
      error = `"${target}" er sat op med symbolguiden — bindinger på det bruges ikke. Vælg et andet element, eller sæt animationerne op i guiden.`;
      return;
    }
    const merged = mergeMoved(explicitFor(target), orphanRows[element] ?? []);
    if ('error' in merged) { error = merged.error; return; }
    if (!await askUser(`Flyt ${orphanRows[element]?.length ?? 0} binding(er) fra det forsvundne "${element}" til "${target}"?`, { ok: 'Flyt' })) return;
    orphanBusy = true;
    let done = '';
    const base = `/api/drawings/${encodeURIComponent(view.id)}/bindings/`;
    try {
      await put(base + encodeURIComponent(target), { bindings: merged.bindings });   // målet først: fejler det, er intet tabt
      await put(base + encodeURIComponent(element), { bindings: [] });
      done = `Bindingerne fra "${element}" er flyttet til "${target}".`;
    } catch (e) {
      error = (e as Error).message;
    } finally {
      orphanBusy = false;
      await load(view.id, true);
      if (done) info = done;   // efter load: at vælge elementet igen rydder beskeden
    }
  }

  function status(id: string): 'explicit' | 'auto' | '' {
    if (explicitFor(id).length) return 'explicit';
    if (autoFor(id).length) return 'auto';
    return '';
  }

  const boundElements = $derived(new Set((view?.bindings ?? []).map((b) => b.element)));
  const scope = $derived(showAll ? { elements, direct: new Set(elements.map((e) => e.id)) } : relevantElements(elements, boundElements));
  const activeGroup = $derived(groups.find((g) => String(g.id) === groupId) ?? null);
  const rows = $derived.by(() => {
    if (activeGroup) {
      // Gruppens medlemmer i gruppens rækkefølge, flat; medlemmer der ikke findes længere springes over
      const byId = new Map(elements.map((e) => [e.id, e]));
      const q = filter.trim().toLowerCase();
      return activeGroup.members.flatMap((m) => byId.get(m) ?? [])
        .filter((e) => !q || [e.id, e.label, e.name, e.desc].some((v) => v?.toLowerCase().includes(q)))
        .map((e) => ({ ...e, depth: 0, context: false }));
    }
    return visibleRows(scope.elements, expanded, filter).map((r) => ({ ...r, context: r.context || !scope.direct.has(r.id) }));
  });
  async function groupMemberFix(member: string, what: 'move' | 'remove'): Promise<void> {
    if (!view || !activeGroup) return;
    try {
      let note = '';
      if (what === 'move') {
        const r = await moveMember(view.id, activeGroup.id, member, selected!);
        if (r.dropped.length) note += ` Animationer på dele der ikke findes på det nye element er droppet: ${r.dropped.join(', ')}.`;
        if (r.discarded) note += ` ${r.discarded} animationer på det gamle medlem er kasseret, fordi det nye allerede var medlem.`;
      } else await changeMembers(view.id, activeGroup.id, [], [member]);
      const keep = groupId;
      groups = await listGroups(view.id);
      groupId = keep;
      await load(view.id, true);
      if (note) error = `Medlemmet er flyttet.${note}`;
    } catch (e) {
      error = `Kunne ikke ${what === 'move' ? 'flytte' : 'fjerne'} gruppemedlemmet: ${(e as Error).message}`;
    }
  }
  const missingInGroup = $derived(activeGroup ? activeGroup.members.filter((m) => !elements.some((e) => e.id === m)) : []);
  /** Symbolets forklaring: den der er sat her (gemt ved bindingerne), ellers en evt. ældre i selve tegningen. */
  const descFor = (e: ElementInfo | null) => (e ? view?.symbols?.[e.id] ?? e.desc ?? '' : '');
  const enc = encodeURIComponent;

  async function saveDesc(): Promise<void> {
    if (!view || !current) return;
    const text = descDraft.trim();
    if (text === descFor(current)) return;
    try {
      await put(`/api/drawings/${enc(view.id)}/symbols/${enc(current.id)}`, { description: text });
      const symbols = { ...(view.symbols ?? {}) };
      if (text) symbols[current.id] = text;
      else delete symbols[current.id];
      view = { ...view, symbols };
      info = 'Forklaring gemt.';
    } catch (e) {
      error = (e as Error).message;
    }
  }

  function toggleNode(id: string): void {
    const next = new Set(expanded);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    expanded = next;
  }
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
    if (d.anim === 'click:select') d.confirm = true;
    changed();
  }

  // Tegningen fylder den ledige højde; markeringsboksene følger med når størrelsen ændres
  const onResize = () => {
    fitSvg(svgRoot, container);
    selBox = boxOf(selected);
    hoverBox = null;
  };
  let stopLayout: (() => void) | null = null;

  onMount(async () => {
    stopLayout = onLayoutChange(onResize, container);
    try {
      drawings = await get<{ id: string; name: string }[]>('/api/drawings');
    } catch (e) {
      error = (e as Error).message;
      return;
    }
    const fromRoute = route.split('/')[1];
    drawingId = fromRoute && drawings.some((d) => d.id === fromRoute) ? fromRoute : drawings[0]?.id ?? '';
    await load(drawingId);
    const wanted = route.split('/')[2]; // #editor/<tegning>/<element> — fx fra "Konfigurér under Bindinger" i Tegn
    if (wanted && elements.some((e) => e.id === decodeURIComponent(wanted))) select(decodeURIComponent(wanted), true);
  });

  onDestroy(() => {
    live.close();
    stopLayout?.();
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
    {#if view && orphanCount}
      <section class="panel orphans">
        <h3>Forsvundne elementer ({orphanCount})</h3>
        <p class="small muted">Disse elementer har bindinger eller en symbolopsætning, men findes ikke i den aktive version af tegningen — typisk fordi
          elementet er slettet i Tegn eller har fået et nyt id (fx ved <em>Erstat med symbol</em> uden "behold id").
          Har elementet fået et nyt id, så vælg det nye i tegningen og tryk <strong>Flyt hertil</strong>; ellers <strong>Fjern</strong>.</p>
        {#each view.orphaned_bindings as o (o)}
          <div class="orphan">
            <code>{o}</code>
            <ul class="small">
              {#each orphanRows[o] ?? [] as b}<li>{b.tag || '—'} · {animName(b.anim)}</li>{/each}
            </ul>
            <div class="row">
              <button class="small" onclick={() => moveOrphan(o)} disabled={orphanBusy || !selected || !orphanRows[o]?.length}
                title={selected ? `Flyt bindingerne til "${selected}"` : 'Vælg først det element, bindingerne skal flyttes til'}>
                {selected ? `Flyt hertil (${selected})` : 'Flyt hertil — vælg et element'}</button>
              <button class="small danger" onclick={() => removeOrphans([o])} disabled={orphanBusy}>Fjern</button>
            </div>
          </div>
        {/each}
        {#each orphanCfgs as o (o.element)}
          <div class="orphan">
            <code>{o.element}</code> <span class="small muted">symbolopsætning{o.type && o.type !== 'custom' ? ` (${o.type})` : ''}{o.has_pin ? ' · med kode' : ''}</span>
            <ul class="small">
              {#each o.anims as a}<li>{ANIM_TXT[a.type] ?? a.type} på {a.part === 'all' ? 'hele symbolet' : a.part}{a.src ? ` · ${a.src}` : ''}</li>{:else}<li>ingen animationer</li>{/each}
            </ul>
            <div class="row">
              <button class="small" onclick={() => moveOrphanCfg(o)} disabled={orphanBusy || !selected}
                title={selected ? `Flyt opsætningen til "${selected}"` : 'Vælg først det element, opsætningen skal flyttes til'}>
                {selected ? `Flyt hertil (${selected})` : 'Flyt hertil — vælg et element'}</button>
              <button class="small danger" onclick={() => removeOrphans([], [o.element])} disabled={orphanBusy}>Fjern</button>
            </div>
          </div>
        {/each}
        {#if orphanCount > 1}
          <button class="small danger" onclick={() => removeOrphans(view!.orphaned_bindings, orphanCfgs.map((o) => o.element))} disabled={orphanBusy}>Fjern alle {orphanCount}</button>
        {/if}
      </section>
    {/if}

    <section class="panel">
      {#if !current}
        <h3>Intet element valgt</h3>
        <p class="muted small">Vælg et element i tegningen eller i listen nedenfor.</p>
      {:else}
        <h3>{displayName(current)} <span class="muted small">{current.name ? `${current.id} · ` : ''}&lt;{current.type}&gt;{current.label && current.name ? ` · label "${current.label}"` : ''}{current.label && !current.name ? ` · label "${current.label}"` : ''}</span></h3>
        {#if descFor(current)}<p class="small desc">{descFor(current)}</p>{/if}
        {#if current.parent}<p class="small muted">Del af <button class="link-btn" onclick={() => select(current.parent!)}>{displayName(elements.find((x) => x.id === current.parent)!)}</button></p>{/if}
        {#if info}<div class="notice">{info}</div>{/if}

        {#if current.type === 'g' || current.name || current.spec}
          {@const sc = view?.symbol_config?.[current.id]}
          <section class="symbol-cfg">
            <h4>Symbol</h4>
            {#if sc}
              <p class="small">Konfigureret: <strong>{({ positions: `${sc.labels.length} positioner`, pulse: 'trykknap', entry: 'setpunkt', view: 'kun visning' } as Record<string, string>)[sc.op] ?? sc.op}</strong>.
                Symbolets egne bindinger nedenfor bruges ikke, så længe konfigurationen findes.</p>
            {:else}
              <p class="small muted">Ikke opsat endnu. Guiden i 6 trin samler betjening, positioner, kontaktplaner, animationer og nøglelås ét sted.</p>
            {/if}
            <div class="row"><button class="primary" onclick={() => (guideFor = { id: current.id, name: displayName(current) })}>{sc ? 'Ret symbol (6 trin)' : 'Opsæt symbol (6 trin)'}</button></div>
            <p class="small muted">Navnet sættes i <a href={'#draw/' + (view?.id ?? '')}>Tegn</a>.</p>
            <label class="field-row">Forklaring
              <textarea bind:value={descDraft} rows="3" maxlength="500" onchange={saveDesc}
                placeholder="Hvad gør symbolet, og hvem må betjene det? Vises som tooltip på Overview"></textarea>
            </label>
          </section>
        {/if}

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
                {:else if d.anim === 'click:select'}
                  <p class="small muted">Positioner (værdien skrives til tagget). Operatører kan kun vælge disse værdier.</p>
                  {#each d.positions as pos, k}
                    <div class="row">
                      <input class="num" bind:value={pos.value} oninput={changed} inputmode="decimal" placeholder="værdi" aria-label="Værdi {k + 1}" />
                      <input bind:value={pos.label} oninput={changed} maxlength="20" placeholder="navn" aria-label="Navn {k + 1}" />
                      <button onclick={() => { d.positions = d.positions.filter((_, j) => j !== k); changed(); }} disabled={d.positions.length <= 2} title="Fjern position">×</button>
                    </div>
                  {/each}
                  <div class="row">
                    <button onclick={() => { d.positions = [...d.positions, { value: String(d.positions.length), label: `Pos ${d.positions.length + 1}` }]; changed(); }} disabled={d.positions.length >= 8}>+ Position</button>
                    <label class="check"><input type="checkbox" bind:checked={d.confirm} onchange={changed} /> Bed om bekræftelse</label>
                  </div>
                  <label class="field-row">Titel i dialogen (valgfri)<input bind:value={d.title} oninput={changed} maxlength="60" placeholder="tag-beskrivelsen" /></label>
                {:else if d.anim === 'click:pulse'}
                  <div class="grid-form">
                    <label>Pulslængde (ms)<input bind:value={d.ms} oninput={changed} inputmode="numeric" /></label>
                    <label class="check"><input type="checkbox" bind:checked={d.confirm} onchange={changed} /> Bed om bekræftelse</label>
                  </div>
                {:else if d.anim === 'text'}
                  <div class="grid-form">
                    <label>Tekst før<input bind:value={d.prefix} oninput={changed} maxlength="40" placeholder="fx Tank : " /></label>
                    <label>Tekst efter<input bind:value={d.suffix} oninput={changed} maxlength="40" placeholder="fx  liter" /></label>
                    <label>Beregning<input bind:value={d.expression} oninput={changed} maxlength="80" placeholder="fx x / 10" /></label>
                    <label>Decimaler<input bind:value={d.decimals} oninput={changed} placeholder="tag-standard" inputmode="numeric" /></label>
                    <label>Tekst ved sand<input bind:value={d.true_text} oninput={changed} maxlength="40" /></label>
                    <label>Tekst ved falsk<input bind:value={d.false_text} oninput={changed} maxlength="40" /></label>
                    <label class="check"><input type="checkbox" bind:checked={d.show_unit} onchange={changed} /> Vis enhed</label>
                  </div>
                  {#if expressionError(d.expression)}<p class="small error">Beregning: {expressionError(d.expression)}</p>{/if}
                  <p class="muted small">Beregning (valgfri): <code>x</code> er tagets værdi — fx <code>x / 10</code>, <code>x * 1,8 + 32</code>, <code>round(x / 10)</code>.
                    + − * / % og parenteser; funktioner abs, round, floor, ceil, sqrt, min, max (flere værdier adskilles med <code>;</code>). Decimaler og enhed gælder resultatet.</p>
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
                {:else if d.anim === 'flow'}
                  <div class="grid-form">
                    <label>Styres af tagget
                      <select bind:value={d.mode} onchange={changed}>
                        <option value="onoff">Til/fra — kører når til</option>
                        <option value="signed">Fortegn — over 0 frem, under 0 tilbage, 0 stop</option>
                        <option value="code">Kode — 0 stop, 1 frem, 2 tilbage</option>
                      </select>
                    </label>
                    <label>Retning styres af (valgfrit)
                      <TagSelect bind:value={d.dir_tag} {tags} placeholder="— intet: retningen er fast —" onchange={changed} />
                    </label>
                    <label>Farve 1 (røret)
                      <span class="row"><input type="color" value={toHex(d.base)} oninput={(e) => { d.base = e.currentTarget.value; changed(); }} /><input bind:value={d.base} oninput={changed} /></span>
                    </label>
                    <label>Farve 2 (lyset)
                      <span class="row"><input type="color" value={toHex(d.light)} oninput={(e) => { d.light = e.currentTarget.value; changed(); }} /><input bind:value={d.light} oninput={changed} /></span>
                    </label>
                    <label>Hastighed (enheder/s)<input bind:value={d.speed} oninput={changed} inputmode="decimal" title="5-500 tegningsenheder pr. sekund" /></label>
                    <label>Streglængde<input bind:value={d.dash} oninput={changed} inputmode="decimal" title="Længden af hver lys og mørk streg (2-200)" /></label>
                  </div>
                  <div class="grid-form">
                    <label>T-stykke/kryds: valgt rør
                      <select bind:value={d.arm} onchange={changed} title="Som røret ses på skærmen — også når symbolet er roteret">
                        <option value="">Intet (lyset følger tegneretningen)</option>
                        <option value="left">Venstre</option><option value="right">Højre</option>
                        <option value="up">Op</option><option value="down">Ned</option>
                      </select>
                    </label>
                    {#if d.arm}
                      <label>Det valgte rør løber
                        <select bind:value={d.arm_flow} onchange={changed}>
                          <option value="in">Ind i krydset (de øvrige ud)</option>
                          <option value="out">Ud af krydset (de øvrige ind)</option>
                        </select>
                      </label>
                    {/if}
                  </div>
                  <div><label class="check"><input type="checkbox" bind:checked={d.reverse} onchange={changed} /> Vend retningen ({d.arm ? 'byt ind og ud' : 'frem = modsat tegneretningen'})</label></div>
                  {#if d.mode === 'onoff'}
                    <div><label class="check"><input type="checkbox" bind:checked={d.invert} onchange={changed} /> Omvendt (kører når værdien er falsk)</label></div>
                  {/if}
                  {#if d.dir_tag}<p class="small muted">Retnings-tagget: Fra = som valgt ovenfor, Til = modsat. Ukendt retning = stop.</p>{/if}
                  <p class="small muted">{d.arm ? 'I et T-stykke eller kryds løber det valgte rør ind (eller ud), og de øvrige rør den modsatte vej. Ved "tilbage" vendes det hele.' : 'Lyset løber langs elementets tegneretning (for et lige rør: mod højre/nedad).'} Står stille ved stop og når værdien er ukendt.</p>
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
                    {:else if d.anim === 'move'}
                      <label>Flyt X ved max<input bind:value={d.dx} oninput={changed} inputmode="decimal" title="Vandret forskydning i tegningens enheder (negativ = til venstre)" /></label>
                      <label>Flyt Y ved max<input bind:value={d.dy} oninput={changed} inputmode="decimal" title="Lodret forskydning i tegningens enheder (negativ = op)" /></label>
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
      <div class="row" style="justify-content: space-between">
        <h3>Symboler og bundne ({scope.direct.size})</h3>
        {#if !filter && !activeGroup && scope.elements.some((e) => e.children)}
          <span class="row small">
            <button class="link-btn" onclick={() => (expanded = new Set(scope.elements.filter((e) => e.children).map((e) => e.id)))}>Fold alle ud</button>
            <button class="link-btn" onclick={() => (expanded = new Set())}>Fold alle sammen</button>
            <button class="link-btn" onclick={() => (expanded = defaultExpanded(scope.elements))}>Standard</button>
          </span>
        {/if}
      </div>
      {#if groups.length}
        <label class="small group-pick">Gruppe
          <select bind:value={groupId} aria-label="Vis kun en gruppe">
            <option value="">Alle symboler</option>
            {#each ofKind(groups, 'function') as g}<option value={String(g.id)}>{g.name} ({g.members.length})</option>{/each}
            {#each ofKind(groups, 'selection') as g}<option value={String(g.id)}>{g.name} ({g.members.length}) · udvalg</option>{/each}
          </select>
        </label>
        {#if activeGroup}
          <div class="row"><button class="small" onclick={() => (groupAnimsOpen = true)} disabled={!activeGroup.members.length}
            title="Sæt animationer op på alle gruppens symboler (gælder ud over deres egne)">Animationer for gruppen …</button></div>
        {/if}
        {#if activeGroup && missingInGroup.length}
          <div class="small notice">
            {missingInGroup.length} af gruppens symboler findes ikke længere på tegningen (slettet eller nyt id). Vælg elementet, der har overtaget pladsen, og tryk <strong>Flyt hertil</strong> — gruppens animationer følger med — eller <strong>Fjern</strong>.
            {#each missingInGroup as m (m)}
              <div class="row"><code>{m}</code>
                <button class="small" onclick={() => groupMemberFix(m, 'move')} disabled={!selected} title={selected ? `Flyt til "${selected}"` : 'Vælg først elementet i listen'}>Flyt hertil</button>
                <button class="small" onclick={() => groupMemberFix(m, 'remove')}>Fjern</button></div>
            {/each}
          </div>
        {/if}
      {/if}
      <input bind:value={filter} placeholder="Søg navn, id, label eller forklaring" style="width:100%" />
      <label class="check small show-all" title="Standard: kun navngivne symboler og elementer med bindinger — navne sættes i Tegn">
        <input type="checkbox" bind:checked={showAll} onchange={() => (expanded = defaultExpanded(scope.elements))} />
        Vis alle elementer ({elements.length})
      </label>
      <ul class="elements tree" role="tree">
        {#each rows as e (e.id)}
          {@const open = filter ? true : expanded.has(e.id)}
          <li role="treeitem" aria-selected={e.id === selected} aria-expanded={e.children ? open : undefined}
            class:symbol={e.symbol} class:context={e.context} style="--depth:{e.depth}">
            {#if e.children}
              <button class="twisty" onclick={() => toggleNode(e.id)} aria-label={open ? 'Fold sammen' : 'Fold ud'} disabled={!!filter}>{open ? '▾' : '▸'}</button>
            {:else}<span class="twisty"></span>{/if}
            <button class="item" class:active={e.id === selected} onclick={() => select(e.id)} title={e.desc ?? ''}>
              <span class="nm">{displayName(e)}</span>
              {#if showsId(e)}<span class="mono muted small id">{e.id}</span>{/if}
              {#if e.children && !open}<span class="muted small">+{descendantCount(scope.elements, e.id)}</span>{/if}
              <span class="muted small">&lt;{e.type}&gt;</span>
              {#if status(e.id)}<span class="badge {status(e.id) === 'explicit' ? 'ok' : ''}">{status(e.id) === 'explicit' ? 'bundet' : 'auto'}</span>{/if}
            </button>
          </li>
        {/each}
      </ul>
    </section>
  </aside>
</div>

{#if groupAnimsOpen && activeGroup && view}
  <GroupAnims drawingId={view.id} group={activeGroup} {tags} onclose={() => (groupAnimsOpen = false)} />
{/if}

{#if guideFor && view}
  <SymbolGuide drawingId={view.id} element={guideFor.id} name={guideFor.name} {tags}
    onclose={() => (guideFor = null)}
    onsaved={async () => { const id = guideFor?.id; guideFor = null; await load(drawingId, true); if (id) select(id, true); }} />
{/if}

<style>
  .anim { border-top: 1px dashed var(--line); padding: .5rem 0 .4rem; margin-top: .4rem; }
  .anim-select { display: flex; flex-direction: column; flex: 1; }
  .preview { white-space: pre; }
  .toolbar { margin-bottom: .75rem; }
  .editor {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(300px, 360px); /* tegningen får resten af bredden */
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
  .canvas :global(svg) { display: block; width: 100%; height: auto; margin: 0 auto; } /* størrelse sættes af fitSvg */
  .box { position: absolute; pointer-events: none; border-radius: 2px; }
  .box.sel { outline: 2px solid #5ccf6e; outline-offset: 2px; background: rgba(92, 207, 110, .3); }
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
  /* Træ: delene af et symbol står indrykket under det */
  .tree li { display: flex; align-items: stretch; padding-left: calc(var(--depth, 0) * 1.1rem); border-bottom: 1px solid var(--line); }
  .tree li.symbol > .item .nm { font-weight: 600; }
  .tree li.context > .item { opacity: .6; }
  .tree .twisty { flex: none; width: 1.4rem; border: none; background: transparent; padding: 0; color: var(--muted); }
  .tree .item { flex: 1; min-width: 0; border-bottom: none; }
  .tree .nm { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
  .tree .id { flex: 0 1 8rem; }
  .desc { margin: .1rem 0 .4rem; color: var(--text); white-space: pre-wrap; }
  .symbol-cfg { border: 1px solid var(--line); border-radius: var(--radius); padding: .5rem .7rem; margin: .5rem 0; background: var(--panel-2); }
  .symbol-cfg h4 { margin: 0 0 .3rem; }
  .show-all { margin: .4rem 0 0; }
  .link-btn { background: none; border: none; padding: 0; color: var(--accent); text-decoration: underline; cursor: pointer; font: inherit; }
  .orphans .orphan { border-top: 1px solid var(--line); padding: .4rem 0; }
  .orphans ul { margin: .2rem 0 .3rem 1rem; padding: 0; }
</style>
