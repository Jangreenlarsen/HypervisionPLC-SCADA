<script lang="ts">
  import { onDestroy, onMount, tick } from 'svelte';
  import { get, type Binding, type DrawingView, type LiveValue, type PlcSummary } from '../lib/api';
  import { byTag as indexByTag, mountSvg, renderAll, renderBinding } from '../lib/canvas';
  import { LiveClient } from '../lib/live';

  let { route = 'overview', canEdit = false }: { route?: string; canEdit?: boolean } = $props();

  let drawings = $state<{ id: string; name: string }[]>([]);
  let selected = $state('');
  let view = $state<DrawingView | null>(null);
  let error = $state('');
  let plcs = $state<Record<string, PlcSummary>>({});
  let connected = $state(false);
  let container: HTMLDivElement;

  const values: Record<string, LiveValue> = {};
  let byTag = new Map<string, Binding[]>();

  const live = new LiveClient(
    (changes) => {
      Object.assign(values, changes);
      for (const name of Object.keys(changes)) for (const b of byTag.get(name) ?? []) render(b);
    },
    (p, c) => {
      plcs = p;
      connected = c;
    },
  );

  function render(b: Binding): void {
    if (container && view) renderBinding(container, b, values, view.tags);
  }

  async function load(id: string): Promise<void> {
    error = '';
    if (!id) return;
    try {
      view = await get<DrawingView>(`/api/drawings/${encodeURIComponent(id)}/view`);
      location.hash = `overview/${id}`;
      await tick();
      mountSvg(container, view.svg);
      byTag = indexByTag(view.bindings);
      renderAll(container, view.bindings, values, view.tags);
      live.subscribe([...byTag.keys()]);
    } catch (e) {
      view = null;
      error = `Kunne ikke vise tegningen: ${(e as Error).message}`;
    }
  }

  onMount(async () => {
    try {
      drawings = await get<{ id: string; name: string }[]>('/api/drawings');
    } catch (e) {
      error = (e as Error).message;
      return;
    }
    const fromRoute = route.split('/')[1];
    selected = fromRoute && drawings.some((d) => d.id === fromRoute) ? fromRoute : drawings[0]?.id ?? '';
    await load(selected);
  });

  onDestroy(() => live.close());

  const problems = $derived(Object.entries(plcs).filter(([, p]) => p.state === 'error'));
</script>

<div class="toolbar row">
  <select bind:value={selected} onchange={() => load(selected)} aria-label="Vælg tegning">
    {#each drawings as d}<option value={d.id}>{d.name}</option>{/each}
  </select>
  {#if canEdit && selected}<a href={'#editor/' + selected}>Redigér bindinger</a>{/if}
  <span class="badge {connected ? 'connected' : 'error'}">{connected ? 'Live' : 'Ingen forbindelse'}</span>
  {#each Object.entries(plcs) as [key, p]}
    <span class="badge {p.state}" title={p.message || p.state}>{p.name || key}: {p.state}{p.sse === 'connected' ? ' · SSE' : ''}</span>
  {/each}
</div>

{#if error}<div class="error">{error}</div>{/if}
{#each problems as [key, p]}
  <div class="error">PLC {p.name || key}: {p.message}</div>
{/each}
{#if !connected}
  <div class="notice">Forbindelsen til SCADA-serveren er afbrudt — værdierne er ikke opdaterede. Forsøger igen …</div>
{/if}
{#if view && view.orphaned_bindings.length}
  <div class="notice">Bindinger til elementer der ikke findes i denne version: {view.orphaned_bindings.join(', ')}</div>
{/if}

{#if !drawings.length && !error}
  <div class="panel">Ingen tegninger endnu. <a href="#drawings">Upload en SVG-tegning</a> for at komme i gang.</div>
{/if}

<div class="canvas" bind:this={container}></div>

<style>
  .toolbar { margin-bottom: .75rem; }
  .canvas {
    background: var(--panel-2);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    padding: .5rem;
    min-height: 200px;
  }
  .canvas :global(svg) {
    display: block;
    width: 100%;
    height: auto;
    max-height: calc(100vh - 170px);
  }
</style>
