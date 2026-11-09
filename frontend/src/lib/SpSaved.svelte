<script lang="ts">
  // Signalveje: listen over de gemte veje (Ret / Slet). Del af SignalPathGuide (v4.15.1).
  interface Row { id: number; name: string; ends?: string[]; elements: unknown[]; conditions: unknown[]; missing: string[] }
  let { paths, ready, busy, onedit, onremove }: {
    paths: Row[]; ready: boolean; busy: boolean; onedit: (p: Row) => void; onremove: (p: Row) => void;
  } = $props();
</script>

{#each paths as p (p.id)}
  <div class="item">
    <div class="grow">
      <strong>{p.name}</strong>
      <div class="small muted">{p.elements.length} dele · {(p.ends?.length ?? 1) > 1 ? `${p.ends!.length} grene · ` : ''}{p.conditions.length} betingelser</div>
      {#if p.missing.length}<div class="small warn">{p.missing.length} dele findes ikke længere — ret vejen</div>{/if}
    </div>
    <button class="small" onclick={() => onedit(p)} disabled={!ready || busy}>Ret</button>
    <button class="small" onclick={() => onremove(p)} disabled={busy} aria-label="Slet {p.name}">Slet</button>
  </div>
{/each}

<style>
  .item { display: flex; align-items: center; gap: .4rem; padding: .35rem 0; border-top: 1px solid var(--line); }
  .grow { flex: 1; min-width: 0; }
  .warn { color: var(--warn); }
</style>
