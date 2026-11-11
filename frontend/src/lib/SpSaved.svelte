<script lang="ts">
  // Signalveje: listen over de gemte veje (Ret / Slet). Del af SignalPathGuide (v4.15.1).
  interface Row { id: number; name: string; ends?: string[]; elements: unknown[]; conditions: unknown[]; missing: string[]; symbol?: string; configured?: boolean }
  let { paths, ready, busy, onedit, onremove, onsymbol }: {
    paths: Row[]; ready: boolean; busy: boolean; onedit: (p: Row) => void; onremove: (p: Row) => void;
    /** Vejen som symbol (v5.4.0): åbn symbol-guiden (6 trin) for vejens egne animationer, logik og signaler */
    onsymbol?: (p: Row) => void;
  } = $props();
</script>

{#each paths as p (p.id)}
  <div class="item">
    <div class="grow">
      <strong>{p.name}</strong>
      <div class="small muted">{p.elements.length} dele · {(p.ends?.length ?? 1) > 1 ? `${p.ends!.length} grene · ` : ''}{p.conditions.length} betingelser</div>
      {#if p.missing.length}<div class="small warn">{p.missing.length} dele findes ikke længere — ret vejen</div>{/if}
    </div>
    <div class="btns">
      {#if onsymbol && p.symbol}
        <button class="small" onclick={() => onsymbol(p)} disabled={!ready || busy}
          title="Åbn vejen som symbol: tilføj egne animationer, logik og signaler på vejens elementer — de overskrives aldrig, når vejen gemmes igen">
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
