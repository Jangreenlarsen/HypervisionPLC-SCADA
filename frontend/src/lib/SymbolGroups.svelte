<script lang="ts">
  // Sektionen "Grupper" i Tegns symbolliste (v0.130.0): gem markeringen som en navngiven gruppe, markér en gruppes symboler,
  // tilføj/fjern de markerede, omdøb, skift art og slet. Samme symbol må være med i flere grupper.
  import { onMount } from 'svelte';
  import GroupAnims from './GroupAnims.svelte';
  import { ask, askText } from './ask';
  import {
    KIND_HINT, KIND_TXT, changeMembers, createGroup, deleteGroup, groupColor, groupsOf, listGroups, movedOrder, ofKind, reorderGroups, updateGroup,
    type GroupKind, type SymbolGroup,
  } from './symbolGroups';

  let { drawingId, selectedIds, select, onchange, tags = [] }: {
    drawingId: string | null;
    tags?: { name: string; source: string; unit: string; writable: boolean; plc: string }[];
    selectedIds: string[];
    /** Markér elementerne på tegningen; returnerer hvor mange der blev fundet */
    select: (ids: string[]) => number;
    onchange?: (groups: SymbolGroup[]) => void;
  } = $props();

  let groups = $state<SymbolGroup[]>([]);
  let error = $state('');
  let info = $state('');
  let busy = $state(false);
  let active = $state<number | null>(null);   // gruppen der sidst blev markeret
  let newKind = $state<GroupKind>('selection');
  let animsFor = $state<SymbolGroup | null>(null);   // gruppen hvis animationer redigeres

  async function refresh(): Promise<void> {
    if (!drawingId) { groups = []; return; }
    try { groups = await listGroups(drawingId); error = ''; onchange?.(groups); }
    catch (e) { error = `Grupperne kunne ikke hentes: ${(e as Error).message}`; }
  }
  onMount(refresh);
  $effect(() => { drawingId; void refresh(); });

  async function run(what: string, fn: () => Promise<void>): Promise<void> {
    busy = true; error = info = '';
    try { await fn(); await refresh(); }
    catch (e) { error = `${what} fejlede: ${(e as Error).message}`; }
    finally { busy = false; }
  }

  async function saveSelection(): Promise<void> {
    if (!drawingId || !selectedIds.length) return;
    const name = await askText(`Navn på gruppen (${selectedIds.length} valgte):`,
      { placeholder: newKind === 'function' ? 'fx Fyr uden akku-tank' : 'fx Kedelrum', ok: 'Gem gruppe' });
    if (!name?.trim()) return;
    await run('Gem gruppe', async () => {
      const g = await createGroup(drawingId!, name.trim(), newKind, selectedIds);
      info = `Gruppen "${g.name}" er gemt med ${g.members.length} symboler.`;
    });
  }

  function pick(g: SymbolGroup): void {
    active = g.id;
    const found = select(g.members);
    info = found === g.members.length ? `${found} symboler markeret.`
      : `${found} af ${g.members.length} symboler findes på tegningen (resten er slettet eller har fået nyt id).`;
  }

  // Tilføj/fjern sender kun de valgte (serveren ændrer enkelte medlemmer) — en forældet skærm kan ikke overskrive andres ændringer
  const addSelected = (g: SymbolGroup) => run('Tilføj', async () => { await changeMembers(drawingId!, g.id, selectedIds, []); });
  const removeSelected = (g: SymbolGroup) => run('Fjern', async () => { await changeMembers(drawingId!, g.id, [], selectedIds); });
  const move = (g: SymbolGroup, dir: -1 | 1) => {
    const ids = movedOrder(groups, g.id, dir);
    if (ids) void run('Flyt', async () => { await reorderGroups(drawingId!, ids); });
  };
  const replaceWithSelected = (g: SymbolGroup) => run('Opdatér', async () => { await updateGroup(drawingId!, g, selectedIds); });
  async function rename(g: SymbolGroup): Promise<void> {
    const name = await askText('Nyt navn på gruppen:', { value: g.name, ok: 'Omdøb' });
    if (!name?.trim() || name.trim() === g.name) return;
    await run('Omdøb', async () => { await updateGroup(drawingId!, { ...g, name: name.trim() }); });
  }
  const toggleKind = (g: SymbolGroup) =>
    run('Skift art', async () => { await updateGroup(drawingId!, { ...g, kind: g.kind === 'function' ? 'selection' : 'function' }); });
  async function remove(g: SymbolGroup): Promise<void> {
    if (!(await ask(`Slet gruppen "${g.name}"? Symbolerne selv slettes ikke.`, { ok: 'Slet', danger: true }))) return;
    await run('Slet', async () => { await deleteGroup(drawingId!, g.id); if (active === g.id) active = null; });
  }
  const mark = (id: string) => groupsOf(groups, id).map((g) => g.name).join(', ');
