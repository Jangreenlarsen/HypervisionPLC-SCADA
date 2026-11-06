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
    layers(): Layer[];
    layerOp(op: 'new' | 'rename' | 'visible' | 'lock' | 'current' | 'delete' | 'moveSel', name: string, arg?: unknown): { ok?: boolean; error?: string };
  }
  interface Layer { name: string; visible: boolean; locked: boolean; current: boolean; count: number }

  let { api, rev, onchange, count = $bindable(0) }: { api: TreeApi | null; rev: number; onchange?: () => void; count?: number } = $props();
  let layers = $state<{ layer: string; items: Item[] }[]>([]);
  let filter = $state('');
  let layerInfo = $state<Layer[]>([]);
  let layerError = $state('');
  let newLayer = $state('');
  let renaming = $state<string | null>(null);
  let renameText = $state('');

  $effect(() => {
    void rev;
    layers = api?.objectList() ?? [];
    layerInfo = api?.layers?.() ?? [];
  });

  /** Lag-handling (v3.33.0) — fejlen vises under lagene; træet og panelerne læses igen. */
  function layerOp(op: Parameters<TreeApi['layerOp']>[0], name: string, arg?: unknown): boolean {
    if (!api) return false;
    const r = api.layerOp(op, name, arg);
    layerError = r?.error ?? '';
    layers = api.objectList();
    layerInfo = api.layers();
    onchange?.();
    return !r?.error;
  }

  const TAG_LABEL: Record<string, string> = {
    rect: 'Rektangel', ellipse: 'Ellipse', circle: 'Cirkel', line: 'Linje', path: 'Sti', polyline: 'Linje', polygon: 'Polygon',
    text: 'Tekst', g: 'Gruppe', image: 'Billede',
  };
  const typeLabel = (it: Item): string =>
    it.pipe ? 'Forbindelse' : SYMBOLS.find((s) => s.id === it.type)?.label ?? TAG_LABEL[it.tag] ?? it.tag;
  const label = (it: Item): string => it.name || typeLabel(it);
  $effect(() => { count = layers.reduce((n, l) => n + l.items.length, 0); });
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

<div class="tree">
  <details class="layers" open={layerInfo.length > 1}>
    <summary>Lag <span class="muted small">({layerInfo.length})</span></summary>
    {#each layerInfo as l (l.name)}
      <div class="lrow" class:cur={l.current}>
        {#if renaming === l.name}
          <input bind:value={renameText} maxlength="40" aria-label="Lagets navn" onkeydown={(e) => { if (e.key === 'Enter' && layerOp('rename', l.name, renameText)) renaming = null; if (e.key === 'Escape') renaming = null; }} />
          <button class="small" onclick={() => { if (layerOp('rename', l.name, renameText)) renaming = null; }}>Gem</button>
        {:else}
          <button class="lname" onclick={() => layerOp('current', l.name)} title="Gør til det aktive lag — nye elementer tegnes her">
            {l.current ? '●' : '○'} {l.name} <span class="muted small">({l.count})</span>
          </button>
          <button class="ic" class:off={!l.visible} onclick={() => layerOp('visible', l.name, !l.visible)} title={l.visible ? 'Skjul laget i Tegn' : 'Vis laget'} aria-label={l.visible ? `Skjul ${l.name}` : `Vis ${l.name}`}>{l.visible ? 'Vis' : 'Skjult'}</button>
          <button class="ic" class:on={l.locked} onclick={() => layerOp('lock', l.name, !l.locked)} title={l.locked ? 'Lås op' : 'Lås laget — elementerne kan ikke vælges i Tegn'} aria-label={l.locked ? `Lås ${l.name} op` : `Lås ${l.name}`}>{l.locked ? 'Låst' : 'Lås'}</button>
          {#if anySelected && !l.current}<button class="ic" onclick={() => layerOp('moveSel', l.name)} title="Flyt det valgte til dette lag">Flyt hertil</button>{/if}
          <button class="ic" onclick={() => { renaming = l.name; renameText = l.name; }} title="Omdøb" aria-label="Omdøb {l.name}">Omdøb</button>
          {#if layerInfo.length > 1 && !l.count}<button class="ic danger" onclick={() => layerOp('delete', l.name)} title="Slet det tomme lag" aria-label="Slet {l.name}">Slet</button>{/if}
        {/if}
      </div>
    {/each}
    <div class="lrow">
      <input bind:value={newLayer} maxlength="40" placeholder="Nyt lag" aria-label="Navn på nyt lag" onkeydown={(e) => { if (e.key === 'Enter' && layerOp('new', '', newLayer)) newLayer = ''; }} />
      <button class="small" onclick={() => { if (layerOp('new', '', newLayer)) newLayer = ''; }}>Opret</button>
    </div>
    {#if layerError}<p class="error small" role="alert">{layerError}</p>{/if}
    <p class="muted small">Skjul og lås gælder kun i Tegn. Den gemte tegning og Overview viser altid alle lag.</p>
  </details>
  <div class="top">
    {#if count > 8}<input class="filter" placeholder="Find element" bind:value={filter} aria-label="Find element" />{/if}
    {#if anySelected}
      <span class="ord">
        <button class="small" onclick={() => order('up')} title="Ét trin frem (over de andre)" aria-label="Frem">▲</button>
        <button class="small" onclick={() => order('down')} title="Ét trin tilbage (under de andre)" aria-label="Tilbage">▼</button>
      </span>
    {/if}
  </div>
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
</div>

<style>
  .layers { margin-bottom: .4rem; border-bottom: 1px solid var(--line); padding-bottom: .3rem; }
  .layers summary { cursor: pointer; font-size: .85rem; font-weight: 600; }
  .lrow { display: flex; gap: 2px; align-items: center; flex-wrap: wrap; padding: 1px 2px; border-radius: 4px; }
  .lrow.cur { background: #eef4ff; }
  .lrow input { flex: 1; min-width: 0; font-size: .85rem; }
  .lname { flex: 1; text-align: left; border: 0; background: transparent; padding: 2px 4px; font-size: .85rem; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ic { font-size: .72rem; padding: 1px 5px; }
  .ic.off { opacity: .6; font-style: italic; }
  .ic.on { background: #fff3cd; border-color: #e0b84c; }
  .ic.danger { color: #b3261e; }
  .top { display: flex; gap: .4rem; align-items: center; margin-bottom: .3rem; }
  .ord { margin-left: auto; display: flex; gap: 2px; }
  .filter { flex: 1; min-width: 0; }
  .list { display: flex; flex-direction: column; }
  .layer { font-size: .75rem; color: #777; text-transform: uppercase; margin: .3rem 0 .1rem; }
  .item { display: flex; justify-content: space-between; gap: .5rem; border: 0; background: transparent; text-align: left; padding: 2px 6px; border-radius: 4px; font-size: .88rem; }
  .item:hover { background: #eef2f8; }
  .item.on { background: #dbe8ff; }
  .name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .kind { color: #888; font-size: .75rem; white-space: nowrap; }
</style>
