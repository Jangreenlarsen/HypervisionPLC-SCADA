<script lang="ts">
  // Objekttræet i den nye tegne-editor: tegningens elementer pr. lag, forrest øverst. Klik vælger, Ctrl/Shift-klik
  // tilføjer/fjerner, ▲▼ flytter det valgte frem/tilbage. Gør det let at finde et element under et andet.
  import { SYMBOLS } from '../symbols';

  interface Item { id: string; name: string; type: string; tag: string; pipe: boolean; selected: boolean }
  export interface TreeApi {
    objectList(): { layer: string; items: Item[] }[];
    selectByIds(ids: string[]): number;
    toggleSelected(id: string): void;
    order(where: 'up' | 'down' | 'top' | 'bottom'): void;
  }

  let { api, rev, onchange }: { api: TreeApi | null; rev: number; onchange?: () => void } = $props();
  let layers = $state<{ layer: string; items: Item[] }[]>([]);
  let filter = $state('');
  let open = $state(true);

  $effect(() => {
    void rev;
    layers = api?.objectList() ?? [];
  });

  const TAG_LABEL: Record<string, string> = {
    rect: 'Rektangel', ellipse: 'Ellipse', circle: 'Cirkel', line: 'Linje', path: 'Sti', polyline: 'Linje', polygon: 'Polygon',
    text: 'Tekst', g: 'Gruppe', image: 'Billede',
  };
  const typeLabel = (it: Item): string =>
    it.pipe ? 'Rør' : SYMBOLS.find((s) => s.id === it.type)?.label ?? TAG_LABEL[it.tag] ?? it.tag;
  const label = (it: Item): string => it.name || typeLabel(it);
  const count = $derived(layers.reduce((n, l) => n + l.items.length, 0));
  const shown = $derived(layers.map((l) => ({
    ...l,
    items: filter.trim() ? l.items.filter((it) => `${label(it)} ${typeLabel(it)} ${it.id}`.toLowerCase().includes(filter.trim().toLowerCase())) : l.items,
  })));
  const anySelected = $derived(layers.some((l) => l.items.some((it) => it.selected)));

  function pick(e: MouseEvent, id: string): void {
    if (!api) return;
    if (e.ctrlKey || e.metaKey || e.shiftKey) api.toggleSelected(id);
    else api.selectByIds([id]);
    layers = api.objectList();
    onchange?.();
  }
  function order(where: 'up' | 'down'): void {
    api?.order(where);
    layers = api?.objectList() ?? [];
    onchange?.();
  }
</script>

<section class="panel tree" aria-label="Objekter">
  <h3>
    <button class="toggle" onclick={() => (open = !open)} aria-expanded={open}>{open ? '▾' : '▸'} Objekter</button>
    <span class="muted small">{count}</span>
    {#if open && anySelected}
      <span class="ord">
        <button class="small" onclick={() => order('up')} title="Ét trin frem (over de andre)" aria-label="Frem">▲</button>
        <button class="small" onclick={() => order('down')} title="Ét trin tilbage (under de andre)" aria-label="Tilbage">▼</button>
      </span>
    {/if}
  </h3>
  {#if open}
    {#if count > 8}<input class="filter" placeholder="Find element" bind:value={filter} aria-label="Find element" />{/if}
    <div class="list">
      {#each shown as l}
        {#if layers.length > 1}<div class="layer">{l.layer}</div>{/if}
        {#each l.items as it (it.id)}
          <button class="item" class:on={it.selected} onclick={(e) => pick(e, it.id)} title="{typeLabel(it)} · id {it.id} — Ctrl/Shift-klik vælger flere">
            <span class="name">{label(it)}</span>
            {#if it.name && it.name !== typeLabel(it)}<span class="kind">{typeLabel(it)}</span>{/if}
          </button>
        {/each}
      {/each}
      {#if !count}<p class="muted small">Tegningen er tom.</p>{/if}
    </div>
  {/if}
</section>

<style>
  .tree h3 { display: flex; align-items: center; gap: .5rem; }
  .toggle { border: 0; background: none; padding: 0; font: inherit; font-weight: inherit; cursor: pointer; }
  .ord { margin-left: auto; display: flex; gap: 2px; }
  .filter { width: 100%; margin-bottom: .3rem; }
  .list { max-height: 14rem; overflow-y: auto; display: flex; flex-direction: column; }
  .layer { font-size: .75rem; color: #777; text-transform: uppercase; margin: .3rem 0 .1rem; }
  .item { display: flex; justify-content: space-between; gap: .5rem; border: 0; background: transparent; text-align: left; padding: 2px 6px; border-radius: 4px; font-size: .88rem; }
  .item:hover { background: #eef2f8; }
  .item.on { background: #dbe8ff; }
  .name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .kind { color: #888; font-size: .75rem; white-space: nowrap; }
</style>