</script>

<div class="groups">
  {#if !drawingId}
    <p class="small muted">Gem tegningen først, så kan du lave grupper.</p>
  {:else}
    <div class="row new">
      <select bind:value={newKind} aria-label="Art" title={KIND_HINT[newKind]}>
        <option value="selection">{KIND_TXT.selection}</option><option value="function">{KIND_TXT.function}</option>
      </select>
      <button class="small primary" onclick={saveSelection} disabled={busy || !selectedIds.length}
        title="Gem de valgte symboler som en navngiven gruppe. Samme symbol må gerne være med i flere grupper.">Gem markering som gruppe ({selectedIds.length})</button>
    </div>
    {#if error}<p class="small error">{error}</p>{/if}
    {#if info}<p class="small muted">{info}</p>{/if}
    {#each ['function', 'selection'] as const as kind}
      {@const list = ofKind(groups, kind)}
      {#if list.length}
        <h4 class="kind" title={KIND_HINT[kind]}>{KIND_TXT[kind]} <span class="muted small">({list.length})</span></h4>
        {#each list as g (g.id)}
          <div class="grp" class:active={active === g.id}>
            <span class="chip" style:background={groupColor(g.id)} title="Gruppens farve i animationsoversigten"></span>
            <button class="pick" onclick={() => pick(g)} title="Markér gruppens symboler på tegningen">{g.name} <span class="muted small">({g.members.length})</span></button>
            <span class="order">
              <button class="small" onclick={() => move(g, -1)} disabled={busy || !movedOrder(groups, g.id, -1)} aria-label="Flyt op" title="Rækkefølge: symbolets egne animationer først, derefter funktionsgrupper, så udvalg — hver art oppefra og ned. Uden passiv vinder den sidste aktive; med passiv den øverste aktive.">▲</button>
              <button class="small" onclick={() => move(g, 1)} disabled={busy || !movedOrder(groups, g.id, 1)} aria-label="Flyt ned">▼</button>
            </span>
            <details class="more">
              <summary class="small" aria-label="Redigér gruppen {g.name}">⋯</summary>
              <div class="row wrap small">
                <button class="small" onclick={() => addSelected(g)} disabled={busy || !selectedIds.length}>Tilføj valgte</button>
                <button class="small" onclick={() => removeSelected(g)} disabled={busy || !selectedIds.length}>Fjern valgte</button>
                <button class="small" onclick={() => replaceWithSelected(g)} disabled={busy || !selectedIds.length} title="Gruppen får præcis de valgte symboler">Sæt til valgte</button>
                <button class="small" onclick={() => (animsFor = g)} disabled={busy || !g.members.length} title="Sæt animationer op, som gælder alle gruppens symboler ud over deres egne">Animationer …</button>
                <button class="small" onclick={() => rename(g)} disabled={busy}>Omdøb</button>
                <button class="small" onclick={() => toggleKind(g)} disabled={busy}>Flyt til {KIND_TXT[g.kind === 'function' ? 'selection' : 'function']}</button>
                <button class="small danger" onclick={() => remove(g)} disabled={busy}>Slet</button>
              </div>
            </details>
          </div>
        {/each}
      {/if}
    {/each}
    {#if !groups.length}<p class="small muted">Ingen grupper endnu. Vælg flere symboler i tegningen og tryk "Gem markering som gruppe".</p>{/if}
    {#if selectedIds.length === 1 && mark(selectedIds[0])}<p class="small muted">Det valgte symbol er med i: {mark(selectedIds[0])}</p>{/if}
  {/if}
</div>

{#if animsFor && drawingId}
  <GroupAnims {drawingId} group={animsFor} {tags} onclose={() => (animsFor = null)} />
{/if}

<style>
  .groups { display: flex; flex-direction: column; gap: .3rem; }
  .new { gap: .4rem; flex-wrap: wrap; }
  .kind { margin: .4rem 0 0; font-size: .9rem; }
  .grp { display: flex; flex-wrap: wrap; align-items: flex-start; gap: .3rem; border: 1px solid var(--line); border-radius: var(--radius); padding: .15rem .3rem; }
  .grp.active { border-color: #5ccf6e; background: rgba(92, 207, 110, .15); }
  .pick { flex: 1; text-align: left; background: none; border: none; padding: .2rem .3rem; cursor: pointer; overflow-wrap: anywhere; }
  .chip { flex: 0 0 auto; width: .7rem; height: .7rem; border-radius: 3px; margin-top: .45rem; }
  .order { flex: 0 0 auto; display: inline-flex; gap: .1rem; }
  .more { flex: 0 0 auto; }
  .more[open] { flex: 1 1 100%; }
  .more summary { cursor: pointer; padding: .2rem .4rem; }
</style>
