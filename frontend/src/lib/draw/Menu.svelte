<script lang="ts">
  // En lille rullemenu (knap + panel) til værktøjslinjen: lukker ved klik udenfor og Esc. Bruges i Tegn (v4.20.0).
  import type { Snippet } from 'svelte';

  let { label, title = '', badge = '', hot = false, wide = false, align = 'left', open = $bindable(false), onopen, children }: {
    label: string; title?: string;
    badge?: string | number;                 // et tal ved siden af navnet (fx antal nye meddelelser)
    hot?: boolean;                           // fremhæv knappen (fx ulæste meddelelser)
    wide?: boolean;                          // bredere panel
    align?: 'left' | 'right';
    open?: boolean;
    onopen?: () => void;                     // kaldes, når menuen åbnes
    children: Snippet;
  } = $props();
  let root: HTMLDivElement;
</script>

<svelte:window
  onmousedown={(e) => { if (open && root && !root.contains(e.target as Node)) open = false; }}
  onkeydown={(e) => { if (open && e.key === 'Escape') open = false; }} />

<div class="dd" bind:this={root}>
  <button class:hot onclick={() => { open = !open; if (open) onopen?.(); }} aria-expanded={open} aria-haspopup="true" {title}>{label}{#if badge !== '' && badge !== 0}<span class="badge">{badge}</span>{/if} ▾</button>
  {#if open}<div class="panel" class:wide class:right={align === 'right'} role="group" aria-label={label}>{@render children()}</div>{/if}
</div>

<style>
  .dd { position: relative; display: inline-block; }
  .panel {
    position: absolute; top: calc(100% + 4px); left: 0; z-index: 100; min-width: 16rem;
    background: var(--panel, #fff); border: 1px solid var(--line); border-radius: 6px;
    box-shadow: 0 6px 18px rgba(0, 0, 0, .18); padding: .5rem .65rem;
    display: flex; flex-direction: column; gap: .4rem; font-size: .88rem;
  }
  .panel.wide { min-width: 24rem; max-width: min(44rem, 90vw); }
  .panel.right { left: auto; right: 0; }
  button.hot { background: #fff4e0; border-color: #ff8f00; }
  .badge { margin-left: .35rem; background: #ff8f00; color: #fff; border-radius: 999px; padding: 0 .4rem; font-size: .72rem; font-weight: 600; }
  .panel :global(.mrow) { display: flex; align-items: center; flex-wrap: wrap; gap: .3rem .5rem; }
  .panel :global(.mhead) { font-size: .72rem; text-transform: uppercase; letter-spacing: .04em; color: var(--muted, #666); margin-top: .2rem; }
  .panel :global(.mrule) { border: 0; border-top: 1px solid var(--line); margin: .1rem 0; }
</style>
