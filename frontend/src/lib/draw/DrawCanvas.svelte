<script lang="ts">
  // Den nye tegneflade (PLAN.md, trin 1): SVG-Edits motor direkte i siden, med vores egen værktøjsrail og statuslinje.
  // Giver Tegn-siden det samme API som den gamle iframe (onready), så resten af Tegn er uændret.
  import { onDestroy, onMount } from 'svelte';
  import { createEngine, type Engine } from './engine';

  let { onready, height = 600 }: { onready: (api: unknown) => void; height?: number } = $props();

  let workarea: HTMLDivElement;
  let textInput: HTMLInputElement;
  let engine: Engine | null = null;
  let mode = $state('select');
  let zoom = $state(1);
  let canUndo = $state(false);
  let canRedo = $state(false);

  // Venstre rail: få værktøjer, SCADA-orienteret. Rør, Symbol ▸ og Display/Omskifter kommer i trin 3–5.
  const TOOLS: { mode: string; label: string; key: string; icon: string }[] = [
    { mode: 'select', label: 'Vælg', key: 'V', icon: 'M5 3 L5 19 L9 15 L12 21 L14 20 L11 14 L17 14 Z' },
    { mode: 'line', label: 'Linje', key: 'L', icon: 'M4 20 L20 4' },
    { mode: 'rect', label: 'Rektangel', key: 'R', icon: 'M4 6 H20 V18 H4 Z' },
    { mode: 'ellipse', label: 'Ellipse', key: 'E', icon: 'M12 6 A8 6 0 1 0 12.01 6 Z' },
    { mode: 'path', label: 'Sti (klik punkter, dobbeltklik for at slutte)', key: 'P', icon: 'M4 18 L9 7 L15 15 L20 5' },
    { mode: 'fhpath', label: 'Frihånd', key: 'F', icon: 'M3 16 C7 4 10 22 14 10 S19 8 21 12' },
    { mode: 'text', label: 'Tekst', key: 'T', icon: 'M5 5 H19 M12 5 V20' },
  ];

  const sync = (): void => {
    if (!engine) return;
    canUndo = engine.canUndo();
    canRedo = engine.canRedo();
  };

  onMount(() => {
    engine = createEngine(workarea, textInput, {
      onMode: (m) => (mode = m),
      onZoom: (z) => (zoom = z),
      onHistory: sync,
    });
    void engine.api.ready.then(() => onready(engine!.api));
  });
  onDestroy(() => engine?.destroy());

  const tool = (m: string): void => engine?.setMode(m);
</script>

<div class="draw" style:height="{height}px">
  <nav class="rail" aria-label="Tegneværktøjer">
    {#each TOOLS as t}
      <button class:on={mode === t.mode} onclick={() => tool(t.mode)} title="{t.label} ({t.key})" aria-label={t.label} aria-pressed={mode === t.mode}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d={t.icon} /></svg>
      </button>
    {/each}
  </nav>
  <div class="main">
    <div class="workarea" bind:this={workarea}></div>
    <footer class="status">
      <button onclick={() => engine?.undo()} disabled={!canUndo} title="Fortryd (Ctrl+Z)">↶</button>
      <button onclick={() => engine?.redo()} disabled={!canRedo} title="Gentag (Ctrl+Y)">↷</button>
      <span class="sep"></span>
      <button onclick={() => engine?.zoomTo(zoom / 1.25)} title="Zoom ud (Ctrl+−)">−</button>
      <span class="zoom">{Math.round(zoom * 100)} %</span>
      <button onclick={() => engine?.zoomTo(zoom * 1.25)} title="Zoom ind (Ctrl++)">+</button>
      <button onclick={() => engine?.zoomFit()} title="Tilpas til vinduet (Ctrl+0)">Tilpas</button>
      <span class="hint">Ctrl + musehjul zoomer · mellemrum eller midterknap + træk flytter udsnittet</span>
    </footer>
  </div>
  <!-- lærredet skriver tekst gennem dette skjulte felt -->
  <input bind:this={textInput} class="text-input" aria-hidden="true" tabindex="-1" />
</div>

<style>
  .draw {
    display: flex;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: #fff;
    overflow: hidden;
    position: relative;
  }
  .rail {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 4px;
    border-right: 1px solid var(--line);
    background: #f4f4f4;
  }
  .rail button {
    width: 36px;
    height: 36px;
    padding: 6px;
    border: 1px solid transparent;
    border-radius: 6px;
    background: transparent;
  }
  .rail button:hover { background: #e6e6e6; }
  .rail button.on { background: #dbe8ff; border-color: #6c93d8; }
  .rail svg { width: 100%; height: 100%; fill: none; stroke: #222; stroke-width: 1.8; stroke-linejoin: round; stroke-linecap: round; }
  .main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  .workarea {
    flex: 1;
    min-height: 0;
    overflow: scroll;
    position: relative;
    background: #9a9a9a;
    scrollbar-color: #6b6b6b #d9d9d9;
  }
  .workarea :global(.svgcanvas) { position: relative; }
  /* Drejegrebets forbindelsesstreg tager ikke imod musen (BUGS.md v0.65.0) */
  .workarea :global(#selectorGrip_rotateconnector) { pointer-events: none; }
  .status {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 3px 6px;
    border-top: 1px solid var(--line);
    background: #f4f4f4;
    font-size: .85rem;
  }
  .status button { padding: 1px 8px; }
  .status .zoom { min-width: 4.5em; text-align: center; font-variant-numeric: tabular-nums; }
  .status .sep { width: 1px; height: 18px; background: var(--line); margin: 0 4px; }
  .status .hint { margin-left: auto; color: #666; }
  .text-input { position: absolute; width: 0; height: 0; opacity: 0; border: 0; padding: 0; left: 0; top: 0; }
</style>
