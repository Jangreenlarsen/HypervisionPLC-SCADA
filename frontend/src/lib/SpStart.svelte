<script lang="ts">
  // Signalveje, trin 1: start, slutpunkter og "gå via". Del af SignalPathGuide (v4.15.1). Al logik ligger i guiden; her er kun visningen.
  import { MAX_ENDS } from './signalPath';

  export type PickMode = 'start' | number | 'add' | 'via' | null;

  let { choices, start, endIds, picking, pickNote, busy, via, viaChoices, branchColor, label,
    onpick, onstoppick, onstart, onend, onremoveend, onaddend, onviapick, onviaselected, onremovevia, onswap, fromSelection }: {
    choices: { id: string; label: string }[];
    start: string;
    endIds: string[];
    picking: PickMode;
    pickNote: string;
    busy: boolean;
    via: { b: number; id: string; missing: boolean }[];                    // valgte via-punkter (og om der ikke er nogen vej gennem dem)
    viaChoices: { id: string; label: string }[];                           // symboler, der kan vælges som via
    branchColor: (b: number) => string;
    label: (id: string) => string;
    onpick: (what: PickMode) => void;                                      // begynd at vælge i tegningen
    onstoppick: () => void;
    onstart: (id: string) => void;
    onend: (i: number, id: string) => void;
    onremoveend: (i: number) => void;
    onaddend: (id: string) => void;
    onviapick: (id: string) => void;                                       // et via-punkt valgt i listen
    onviaselected: () => void;                                             // brug det, der er valgt i tegningen, som via
    onremovevia: (id: string) => void;
    onswap: () => void;
    fromSelection: () => string | null;                                    // symbolet, der er valgt i tegningen (eller null, og en fejl vises)
  } = $props();
</script>

<div class="row">
  {#if picking !== null}
    <button onclick={onstoppick}>Afbryd valg</button>
  {:else}
    <button class="primary" onclick={() => onpick('start')} disabled={busy} title="Klik på startsymbolet og derefter slutsymbolet i tegningen">Vælg på tegningen</button>
    {#if start && endIds.length}<button onclick={() => onpick('add')} disabled={busy || endIds.length >= MAX_ENDS} title="Vejen deler sig: tilføj endnu et slutpunkt">+ Slutpunkt</button>{/if}
  {/if}
</div>
{#if pickNote}<p class="small pick" role="status">{pickNote}</p>{/if}
<label class="field">Start
  <span class="row nowrap">
    <select value={start} onchange={(e) => onstart(e.currentTarget.value)}><option value="">— vælg —</option>{#each choices as e (e.id)}<option value={e.id}>{e.label}</option>{/each}</select>
    <button class="small" onclick={() => { const id = fromSelection(); if (id) onstart(id); }} title="Brug symbolet, der er valgt i tegningen">← valgt</button>
  </span>
</label>
{#each endIds as e, i (i)}
  <label class="field"><span><span class="dot" style="background:{branchColor(i)}"></span>{endIds.length > 1 ? `Slut ${i + 1}` : 'Slut'}</span>
    <span class="row nowrap">
      <select value={e} onchange={(ev) => onend(i, ev.currentTarget.value)}><option value="">— fjern —</option>{#each choices as c (c.id)}<option value={c.id}>{c.label}</option>{/each}</select>
      <button class="small" onclick={() => { const id = fromSelection(); if (id) onend(i, id); }} title="Brug symbolet, der er valgt i tegningen">← valgt</button>
      {#if endIds.length > 1}<button class="small" onclick={() => onremoveend(i)} aria-label="Fjern slutpunkt {i + 1}" title="Fjern slutpunktet">✕</button>{/if}
    </span>
  </label>
{/each}
{#if endIds.length && endIds.length < MAX_ENDS}
  <label class="field">Flere slutpunkter (vejen deler sig)
    <span class="row nowrap">
      <select value="" onchange={(e) => { onaddend(e.currentTarget.value); e.currentTarget.value = ''; }} aria-label="Tilføj slutpunkt">
        <option value="">+ tilføj et slutpunkt …</option>{#each choices.filter((c) => c.id !== start && !endIds.includes(c.id)) as c (c.id)}<option value={c.id}>{c.label}</option>{/each}
      </select>
      <button class="small" onclick={() => { const id = fromSelection(); if (id) onaddend(id); }} title="Tilføj symbolet, der er valgt i tegningen, som slutpunkt">← valgt</button>
    </span>
  </label>
{/if}
{#if !endIds.length && start}
  <label class="field">Slut
    <span class="row nowrap">
      <select value="" onchange={(e) => onaddend(e.currentTarget.value)} aria-label="Slut"><option value="">— vælg —</option>{#each choices.filter((c) => c.id !== start) as c (c.id)}<option value={c.id}>{c.label}</option>{/each}</select>
      <button class="small" onclick={() => { const id = fromSelection(); if (id) onaddend(id); }} title="Brug symbolet, der er valgt i tegningen">← valgt</button>
    </span>
  </label>
  {#if picking === null}<div class="row"><button onclick={() => onpick(0)} disabled={busy} title="Klik på slutsymbolet i tegningen">Vælg slut på tegningen</button></div>{/if}
{/if}
{#if start && endIds.length}
  <label class="field">Gå via (valgfrit) <span class="small muted">— rør eller symboler, vejen skal igennem</span>
    <span class="row nowrap">
      <select value="" onchange={(e) => { const id = e.currentTarget.value; e.currentTarget.value = ''; onviapick(id); }} aria-label="Gå via">
        <option value="">+ gå via …</option>{#each viaChoices as c (c.id)}<option value={c.id}>{c.label}</option>{/each}
      </select>
      <button class="small" onclick={onviaselected} title="Gå via det, der er valgt i tegningen">← valgt</button>
    </span>
  </label>
  {#if picking === null}<div class="row"><button class="small" onclick={() => onpick('via')} disabled={busy} title="Klik på et rør eller symbol i tegningen">Vælg via på tegningen</button></div>{/if}
  {#each via as v (v.id)}
    <div class="viarow small"><span class="dot" style="background:#6a1b9a"></span>Via {label(v.id)}{endIds.length > 1 ? ` (gren ${v.b + 1})` : ''}
      {#if v.missing}<span class="warn"> — ingen vej gennem det</span>{/if}
      <button class="small" onclick={() => onremovevia(v.id)} aria-label="Fjern via {label(v.id)}">✕</button></div>
  {/each}
{/if}
{#if start && endIds.length === 1}<div class="row"><button class="small" onclick={onswap} title="Byt start og slut (retningen følger i øvrigt pumpen)">⇄ Byt om</button></div>{/if}

<style>
  .pick { background: #fff4e0; border: 1px solid #ff8f00; border-radius: var(--radius); padding: .3rem .45rem; }
  .field { display: flex; flex-direction: column; gap: .15rem; font-size: .85rem; margin-bottom: .35rem; }
  .field select { min-width: 0; }
  .nowrap { flex-wrap: nowrap; gap: .3rem; display: flex; align-items: center; }
  .nowrap select { flex: 1; min-width: 0; }
  .warn { color: var(--warn); }
  .dot { display: inline-block; width: .7rem; height: .7rem; border-radius: 50%; margin-right: .3rem; vertical-align: middle; }
  .viarow { display: flex; align-items: center; gap: .3rem; margin: .15rem 0; }
</style>
