<script lang="ts">
  // Symbol-oversigt (v5.5.0): alle symboler på tegningen som et træ — ét sted at gå til dem for at rette dem.
  // Niveau 1: Grundsymboler · Signalveje · Grupper. Niveau 2: vejens elementer · gruppens medlemmer. Ingen ny redigeringslogik:
  // rækkerne åbner de eksisterende guider og dialoger.
  import { onDestroy } from 'svelte';
  import { get } from './api';
  import { listGroups, type SymbolGroup } from './symbolGroups';
  import { buildTree, countSymbols, filterTree, type PathRow, type SymbolRow, type TreeNode } from './symbolTree';

  let { drawingId, rev = 0, ready, select, onguide, ongroup }: {
    drawingId: string | null; rev?: number; ready: boolean;
    /** Markér elementerne på tegningen */
    select: (ids: string[]) => number;
    /** Symbol-guiden (6 trin): grundsymbol (elementet) eller signalvej (`sv~<id>`) */
    onguide: (id: string, name: string) => void;
    /** Gruppens animationer */
    ongroup: (g: SymbolGroup) => void;
  } = $props();

  let symbols = $state<SymbolRow[]>([]);
  let paths = $state<PathRow[]>([]);
  let groups = $state<SymbolGroup[]>([]);
  let error = $state('');
  let note = $state('');
  let query = $state('');
  let onlyOpen = $state(false);
  let open = $state<Set<string>>(new Set(['s:symbols', 's:paths', 's:groups']));
  let timer: ReturnType<typeof setTimeout> | undefined;
  let seq = 0;

  async function load(): Promise<void> {
    const id = drawingId;
    if (!id) { symbols = []; paths = []; groups = []; return; }
    const mine = ++seq;
    const enc = encodeURIComponent(id);
    const [s, p, g] = await Promise.allSettled([get<SymbolRow[]>(`/api/drawings/${enc}/symbols`), get<PathRow[]>(`/api/drawings/${enc}/signal-paths`), listGroups(id)]);
    if (mine !== seq) return;       // et nyere opslag er på vej
    symbols = s.status === 'fulfilled' ? s.value : [];
    paths = p.status === 'fulfilled' ? p.value : [];
    groups = g.status === 'fulfilled' ? g.value : [];
    const bad = [s, p, g].find((x) => x.status === 'rejected') as PromiseRejectedResult | undefined;
    error = bad ? `Oversigten kunne ikke hentes helt: ${(bad.reason as Error).message}` : '';
  }
  // tegningen ændres hele tiden (flyt, træk …): hent først, når det har ligget stille et øjeblik
  $effect(() => {
    void drawingId; void rev;
    clearTimeout(timer);
    timer = setTimeout(() => void load(), 500);
  });
  onDestroy(() => clearTimeout(timer));

  const tree = $derived(buildTree(symbols, paths, groups));
  const shown = $derived(filterTree(tree, query, onlyOpen));
  const counts = $derived(countSymbols(symbols));
  const filtering = $derived(query.trim() !== '' || onlyOpen);

  const isOpen = (n: TreeNode) => filtering || open.has(n.key);
  function toggle(n: TreeNode): void {
    const next = new Set(open);
    if (next.has(n.key)) next.delete(n.key); else next.add(n.key);
    open = next;
  }
  function pick(n: TreeNode): void {
    if (!n.ids.length) return;
    const found = select(n.ids);
    note = found === n.ids.length ? '' : `${n.ids.length - found} af ${n.ids.length} findes ikke i den aktive version af tegningen.`;
  }
  const groupOf = (n: TreeNode) => groups.find((g) => g.id === n.group);
</script>

<div class="row small">
  <input bind:value={query} placeholder="Søg symbol, vej eller gruppe" aria-label="Søg i symbol-oversigten" class="grow" />
  <label class="opt" title="Vis kun de symboler og veje, der endnu ikke har en opsætning"><input type="checkbox" bind:checked={onlyOpen} /> ikke opsatte</label>
</div>
<p class="small muted">{counts.configured} af {counts.total} grundsymboler er opsat.</p>
{#if error}<p class="small error">{error}</p>{/if}
{#if note}<p class="small warn">{note}</p>{/if}

{#snippet node(n: TreeNode, depth: number)}
  <div class="trow" class:section={n.kind === 'section'} style="padding-left: {depth * 0.9}rem">
    {#if n.children.length}
      <button class="tg" onclick={() => toggle(n)} aria-label={isOpen(n) ? 'Fold sammen' : 'Fold ud'} aria-expanded={isOpen(n)}>{isOpen(n) ? '▾' : '▸'}</button>
    {:else}<span class="tg"></span>{/if}
    {#if n.kind === 'section'}
      <button class="lbl strong" onclick={() => toggle(n)}>{n.label} <span class="muted small">({n.sub})</span></button>
    {:else}
      <button class="lbl" onclick={() => pick(n)} disabled={!ready || !n.ids.length} title="Vælg på tegningen">
        {n.label}{#if n.sub} <span class="muted small sub">{n.sub}</span>{/if}{#if n.configured}<span class="ok" title="Har en opsætning">✓</span>{/if}
      </button>
      {#if n.guide}
        <button class="small" onclick={() => onguide(n.guide!.id, n.guide!.name)} disabled={!ready}
          title={n.kind === 'path' ? 'Åbn vejen som symbol (6 trin): egne animationer, logik og signaler' : 'Opsæt symbolet (6 trin)'}>Opsæt</button>
      {:else if n.group !== null && groupOf(n)}
        <button class="small" onclick={() => ongroup(groupOf(n)!)} disabled={!ready} title="Gruppens animationer">Animationer</button>
      {/if}
    {/if}
  </div>
  {#if n.children.length && isOpen(n)}
    {#each n.children as c (c.key)}{@render node(c, depth + 1)}{/each}
  {/if}
{/snippet}

{#each shown as s (s.key)}{@render node(s, 0)}{/each}
{#if !shown.length}
  <p class="small muted">{filtering ? 'Intet passer til søgningen.' : 'Ingen symboler, veje eller grupper på tegningen endnu.'}</p>
{/if}

<style>
  .trow { display: flex; align-items: center; gap: .25rem; padding-block: .1rem; min-width: 0; }
  .trow.section { margin-top: .3rem; border-top: 1px solid var(--line); padding-top: .25rem; }
  .tg { width: 1.2rem; flex: none; background: none; border: 0; padding: 0; cursor: pointer; color: var(--muted, #666); }
  .lbl { flex: 1; min-width: 0; text-align: left; background: none; border: 0; padding: .1rem .2rem; cursor: pointer; overflow-wrap: anywhere; font: inherit; color: inherit; }
  .lbl:hover:not(:disabled) { background: var(--panel-2, #f3f3f3); border-radius: 4px; }
  .lbl.strong { font-weight: 600; }
  .sub, .ok { margin-left: .35rem; }
  .ok { color: #2e7d32; }
  .warn { color: var(--warn); }
  .grow { flex: 1; min-width: 0; }
</style>
