<script lang="ts">
  // Animationer ejet af en gruppe (v0.131.0): for hvert medlem af gruppen sættes gruppens egne animationer op. De gælder
  // ved siden af symbolets egne og andre gruppers — som vises skrivebeskyttet i deres farver, så man kan se hvad man ikke skal røre.
  import { onMount } from 'svelte';
  import { ask } from './ask';
  import { get } from './api';
  import TagSelect from './TagSelect.svelte';
  import AnimParams from './AnimParams.svelte';
  import OwnerAnims from './OwnerAnims.svelte';
  import {
    ANIM_TXT, MAX_ANIMS, ON, WHEN_TYPES, alarmRef, animDefaults, keepSuggestion, parseAlarmRef, partLabel, tagKind, typesFor,
    type Anim, type SrcKind, type SymbolInfo,
  } from './symbolConfig';
  import { getGroupAnims, groupAnimsOn, groupColor, putGroupAnims, type GroupAnim, type OwnerBlock, type SymbolGroup } from './symbolGroups';

  interface TagRow { name: string; source: string; unit: string; writable: boolean; plc: string }
  let { drawingId, group, tags: tagsProp = [], onclose, onsaved }: {
    drawingId: string; group: SymbolGroup; tags?: TagRow[]; onclose: () => void; onsaved?: () => void;
  } = $props();
  let fetchedTags = $state<TagRow[]>([]);   // hentes hvis kalderen ikke havde tags klar
  const tags = $derived(tagsProp.length ? tagsProp : fetchedTags);

  const enc = encodeURIComponent;
  let element = $state('');
  let symbol = $state<SymbolInfo | null>(null);
  let ownAnims = $state<GroupAnim[]>([]);
  let others = $state<OwnerBlock[]>([]);
  let mine = $state<Anim[]>([]);
  let saved = $state('[]');
  let loading = $state(false);
  let busy = $state(false);
  let error = $state('');
  let info = $state('');
  let withAnims = $state<Set<string>>(new Set());   // medlemmer der allerede har gruppe-animationer

  const color = $derived(groupColor(group.id));
  const dirty = $derived(JSON.stringify(mine) !== saved);
  const tagByName = $derived(new Map(tags.map((t) => [t.name, t])));
  const partIds = $derived(['all', ...Object.keys(symbol?.parts ?? {})]);
  const partInfo = (id: string) => (id === 'all' ? symbol ?? undefined : symbol?.parts[id]);
  const nameOf = (id: string) => id;

  async function loadElement(el: string): Promise<void> {
    loading = true; error = info = '';
    try {
      const [cfg, owners] = await Promise.all([
        get<{ config: { anims?: GroupAnim[] } | null; symbol: SymbolInfo | null }>(`/api/drawings/${enc(drawingId)}/symbols/${enc(el)}/config`),
        groupAnimsOn(drawingId, el),
      ]);
      symbol = cfg.symbol;
      ownAnims = cfg.config?.anims ?? [];
      const own = owners.find((o) => o.group_id === group.id);
      mine = structuredClone(own?.anims ?? []) as Anim[];
      saved = JSON.stringify(mine);
      others = owners.filter((o) => o.group_id !== group.id)
        .map((o) => ({ key: `g${o.group_id}`, label: `Gruppen ${o.group_name}`, color: groupColor(o.group_id), anims: o.anims }));
    } catch (e) {
      error = `Kunne ikke hente ${el}: ${(e as Error).message}`;
    } finally {
      loading = false;
    }
  }

  async function loadMarks(): Promise<void> {
    try { withAnims = new Set(Object.keys(await getGroupAnims(drawingId, group.id))); } catch { /* kun en markering i listen */ }
  }
  onMount(() => {
    if (!tagsProp.length) get<TagRow[]>('/api/tags').then((t) => (fetchedTags = t)).catch((e) => (error = `Tags kunne ikke hentes: ${(e as Error).message}`));
    element = group.members[0] ?? ''; void loadMarks(); if (element) void loadElement(element); });

  async function pick(el: string): Promise<void> {
    if (el === element) return;
    if (dirty && !(await ask('Du har ændringer der ikke er gemt. Kassér dem?', { ok: 'Kassér', danger: true }))) return;
    element = el;
    await loadElement(el);
  }

  const owners = $derived<OwnerBlock[]>([
    { key: 'own', label: 'Symbolets egne', color: null, anims: ownAnims },
    ...others,
  ]);

  // ---- redigering af gruppens rækker (som i symbolguiden, men uden positioner og logikblokke)
  function kindOf(a: { src: string }): SrcKind {
    if (a.src === ON || parseAlarmRef(a.src)) return 'bool';
    return tagKind(tagByName.get(a.src)?.source) === 'bool' ? 'bool' : 'num';
  }
  const srcMode = (a: Anim): string => (a.src === ON ? ON : parseAlarmRef(a.src) ? 'alarm' : 'tag');
  function resetParams(a: Anim, wasSrc?: string): void {
    if (!typesFor(partInfo(a.part)).includes(a.type)) a.type = 'fill';
    const fresh = animDefaults(a.type, kindOf(a), 0);
    const before = wasSrc === undefined ? undefined : animDefaults(a.type, kindOf({ src: wasSrc }), 0);
    if (!keepSuggestion(wasSrc, a.params, fresh, before)) a.params = fresh;
    a.only = null;
  }
  function setSrcMode(a: Anim, mode: string): void {
    a.src = mode === ON ? ON : mode === 'alarm' ? alarmRef('active', '') : '';
    resetParams(a);
  }
  function addAnim(): void {
    mine.push({ part: 'all', type: 'fill', when: false, src: '', params: animDefaults('fill', 'num', 0), only: null });
  }
  function moveAnim(i: number, d: -1 | 1): void {
    const j = i + d;
    if (j < 0 || j >= mine.length) return;
    [mine[i], mine[j]] = [mine[j], mine[i]];
  }

  async function save(): Promise<void> {
    busy = true; error = info = '';
    try {
      const r = await putGroupAnims(drawingId, group.id, element, structuredClone($state.snapshot(mine)) as GroupAnim[]);
      mine = structuredClone(r.anims) as Anim[];
      saved = JSON.stringify(mine);
      info = mine.length ? `Gemt (${mine.length} animationer).` : 'Gruppens animationer på symbolet er fjernet.';
      if (mine.length) withAnims.add(element); else withAnims.delete(element);
      withAnims = new Set(withAnims);
      onsaved?.();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  async function close(): Promise<void> {
    if (dirty && !(await ask('Du har ændringer der ikke er gemt. Luk alligevel?', { ok: 'Luk', danger: true }))) return;
    onclose();
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={close}>
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="panel dlg" role="dialog" aria-modal="true" aria-label="Animationer for gruppen {group.name}" tabindex="-1"
    onclick={(e) => e.stopPropagation()} style:--c={color}>
    <header class="row head">
      <h2><span class="chip" style:background={color}></span> Animationer for gruppen {group.name}</h2>
      <button class="close" onclick={close} aria-label="Luk">✕</button>
    </header>
    <p class="small muted">Gruppens animationer gælder <strong>ud over</strong> symbolets egne og andre gruppers. Vælg et symbol i gruppen og sæt dets animationer op.
      Symbolets egne og andre gruppers vises nedenfor, så du kan se hvad der allerede findes.</p>

    <div class="members" role="tablist" aria-label="Gruppens symboler">
      {#each group.members as m}
        <button role="tab" aria-selected={m === element} class:active={m === element} onclick={() => pick(m)}>
          {nameOf(m)}{#if withAnims.has(m)} <span class="dot" title="Har animationer fra denne gruppe"></span>{/if}
        </button>
      {/each}
    </div>

    <div class="body">
      {#if !group.members.length}
        <p class="muted">Gruppen har ingen symboler endnu.</p>
      {:else if loading}
        <p class="muted">Henter …</p>
      {:else}
        <OwnerAnims {owners} {symbol} />
        <h4 style:color={color}>Gruppens animationer på {element} ({mine.length}/{MAX_ANIMS})</h4>
        {#each mine as a, i}
          {@const kind = kindOf(a)}
          <div class="anim">
            <div class="row wrap">
              <select bind:value={a.part} onchange={() => resetParams(a)} aria-label="Del">
                {#each partIds as p}<option value={p}>{partLabel(p, symbol)}</option>{/each}
              </select>
              <select bind:value={a.type} onchange={() => resetParams(a)} aria-label="Animation">
                {#each typesFor(partInfo(a.part)) as t}<option value={t}>{ANIM_TXT[t]}</option>{/each}
              </select>
              <span class="small muted">styres af</span>
              <select value={srcMode(a)} onchange={(e) => setSrcMode(a, e.currentTarget.value)} aria-label="Kilde">
                <option value="tag">et tag</option>
                {#if !['level', 'opacity', 'scale', 'text'].includes(a.type)}<option value="alarm">en alarm</option><option value={ON}>altid til</option>{/if}
              </select>
              {#if srcMode(a) === 'tag'}<TagSelect value={a.src} {tags} onchange={(v) => { const was = a.src; a.src = v; resetParams(a, was); }} />{/if}
              {#if srcMode(a) === 'alarm'}
                {@const al = parseAlarmRef(a.src)!}
                <select value={al.kind} onchange={(e) => (a.src = alarmRef(e.currentTarget.value as 'active' | 'unack', al.tag))} aria-label="Alarmtilstand">
                  <option value="active">er aktiv</option><option value="unack">er ukvitteret</option>
                </select>
                <span class="small muted">på</span>
                <TagSelect value={al.tag} {tags} onchange={(v) => { a.src = alarmRef(al.kind, v); resetParams(a); }} />
              {/if}
              <span class="spacer"></span>
              <button class="small" onclick={() => moveAnim(i, -1)} disabled={i === 0} aria-label="Op">▲</button>
              <button class="small" onclick={() => moveAnim(i, 1)} disabled={i === mine.length - 1} aria-label="Ned">▼</button>
              <button class="small" onclick={() => mine.splice(i, 1)} aria-label="Fjern animation">✕</button>
            </div>
            <AnimParams {a} {kind} {tags} valueOf={() => undefined} metaOf={(t) => { const r = tagByName.get(t); return r ? ({ unit: r.unit } as never) : undefined; }} />
            {#if WHEN_TYPES.includes(a.type)}
              <label class="opt small">Når den ikke er aktiv:
                <select value={a.when ? 'when' : 'toggle'} onchange={(e) => (a.when = e.currentTarget.value === 'when')} aria-label="Når den ikke er aktiv">
                  <option value="toggle">vis fra-tilstand</option>
                  <option value="when">gør ingenting (passiv)</option>
                </select>
              </label>
            {/if}
          </div>
        {:else}
          <p class="small muted">Ingen animationer fra gruppen på dette symbol endnu.</p>
        {/each}
        <button class="small" onclick={addAnim} disabled={mine.length >= MAX_ANIMS}>+ Animation</button>
        <p class="small muted">Flere animationer af samme slags på samme del: den <strong>øverste aktive</strong> vinder. Symbolets egne og gruppernes ligger i kæde — gruppernes kommer efter symbolets egne, så uden "passiv" vinder den sidste af samme slags.</p>
      {/if}
      {#if error}<p class="error">{error}</p>{/if}
      {#if info}<p class="small muted">{info}</p>{/if}
    </div>

    <footer class="row">
      <span class="spacer"></span>
      <button onclick={close}>Luk</button>
      <button class="primary" onclick={save} disabled={busy || loading || !dirty || !group.members.length}>Gem for {element}</button>
    </footer>
  </div>
</div>

<style>
  .backdrop { position: fixed; inset: 0; background: rgba(0, 0, 0, .35); display: flex; align-items: flex-start; justify-content: center; padding: 4vh 16px 0; z-index: 25; }
  .dlg { width: 100%; max-width: 900px; max-height: 92vh; display: flex; flex-direction: column; box-shadow: 0 8px 30px rgba(0, 0, 0, .25); border-top: 4px solid var(--c); }
  .head { align-items: baseline; gap: .6rem; }
  .head h2 { margin: 0; font-size: 1.15rem; }
  .chip { display: inline-block; width: .8rem; height: .8rem; border-radius: 3px; vertical-align: middle; }
  .close { margin-left: auto; }
  .members { display: flex; flex-wrap: wrap; gap: .25rem; margin: .4rem 0; border-bottom: 1px solid var(--line); padding-bottom: .4rem; }
  .members button.active { background: var(--c); color: #fff; border-color: var(--c); }
  .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--c); margin-left: .25rem; }
  .members button.active .dot { background: #fff; }
  .body { overflow: auto; flex: 1; min-height: 200px; padding-right: .3rem; }
  .body h4 { margin: .8rem 0 .3rem; }
  .anim { border: 1px solid var(--line); border-left: 5px solid var(--c); border-radius: var(--radius); padding: .4rem; margin: .35rem 0; background: var(--panel-2); }
  .wrap { flex-wrap: wrap; gap: .35rem .6rem; align-items: center; }
  .opt { display: inline-flex; align-items: center; gap: .3rem; }
  .spacer { flex: 1; }
  footer { gap: .5rem; align-items: center; border-top: 1px solid var(--line); padding-top: .5rem; margin-top: .5rem; }
  .error { color: var(--alarm); }
  .anim :global(select) { width: auto; max-width: 15em; }
</style>
