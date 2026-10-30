<script lang="ts">
  // Den nye tegneflade (PLAN.md): SVG-Edits motor direkte i siden med vores egen værktøjsrail (venstre), en svævende
  // linje til det markerede (justér, fordel, rækkefølge, gruppér), højreklikmenu og statuslinje (fortryd, zoom, tegnehjælp).
  // Giver Tegn-siden det samme API som den gamle iframe (onready), så resten af Tegn er uændret.
  import { onDestroy, onMount, type Snippet } from 'svelte';
  import { createEngine, type Engine } from './engine';

  let { onready, onupdate, height = 600, status, hint = '' }: {
    onready: (api: unknown) => void;
    /** markering/tegning kan være ændret — panelet til højre læser igen */
    onupdate?: () => void;
    height?: number;
    /** tegnehjælp (gitter, fang …) i statuslinjen — ejes af Tegn-siden */
    status?: Snippet;
    hint?: string;
  } = $props();

  let workarea: HTMLDivElement;
  let textInput: HTMLInputElement;
  let engine: Engine | null = null;
  let api: any = null; // eslint-disable-line @typescript-eslint/no-explicit-any
  let mode = $state('select');
  let zoom = $state(1);
  let canUndo = $state(false);
  let canRedo = $state(false);
  let count = $state(0);
  let isGroup = $state(false);   // ét element valgt, og det er en gruppe (kan opløses)
  let message = $state('');
  let menu = $state<{ x: number; y: number } | null>(null);

  // Venstre rail: få værktøjer, SCADA-orienteret. Symbol ▸ og Display/Omskifter kommer i de næste trin.
  const TOOLS: { mode: string; label: string; key: string; icon: string }[] = [
    { mode: 'select', label: 'Vælg og flyt', key: 'V', icon: 'M5 3 L5 19 L9 15 L12 21 L14 20 L11 14 L17 14 Z' },
    { mode: 'pipe', label: 'Rør — vandret/lodret, følger symbolerne', key: 'O', icon: 'M3 8 H14 V20 M3 4 H18 V20' },
    { mode: 'line', label: 'Linje', key: 'L', icon: 'M4 20 L20 4' },
    { mode: 'rect', label: 'Rektangel', key: 'R', icon: 'M4 6 H20 V18 H4 Z' },
    { mode: 'ellipse', label: 'Ellipse', key: 'E', icon: 'M12 6 A8 6 0 1 0 12.01 6 Z' },
    { mode: 'path', label: 'Sti — klik punkter, klik på startpunktet for at lukke', key: 'P', icon: 'M4 18 L9 7 L15 15 L20 5' },
    { mode: 'fhpath', label: 'Frihånd', key: 'F', icon: 'M3 16 C7 4 10 22 14 10 S19 8 21 12' },
    { mode: 'text', label: 'Tekst — klik og skriv', key: 'T', icon: 'M5 5 H19 M12 5 V20' },
  ];

  // Den svævende linje: ikoner som stier i et 24×24-felt
  const ALIGN: { t: string; label: string; icon: string }[] = [
    { t: 'l', label: 'Venstrestil', icon: 'M4 3 V21 M7 7 H18 M7 14 H13' },
    { t: 'c', label: 'Centrér vandret', icon: 'M12 3 V21 M6 7 H18 M9 14 H15' },
    { t: 'r', label: 'Højrestil', icon: 'M20 3 V21 M6 7 H17 M11 14 H17' },
    { t: 't', label: 'Justér top', icon: 'M3 4 H21 M7 7 V18 M14 7 V13' },
    { t: 'm', label: 'Centrér lodret', icon: 'M3 12 H21 M7 6 V18 M14 9 V15' },
    { t: 'b', label: 'Justér bund', icon: 'M3 20 H21 M7 6 V17 M14 11 V17' },
  ];

  const sync = (): void => {
    if (!engine) return;
    canUndo = engine.canUndo();
    canRedo = engine.canRedo();
    count = engine.selectionCount();
    isGroup = count === 1 && engine.canvas.getSelectedElements()[0]?.tagName === 'g';
    onupdate?.();
  };

  onMount(() => {
    engine = createEngine(workarea, textInput, {
      onMode: (m) => (mode = m),
      onZoom: (z) => { zoom = z; onupdate?.(); },
      onHistory: sync,
      onMessage: (t) => (message = t),
    });
    api = engine.api;
    void engine.api.ready.then(() => onready(engine!.api));
  });
  onDestroy(() => engine?.destroy());

  const tool = (m: string): void => engine?.setMode(m);
  function act(name: string): void {
    message = '';
    menu = null;
    engine?.perform(name);
  }
  function call(fn: () => unknown): void {
    message = '';
    menu = null;
    fn();
    sync();
  }

  function onContext(e: MouseEvent): void {
    e.preventDefault();
    // højreklik på et element, der ikke er valgt: lærredet har allerede valgt det ved museknappen
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    // menuen holdes inden for tegnefladen (tæt på kanten åbner den opad/til venstre)
    const MENU_W = 230, MENU_H = 360;
    const x = e.clientX - r.left, y = e.clientY - r.top;
    menu = { x: Math.max(0, x + MENU_W > r.width ? x - MENU_W : x), y: Math.max(0, y + MENU_H > r.height ? Math.max(0, r.height - MENU_H) : y) };
    sync();
  }
  const closeMenu = (): void => { menu = null; };
