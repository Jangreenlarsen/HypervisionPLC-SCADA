<script lang="ts">
  // Signalveje: listen over de gemte veje (Ret / Slet). Del af SignalPathGuide (v4.15.1).
  interface Row { id: number; name: string; ends?: string[]; elements: unknown[]; missing: string[]; symbol?: string; configured?: boolean }
  let { paths, ready, busy, onedit, onremove, onsymbol }: {
    paths: Row[]; ready: boolean; busy: boolean; onedit: (p: Row) => void; onremove: (p: Row) => void;
    /** Vejen som symbol: åbn symbol-guiden (6 trin) — tilbagemelding (trin 2), kontaktflade (trin 3) og animationer (trin 4) */
    onsymbol?: (p: Row) => void;
  } = $props();
</script>

{#each paths as p (p.id)}
  <div class="item">
    <div class="grow">
      <strong>{p.name}</strong>
      <div class="small muted">{p.elements.length} dele{(p.ends?.length ?? 1) > 1 ? ` · ${p.ends!.length} grene` : ''}</div>
      {#if p.missing.length}<div class="small warn">{p.missing.length} dele findes ikke længere — ret vejen</div>{/if}
    </div>
    <div class="btns">
      {#if onsymbol && p.symbol}
        <button class="small" onclick={() => onsymbol(p)} disabled={!ready || busy}
          title="Sæt vejen op som et symbol (6 trin): tilbagemelding fra et PLC-tag eller et andet symbols position, kontaktflade og animationer">
          Ret som symbol{p.configured ? ' ✓' : ''}</button>
      {/if}
      <button class="small" onclick={() => onedit(p)} disabled={!ready || busy}>Ret</button>
      <button class="small" onclick={() => onremove(p)} disabled={busy} aria-label="Slet {p.name}">Slet</button>
    </div>
  </div>
{/each}

<style>
  .item { display: flex; flex-direction: column; gap: .3rem; padding: .4rem 0; border-top: 1px solid var(--line); }
  .grow { min-width: 0; overflow-wrap: anywhere; }
  .btns { display: flex; flex-wrap: wrap; gap: .3rem; }
  .warn { color: var(--warn); }
</style>
