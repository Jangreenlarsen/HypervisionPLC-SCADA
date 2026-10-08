<script lang="ts">
  import { onDestroy, onMount, tick } from 'svelte';
  import { get, post, type Binding, type DrawingView, type LiveValue, type PlcSummary } from '../lib/api';
  import { clickFor, parseSetpoint, rangeText, toggleQuestion } from '../lib/actions';
  import { formatValue } from '../lib/animate';
  import { byTag as indexByTag, fitSvg, mountSvg, onLayoutChange, renderAll, renderBinding } from '../lib/canvas';
  import { LiveClient } from '../lib/live';

  let { route = 'overview', canEdit = false, canOperate = false }: { route?: string; canEdit?: boolean; canOperate?: boolean } = $props();

  interface Dialog { binding: Binding; step: 'input' | 'confirm'; input: string; value: number | null; error: string; busy: boolean }
  interface Toast { kind: 'ok' | 'warn' | 'error'; text: string }

  let drawings = $state<{ id: string; name: string }[]>([]);
  let selected = $state('');
  let view = $state<DrawingView | null>(null);
  let error = $state('');
  let plcs = $state<Record<string, PlcSummary>>({});
  let connected = $state(false);
  let dialog = $state<Dialog | null>(null);
  let toast = $state<Toast | null>(null);
  let container: HTMLDivElement;
  let svgRoot: SVGSVGElement | null = null;
  let stopLayout: (() => void) | null = null;

  /** Tegningen fylder den ledige plads i vinduet med sine proportioner (genberegnes ved resize/zoom). */
  const fit = () => fitSvg(svgRoot, container);
  let toastTimer: ReturnType<typeof setTimeout>;

  const values: Record<string, LiveValue> = {};
  let byTag = new Map<string, Binding[]>();

  let alarmTags = new Map<string, 'unack' | 'ack'>();

  function markAlarms(): void {
    if (!container || !view) return;
    for (const b of view.bindings) {
      if (!b.tag) continue;
      const el = container.querySelector(`#${CSS.escape(b.element)}`);
      if (!el) continue;
      const st = alarmTags.get(b.tag);
      el.classList.toggle('hv-alarm-unack', st === 'unack');
      el.classList.toggle('hv-alarm-ack', st === 'ack');
    }
  }

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

  live.onAlarms = (_s, active) => {
    const next = new Map<string, 'unack' | 'ack'>();
    for (const a of active) {
      if (!a.tag) continue; // PLC-kommunikationsalarmer vises i banneret, ikke på elementer
      const st = a.state === 'active_ack' ? 'ack' : 'unack';
      if (next.get(a.tag) !== 'unack') next.set(a.tag, st);
    }
    alarmTags = next;
    markAlarms();
  };

  function render(b: Binding): void {
    if (container && view) renderBinding(container, b, values, view.tags);
  }

  async function load(id: string): Promise<void> {
    error = '';
    if (!id) return;
    try {
      view = await get<DrawingView>(`/api/drawings/${encodeURIComponent(id)}/view`);
      selected = id;
      if (location.hash !== `#overview/${id}`) history.replaceState(null, '', `#overview/${id}`);
      await tick();
      svgRoot = mountSvg(container, view.svg);
      fit();
      byTag = indexByTag(view.bindings.filter((b) => b.tag));
      renderAll(container, view.bindings, values, view.tags);
      markAlarms();
      live.subscribe([...byTag.keys()]);
    } catch (e) {
      view = null;
      error = `Kunne ikke vise tegningen: ${(e as Error).message}`;
    }
  }

  function showToast(kind: Toast['kind'], text: string): void {
    toast = { kind, text };
    clearTimeout(toastTimer);
    if (kind === 'ok') toastTimer = setTimeout(() => (toast = null), 4000);
  }

  /** Første forfader med en klik-handling (klik rammer ofte et barn, fx teksten i en knap). */
  function clickTarget(target: Element | null): Binding | null {
    let el = target;
    while (el && el !== svgRoot && view) {
      if (el.id) {
        const b = clickFor(view.bindings, el.id);
        if (b) return b;
      }
      el = el.parentElement;
    }
    return null;
  }

  async function onCanvasClick(e: MouseEvent): Promise<void> {
    const b = clickTarget(e.target as Element);
    if (!b || !view) return;
    if (b.anim === 'click:goto') {
      if (drawings.some((d) => d.id === b.params.drawing)) await load(b.params.drawing);
      else showToast('error', `Tegningen "${b.params.drawing}" findes ikke længere`);
      return;
    }
    if (!canOperate) {
      showToast('error', 'Betjening kræver rollen operatør');
      return;
    }
    if (b.anim === 'click:write') {
      const v = values[b.tag]?.value;
      dialog = { binding: b, step: 'input', input: typeof v === 'number' ? String(v) : '', value: null, error: '', busy: false };
    } else if (b.params.confirm) {
      dialog = { binding: b, step: 'confirm', input: '', value: null, error: '', busy: false };
    } else {
      await execute(b, null);
    }
  }

  async function submitDialog(): Promise<void> {
    if (!dialog || !view) return;
    const b = dialog.binding;
    if (b.anim === 'click:write' && dialog.step === 'input') {
      try {
        dialog.value = parseSetpoint(dialog.input, view.tags[b.tag]);
      } catch (e) {
        dialog.error = (e as Error).message;
        return;
      }
      if (view.tags[b.tag]?.confirm_write) {
        dialog.step = 'confirm';
        dialog.error = '';
        return;
      }
    }
    dialog.busy = true;
    const ok = await execute(b, dialog.value);
    if (ok) dialog = null;
    else if (dialog) dialog.busy = false;
  }

  /** Udfør handlingen. Ved fejl vises serverens/PLC'ens egen fejltekst. */
  async function execute(b: Binding, value: number | null): Promise<boolean> {
    const tag = encodeURIComponent(b.tag);
    const meta = view?.tags[b.tag];
    const name = b.params.title || meta?.description || b.tag;
    try {
      if (b.anim === 'click:write') {
        const r = await post<{ written: number; matches: boolean; warning: string }>(`/api/tags/${tag}/write`, { value });
        if (r.matches) showToast('ok', `${name} sat til ${formatValue(r.written, meta)}`);
        else showToast('warn', r.warning);
      } else if (b.anim === 'click:toggle') {
        const r = await post<{ written: unknown; matches: boolean; warning: string }>(`/api/tags/${tag}/toggle`, {});
        if (r.matches) showToast('ok', `${name}: ${formatValue(r.written, meta)}`);
        else showToast('warn', r.warning);
      } else if (b.anim === 'click:pulse') {
        await post(`/api/tags/${tag}/pulse`, { ms: b.params.ms ?? 500 });
        showToast('ok', `Puls sendt til ${name}`);
      }
      return true;
    } catch (e) {
      if (dialog) dialog.error = (e as Error).message;
      else showToast('error', (e as Error).message);
      return false;
    }
  }

  function onKey(e: KeyboardEvent): void {
    if (!dialog || dialog.busy) return;
    if (e.key === 'Escape') dialog = null;
    else if (e.key === 'Enter') submitDialog();
  }

  onMount(async () => {
    stopLayout = onLayoutChange(fit, container);
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

  onDestroy(() => {
    stopLayout?.();
    live.close();
    clearTimeout(toastTimer);
  });

  const problems = $derived(Object.entries(plcs).filter(([, p]) => p.state === 'error'));
  const dMeta = $derived(dialog && view ? view.tags[dialog.binding.tag] : undefined);
  const dName = $derived(dialog ? dialog.binding.params.title || dMeta?.description || dialog.binding.tag : '');
  const dLive = $derived(dialog ? values[dialog.binding.tag] : undefined);
</script>

<svelte:window onkeydown={onKey} />

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

{#if toast}
  <div class={toast.kind === 'error' ? 'error' : toast.kind === 'warn' ? 'notice' : 'notice ok-toast'} role="status">
    {toast.text}
    {#if toast.kind !== 'ok'}<button class="small" onclick={() => (toast = null)}>OK</button>{/if}
  </div>
{/if}
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

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="canvas" bind:this={container} onclick={onCanvasClick}></div>

{#if dialog}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="backdrop" onclick={() => !dialog?.busy && (dialog = null)}>
    <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
    <div class="panel dialog" role="dialog" aria-modal="true" aria-label={dName} tabindex="-1" onclick={(e) => e.stopPropagation()}>
      <h2>{dName}</h2>
      <p class="muted small">
        Nu: <strong>{formatValue(dLive?.value, dMeta)}</strong>
        {#if dLive && dLive.quality !== 'good'}<span class="badge comm_error">{dLive.quality}</span>{/if}
      </p>
      {#if dialog.binding.anim === 'click:write' && dialog.step === 'input'}
        <label class="field">Ny værdi{dMeta?.unit ? ` (${dMeta.unit})` : ''}
          <!-- svelte-ignore a11y_autofocus -->
          <input bind:value={dialog.input} inputmode="decimal" autofocus />
        </label>
        <p class="muted small">Tilladt: {rangeText(dMeta)}</p>
      {:else if dialog.binding.anim === 'click:write'}
        <p>Sæt <strong>{dName}</strong> til <strong>{formatValue(dialog.value, dMeta)}</strong>?</p>
      {:else if dialog.binding.anim === 'click:toggle'}
        <p>{toggleQuestion(dialog.binding.tag, dLive, dMeta)}</p>
      {:else}
        <p>Send en puls på {dialog.binding.params.ms ?? 500} ms til <strong>{dName}</strong>?</p>
      {/if}
      {#if dialog.error}<div class="error">{dialog.error}</div>{/if}
      <div class="row">
        <button class="primary" onclick={submitDialog} disabled={dialog.busy}>
          {dialog.binding.anim === 'click:write' && dialog.step === 'input' ? 'OK' : 'Bekræft'}
        </button>
        {#if dialog.binding.anim === 'click:write' && dialog.step === 'confirm'}
          <button onclick={() => dialog && (dialog.step = 'input')} disabled={dialog.busy}>Tilbage</button>
        {/if}
        <button onclick={() => (dialog = null)} disabled={dialog.busy}>Annullér</button>
      </div>
    </div>
  </div>
{/if}

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
    width: 100%; /* overskrives af fit() med tegningens præcise størrelse */
    height: auto;
    margin: 0 auto;
  }
  .ok-toast { background: #e8f5e9; border-color: #a5d6a7; }
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, .35);
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding: 12vh 16px 0;
    z-index: 10;
  }
  .dialog { width: 100%; max-width: 380px; box-shadow: 0 8px 30px rgba(0, 0, 0, .25); }
  .field { display: flex; flex-direction: column; gap: .25rem; font-size: .9rem; color: var(--muted); }
  .field input { font-size: 1.3rem; }
</style>
