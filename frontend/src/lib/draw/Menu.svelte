<script lang="ts">
  // En lille rullemenu (knap + panel) til værktøjslinjen: lukker ved klik udenfor og Esc. Bruges i Tegn (v4.20.0).
  import type { Snippet } from 'svelte';

  let { label, title = '', children }: { label: string; title?: string; children: Snippet } = $props();
  let open = $state(false);
  let root: HTMLDivElement;
</script>

<svelte:window
  onmousedown={(e) => { if (open && root && !root.contains(e.target as Node)) open = false; }}
  onkeydown={(e) => { if (open && e.key === 'Escape') open = false; }} />

<div class="dd" bind:this={root}>
  <button onclick={() => (open = !open)} aria-expanded={open} aria-haspopup="true" {title}>{label} ▾</button>
  {#if open}<div class="panel" role="group" aria-label={label}>{@render children()}</div>{/if}
</div>

<style>
  .dd { position: relative; display: inline-block; }
  .panel {
    position: absolute; top: calc(100% + 4px); left: 0; z-index: 100; min-width: 16rem;
    background: var(--panel, #fff); border: 1px solid var(--line); border-radius: 6px;
    box-shadow: 0 6px 18px rgba(0, 0, 0, .18); padding: .5rem .65rem;
    display: flex; flex-direction: column; gap: .4rem; font-size: .88rem;
  }
  .panel :global(.mrow) { display: flex; align-items: center; flex-wrap: wrap; gap: .3rem .5rem; }
  .panel :global(.mhead) { font-size: .72rem; text-transform: uppercase; letter-spacing: .04em; color: var(--muted, #666); margin-top: .2rem; }
  .panel :global(.mrule) { border: 0; border-top: 1px solid var(--line); margin: .1rem 0; }
</style>
