<script lang="ts">
  // Et selvstændigt vindue over tegningen (v6.1.0): kan flyttes (træk i overskriften) og gøres større (hjørnet); placering og
  // størrelse huskes i browseren pr. `key`. Tegningen bagved kan stadig bruges (ingen mørk baggrund). Til editorerne i Tegn, så de
  // ikke skal ligge i sidemenuen.
  import type { Snippet } from 'svelte';

  let { key, title, onclose, children, width = 440, height = 560 }: {
    key: string; title: string; onclose: () => void; children: Snippet; width?: number; height?: number;
  } = $props();

  type Win = { x: number; y: number; w: number; h: number };
  function load(): Win {
    const def = { x: Math.max(80, (typeof window !== 'undefined' ? window.innerWidth : 1600) - 330 - width - 20), y: 120, w: width, h: height };
    try {
      const r = JSON.parse(localStorage.getItem(key) ?? '{}');
      const n = (v: unknown, d: number) => (typeof v === 'number' && Number.isFinite(v) ? v : d);
      return { x: n(r.x, def.x), y: n(r.y, def.y), w: n(r.w, def.w), h: n(r.h, def.h) };
    } catch {
      return def;
    }
  }
  let win = $state(load());
  function clamp(): void {
    const vw = window.innerWidth, vh = window.innerHeight;
    win.w = Math.min(Math.max(win.w, 300), vw - 20);
    win.h = Math.min(Math.max(win.h, 200), vh - 60);
    win.x = Math.min(Math.max(win.x, 0), vw - 120);
    win.y = Math.min(Math.max(win.y, 40), vh - 60);
  }
  $effect(() => {
    const w = $state.snapshot(win);
    try { localStorage.setItem(key, JSON.stringify(w)); } catch { /* blokeret localStorage: huskes bare ikke */ }
  });
  $effect(() => { clamp(); });
  function dragStart(e: PointerEvent): void {
    if ((e.target as HTMLElement).closest('button')) return;
    e.preventDefault();
    const sx = e.clientX - win.x, sy = e.clientY - win.y;
    const move = (ev: PointerEvent) => { win.x = ev.clientX - sx; win.y = ev.clientY - sy; clamp(); };
    const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  }
  let box = $state<HTMLDivElement | null>(null);
  $effect(() => {     // størrelsen, når brugeren trækker i hjørnet (CSS resize)
    const b = box;
    if (!b) return;
    const ro = new ResizeObserver(() => { win.w = Math.round(b.offsetWidth); win.h = Math.round(b.offsetHeight); });
    ro.observe(b);
    return () => ro.disconnect();
  });
  function onkey(e: KeyboardEvent): void {
    if (e.key === 'Escape' && box?.contains(document.activeElement)) onclose();
  }
</script>

<svelte:window onkeydown={onkey} />
<div class="fwin" bind:this={box} role="dialog" aria-label={title}
     style="left:{win.x}px; top:{win.y}px; width:{win.w}px; height:{win.h}px">
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="fhead" onpointerdown={dragStart} title="Træk for at flytte vinduet">
    <strong>{title}</strong><span class="grow"></span>
    <button class="small" onclick={onclose} aria-label="Luk {title}" title="Luk (Esc)">✕</button>
  </div>
  <div class="fbody">{@render children()}</div>
</div>

<style>
  .fwin {
    position: fixed; z-index: 36; display: flex; flex-direction: column; resize: both; overflow: hidden;
    min-width: 300px; min-height: 200px; background: var(--panel, #fff); border: 1px solid var(--line);
    border-radius: 8px; box-shadow: 0 10px 30px rgba(0, 0, 0, .25);
  }
  .fhead { display: flex; align-items: center; gap: .4rem; padding: .35rem .5rem .35rem .7rem; cursor: move; user-select: none;
    background: var(--panel-2, #f3f3f3); border-bottom: 1px solid var(--line); border-radius: 8px 8px 0 0; flex: none; touch-action: none; }
  .fhead .grow { flex: 1; }
  .fbody { flex: 1; overflow: auto; padding: .5rem .7rem .7rem; min-height: 0; }
</style>
