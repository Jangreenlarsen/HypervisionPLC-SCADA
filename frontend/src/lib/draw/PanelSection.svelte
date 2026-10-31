<script lang="ts">
  // En foldbar sektion i Tegns højre panel (v3.5.0): overskrift med fold ud/ind og 📌 fastgør. Tilstanden ejes af Tegn
  // (panels.ts), så sektionerne kan folde hinanden sammen.
  import type { Snippet } from 'svelte';

  let { id, title, open, pinned, ontoggle, onpin, badge, children, grow = false }: {
    id: string;
    title: string;
    open: boolean;
    pinned: boolean;
    ontoggle: (id: string) => void;
    onpin: (id: string) => void;
    badge?: Snippet;
    children: Snippet;
    /** fylder den resterende højde (symbolbiblioteket) */
    grow?: boolean;
  } = $props();
</script>

<section class="panel psec" class:open class:grow aria-label={title}>
  <header>
    <button class="head" onclick={() => ontoggle(id)} aria-expanded={open}>
      <span class="chev" aria-hidden="true">{open ? '▾' : '▸'}</span>
      <span class="title">{title}</span>
      {#if badge}<span class="badge">{@render badge()}</span>{/if}
    </button>
    <button class="pin" class:on={pinned} onclick={() => onpin(id)} aria-pressed={pinned}
            title={pinned ? 'Fastgjort — står altid åben. Klik for at løsne' : 'Fastgør — sektionen bliver stående åben, når du åbner andre'}>📌</button>
  </header>
  {#if open}<div class="body">{@render children()}</div>{/if}
</section>

<style>
  .psec { padding: 0; display: flex; flex-direction: column; min-height: 0; }
  header { display: flex; align-items: center; gap: .25rem; padding: .35rem .5rem .35rem .2rem; flex: none; }
  .head { flex: 1; display: flex; align-items: center; gap: .4rem; border: 0; background: none; padding: .2rem .3rem; font: inherit; font-weight: 600; text-align: left; cursor: pointer; min-width: 0; }
  .chev { width: 1em; color: #666; }
  .title { white-space: nowrap; }
  .badge { font-weight: 400; color: #777; font-size: .8rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .pin { border: 1px solid transparent; background: none; padding: 1px 4px; border-radius: 4px; font-size: .8rem; opacity: .35; filter: grayscale(1); cursor: pointer; }
  .pin:hover { opacity: .8; }
  .pin.on { opacity: 1; filter: none; border-color: #c9d6ee; background: #eef3fb; }
  .body { padding: 0 .9rem .8rem; overflow-y: auto; min-height: 0; }
</style>
