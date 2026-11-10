<script lang="ts">
  // Signalveje, trin 4: hvilke animationer vejen lægger på hvilke slags elementer. Del af SignalPathGuide (v4.15.1).
  import type { NetRow } from './signalPath';
  import { GROUPS, GROUP_LABEL, TYPE_LABEL, WAYS_PART, WHOLE, anyChosen, groupOf, type Look, type LookGroup } from './pathLook';

  let { look = $bindable(), light = $bindable(), speed = $bindable(), present, rows, parts }: {
    look: Look; light: string; speed: number;
    present: Map<LookGroup, number>;                       // hvor mange elementer af hver slags der er på vejen
    rows: NetRow[];
    parts: (id: string) => { id: string; pid: string; text: string }[];   // et symbols navngivne dele
  } = $props();
</script>

<p class="small muted">Vælg, hvad vejen skal gøre ved hver slags element, når den er aktiv. Er den ikke aktiv, røres delen ikke.</p>
{#each GROUPS.filter((x) => present.has(x)) as g (g)}
  {@const first = rows.find((r) => groupOf(r.role) === g)}
  {@const list = parts(first?.id ?? '')}
  <fieldset class="look">
    <legend>{GROUP_LABEL[g]} <span class="small muted">({present.get(g)})</span></legend>
    {#if g !== 'pipe'}<p class="small muted names">{rows.filter((r) => groupOf(r.role) === g).map((r) => r.name || r.id).join(', ')}</p>{/if}
    {#each look[g] as a (a.type)}
      <div class="lrow">
        <label class="opt"><input type="checkbox" bind:checked={a.on} aria-label="{TYPE_LABEL[a.type]} på {GROUP_LABEL[g]}" /> {TYPE_LABEL[a.type]}</label>
        {#if a.on}
          {#if a.type === 'flow'}
            <input type="color" bind:value={light} aria-label="Lysfarve" title="Lysfarve" />
            <input class="num" type="number" min="5" max="500" bind:value={speed} aria-label="Fart" title="Fart" />
          {:else if a.type === 'fill' || a.type === 'stroke'}
            <input type="color" bind:value={a.color} aria-label="Farve for {TYPE_LABEL[a.type]}" title="Farve, når vejen er aktiv" />
          {:else if a.type === 'blink'}
            <select bind:value={a.speed} aria-label="Blinkhastighed"><option value="slow">langsomt</option><option value="normal">normalt</option><option value="fast">hurtigt</option></select>
          {/if}
          {#if g !== 'pipe' && a.type !== 'flow'}
            <select class="part" bind:value={a.part} aria-label="Del for {TYPE_LABEL[a.type]} på {GROUP_LABEL[g]}">
              {#if g === 'threeway'}<option value={WAYS_PART}>Portene i vejen</option>{/if}
              <option value={WHOLE}>Hele symbolet</option>
              {#each list as p (p.id)}<option value={p.id}>{p.text ? `${p.text} (${p.pid || p.id})` : (p.pid || p.id)}</option>{/each}
            </select>
          {/if}
        {/if}
      </div>
    {/each}
  </fieldset>
{/each}
{#if !anyChosen(look, new Set(present.keys()))}<p class="small warn">Vælg mindst én animation.</p>{/if}

<style>
  .warn { color: var(--warn); }
  .opt { display: flex; gap: .35rem; align-items: flex-start; font-size: .85rem; margin: .2rem 0; }
  .look { border: 1px solid var(--line); border-radius: var(--radius); margin: .3rem 0; padding: .2rem .5rem .4rem; }
  .look legend { font-size: .82rem; font-weight: 600; padding: 0 .3rem; }
  .names { margin: 0 0 .2rem; }
  .lrow { display: flex; align-items: center; flex-wrap: wrap; gap: .3rem .5rem; }
  .lrow .opt { margin: .1rem 0; min-width: 9rem; }
  .lrow input[type='color'] { width: 2rem; height: 1.5rem; padding: 0; }
  .lrow .num { width: 4rem; }
  .lrow .part { max-width: 100%; font-size: .8rem; }
</style>