</script>

<svelte:window onkeydown={(e) => { if (e.key === 'Escape') closeMenu(); }} onblur={closeMenu} />

<div class="draw" style:height="{height}px">
  <nav class="rail" aria-label="Tegneværktøjer">
    <button onclick={() => act('undo')} disabled={!canUndo} title="Fortryd (Ctrl+Z)" aria-label="Fortryd">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6 L4 11 L9 16 M4 11 H14 A6 6 0 0 1 14 23" /></svg>
    </button>
    <button onclick={() => act('redo')} disabled={!canRedo} title="Gentag (Ctrl+Y)" aria-label="Gentag">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 6 L20 11 L15 16 M20 11 H10 A6 6 0 0 0 10 23" /></svg>
    </button>
    <span class="rsep"></span>
    {#each TOOLS as t}
      <button class:on={mode === t.mode} onclick={() => tool(t.mode)} title="{t.label} ({t.key})" aria-label={t.label} aria-pressed={mode === t.mode}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d={t.icon} /></svg>
      </button>
    {/each}
  </nav>
  <div class="main">
    <!-- svar på højreklik i tegnefladen; menuen styres også med tastaturet (Escape lukker) -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="stage" oncontextmenu={onContext} onmousedown={(e) => { if (menu && !(e.target as HTMLElement).closest('.cmenu')) closeMenu(); }}>
      <div class="workarea" bind:this={workarea}></div>

      {#if count > 0}
        <div class="selbar" role="toolbar" aria-label="Det markerede">
          {#each ALIGN as a}
            <button onclick={() => call(() => api?.align(a.t))} title="{a.label}{count === 1 ? ' (i forhold til tegningen)' : ''}" aria-label={a.label}>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d={a.icon} /></svg>
            </button>
          {/each}
          <span class="sep"></span>
          <button onclick={() => call(() => api?.distribute('x'))} disabled={count < 3} title="Fordel vandret (mindst 3)" aria-label="Fordel vandret">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 4 V20 M21 4 V20 M10 8 H14 V16 H10 Z" /></svg>
          </button>
          <button onclick={() => call(() => api?.distribute('y'))} disabled={count < 3} title="Fordel lodret (mindst 3)" aria-label="Fordel lodret">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 3 H20 M4 21 H20 M8 10 H16 V14 H8 Z" /></svg>
          </button>
          <span class="sep"></span>
          <button onclick={() => call(() => api?.order('top'))} title="Læg øverst" aria-label="Læg øverst">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 9 H20 V20 H8 Z M4 4 H16 V9" /><path class="fill" d="M8 9 H20 V20 H8 Z" /></svg>
          </button>
          <button onclick={() => call(() => api?.order('bottom'))} title="Læg nederst" aria-label="Læg nederst">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path class="fill" d="M4 4 H16 V15 H4 Z" /><path d="M8 9 H20 V20 H8 Z" /></svg>
          </button>
          <button onclick={() => call(() => api?.flip('h'))} title="Spejl vandret" aria-label="Spejl vandret">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 V21 M9 6 L3 18 H9 Z M15 6 L21 18 H15 Z" /></svg>
          </button>
          <button onclick={() => call(() => api?.flip('v'))} title="Spejl lodret" aria-label="Spejl lodret">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12 H21 M6 9 L18 3 V9 Z M6 15 L18 21 V15 Z" /></svg>
          </button>
          <span class="sep"></span>
          {#if count > 1}
            <button class="txt" onclick={() => act('group')} title="Gruppér (Ctrl+G)">Gruppér</button>
          {:else if isGroup}
            <button class="txt" onclick={() => act('ungroup')} title="Opløs gruppen (Ctrl+Shift+G)">Opløs</button>
          {/if}
          <button class="txt" onclick={() => act('duplicate')} title="Dupliker (Ctrl+D)">Dupliker</button>
          <button class="txt danger" onclick={() => act('delete')} title="Slet (Delete)">Slet</button>
        </div>
      {/if}

      {#if menu}
        <div class="cmenu" role="menu" style:left="{menu.x}px" style:top="{menu.y}px">
          <button role="menuitem" onclick={() => act('cut')} disabled={!count}>Klip <kbd>Ctrl+X</kbd></button>
          <button role="menuitem" onclick={() => act('copy')} disabled={!count}>Kopiér <kbd>Ctrl+C</kbd></button>
          <button role="menuitem" onclick={() => act('paste')}>Indsæt <kbd>Ctrl+V</kbd></button>
          <button role="menuitem" onclick={() => act('duplicate')} disabled={!count}>Dupliker <kbd>Ctrl+D</kbd></button>
          <hr />
          <button role="menuitem" onclick={() => act('group')} disabled={count < 2}>Gruppér <kbd>Ctrl+G</kbd></button>
          <button role="menuitem" onclick={() => act('ungroup')} disabled={!isGroup}>Opløs gruppe <kbd>Ctrl+Shift+G</kbd></button>
          <hr />
          <button role="menuitem" onclick={() => call(() => api?.order('top'))} disabled={!count}>Læg øverst</button>
          <button role="menuitem" onclick={() => call(() => api?.order('up'))} disabled={!count}>Ét lag op</button>
          <button role="menuitem" onclick={() => call(() => api?.order('down'))} disabled={!count}>Ét lag ned</button>
          <button role="menuitem" onclick={() => call(() => api?.order('bottom'))} disabled={!count}>Læg nederst</button>
          <hr />
          <button role="menuitem" class="danger" onclick={() => act('delete')} disabled={!count}>Slet <kbd>Delete</kbd></button>
        </div>
      {/if}
      {#if message}<div class="msg" role="alert">{message} <button class="small" onclick={() => (message = '')} aria-label="Luk">✕</button></div>{/if}
    </div>
    <footer class="status">
      <button onclick={() => act('zoomOut')} title="Zoom ud (Ctrl+−)" aria-label="Zoom ud">−</button>
      <span class="zoom">{Math.round(zoom * 100)} %</span>
      <button onclick={() => act('zoomIn')} title="Zoom ind (Ctrl++)" aria-label="Zoom ind">+</button>
      <button onclick={() => act('zoomFit')} title="Tilpas til vinduet (Ctrl+0)">Tilpas</button>
      {#if status}<span class="sep"></span>{@render status()}{/if}
    </footer>
    {#if hint}<div class="hint small" aria-live="polite">{hint}</div>{/if}
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
  .rail button:disabled { opacity: .35; }
  .rsep { height: 1px; background: var(--line); margin: 3px 2px; }
  svg { width: 100%; height: 100%; fill: none; stroke: #222; stroke-width: 1.8; stroke-linejoin: round; stroke-linecap: round; }
  svg .fill { fill: #9db8e8; }
  .main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  .stage { flex: 1; min-height: 0; position: relative; display: flex; }
  .workarea {
    flex: 1;
    min-width: 0;
    overflow: scroll;
    position: relative;
    background: #9a9a9a;
    scrollbar-color: #6b6b6b #d9d9d9;
  }
  .workarea :global(.svgcanvas) { position: relative; }
  /* Drejegrebets forbindelsesstreg tager ikke imod musen (BUGS.md v0.65.0) */
  .workarea :global(#selectorGrip_rotateconnector) { pointer-events: none; }

  .selbar {
    position: absolute;
    top: 8px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 2px;
    padding: 3px 5px;
    background: #fff;
    border: 1px solid var(--line);
    border-radius: 8px;
    box-shadow: 0 2px 8px rgb(0 0 0 / .18);
    z-index: 60;
    white-space: nowrap;
  }
  .selbar button { width: 30px; height: 30px; padding: 4px; border: 1px solid transparent; border-radius: 5px; background: transparent; }
  .selbar button.txt { width: auto; padding: 2px 8px; font-size: .85rem; }
  .selbar button:hover:not(:disabled) { background: #e9eef7; }
  .selbar button:disabled { opacity: .35; }
  .selbar .danger { color: #b3261e; }
  .sep { width: 1px; height: 20px; background: var(--line); margin: 0 4px; flex: none; }

  .cmenu {
    position: absolute;
    z-index: 70;
    display: flex;
    flex-direction: column;
    min-width: 13rem;
    padding: 4px 0;
    background: #fff;
    border: 1px solid var(--line);
    border-radius: 6px;
    box-shadow: 0 4px 14px rgb(0 0 0 / .22);
  }
  .cmenu button {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    padding: 4px 12px;
    border: 0;
    border-radius: 0;
    background: transparent;
    text-align: left;
    font-size: .9rem;
  }
  .cmenu button:hover:not(:disabled) { background: #e9eef7; }
  .cmenu button:disabled { color: #aaa; }
  .cmenu .danger { color: #b3261e; }
  .cmenu kbd { font-size: .75rem; color: #777; background: none; border: 0; }
  .cmenu hr { margin: 3px 0; border: 0; border-top: 1px solid var(--line); }
  .msg {
    position: absolute;
    bottom: 10px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 60;
    padding: 5px 10px;
    background: #fff4e5;
    border: 1px solid #e0b062;
    border-radius: 6px;
    font-size: .9rem;
  }

  .status {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 4px 6px;
    padding: 3px 6px;
    border-top: 1px solid var(--line);
    background: #f4f4f4;
    font-size: .85rem;
  }
  .status button { padding: 1px 8px; }
  .status .zoom { min-width: 4.5em; text-align: center; font-variant-numeric: tabular-nums; }
  .hint { padding: 2px 8px 4px; background: #f4f4f4; color: #555; border-top: 1px solid #e4e4e4; }
  .text-input { position: absolute; width: 0; height: 0; opacity: 0; border: 0; padding: 0; left: 0; top: 0; }
</style>
