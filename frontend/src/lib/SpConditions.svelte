<script module lang="ts">
  import type { Answer } from './signalPath';
  export type QAnswer = Answer & { key: string; branches: number[] };
  export interface AiState { text: string; thinking: boolean; start: number; secs: number; note: string; set: Set<string>; unfilled: string[] }
</script>

<script lang="ts">
  // Signalveje, trin 3: hvornår går der flow — en betingelse pr. ventil/pumpe/kontakt, og "Forklar med egne ord". Del af SignalPathGuide (v4.15.1).
  import { assist } from './assistStore.svelte';
  import { QUESTION, type NetRow, type Question, type TagInfo } from './signalPath';
  import { parseWay, wayLabel } from './symbolFlow';

  let { answers = $bindable(), ai = $bindable(), focusId = $bindable(), questions, askedOnce, rows, tagsOf, allTags, branchCount, branchColor, busy, onsuggest, onstop }: {
    answers: QAnswer[]; ai: AiState; focusId: string;
    questions: Question[]; askedOnce: Question[];
    rows: NetRow[];
    tagsOf: (id: string) => TagInfo[];                     // symbolets egne tags
    allTags: TagInfo[];
    branchCount: number;
    branchColor: (b: number) => string;
    busy: boolean;
    onsuggest: () => void;
    onstop: () => void;
  } = $props();

  const rowOf = (id: string) => rows.find((r) => r.id === id);
  const tagOf = (n: string) => allTags.find((t) => t.name === n);
</script>

{#if !questions.length}<p class="small muted">Ingen ventiler eller pumper på vejen — løbelyset kører altid.</p>{/if}
{#if askedOnce.length && assist.available && assist.canAsk}
  <div class="explain">
    <label class="field">Forklar med egne ord <span class="small muted">(hjælperen udfylder forslag)</span>
      <textarea bind:value={ai.text} rows="2" maxlength="400" disabled={ai.thinking}
                placeholder="fx når pumpe 5 kører og MVS1 står over 50 %"></textarea>
    </label>
    <div class="row">
      {#if ai.thinking}
        <button onclick={onstop}>Stop</button>
        <span class="small muted">{ai.note} {ai.secs} s</span>
      {:else}
        <button onclick={onsuggest} disabled={!ai.text.trim() || busy}>Udfyld med hjælperen</button>
        {#if ai.note}<span class="small muted">{ai.note}</span>{:else}<span class="small muted">tager typisk 1–3 min</span>{/if}
      {/if}
    </div>
    {#if ai.unfilled.length && !ai.thinking}
      <p class="small warn">Ikke udfyldt af hjælperen: {ai.unfilled.map((id) => rowOf(id)?.name || id).join(', ')} — vælg selv.</p>
    {/if}
  </div>
{/if}
{#each answers as a (a.key)}
  {@const r = rowOf(a.element)}
  {@const q = questions.find((x) => x.key === a.key)}
  {@const own = tagsOf(a.element)}
  {@const t = tagOf(a.src)}
  <div class="q" onmouseenter={() => (focusId = a.element)} onmouseleave={() => (focusId = '')} role="group" aria-label="Betingelse for {r?.name || a.element}">
    <div><strong>{r?.name || a.element}</strong>
      {#if q?.way}<span class="chip">{wayLabel(parseWay(q.way)!)}</span>{/if}
      {#each a.branches as b (b)}{#if branchCount > 1}<span class="dot" style="background:{branchColor(b)}" title="Gren {b + 1}"></span>{/if}{/each}
      <span class="small muted">{q ? (q.way ? `Hvornår leder ventilen ${wayLabel(parseWay(q.way)!)}?` : QUESTION[q.role]) : ''}</span>
      {#if ai.set.has(a.element)}<span class="ai" title="Udfyldt af hjælperen — tjek det">forslag</span>{/if}</div>
    <select bind:value={a.src} aria-label="Tag for {r?.name || a.element}">
      <option value="">— ingen betingelse (altid) —</option>
      {#if own.length}<optgroup label="Symbolets egne tags">{#each own as o (o.name)}<option value={o.name}>{o.name}</option>{/each}</optgroup>{/if}
      <optgroup label="Alle tags">{#each allTags as o (o.name)}<option value={o.name}>{o.name}{o.unit ? ` [${o.unit}]` : ''}</option>{/each}</optgroup>
    </select>
    {#if t?.is_bool}
      <select bind:value={a.on} aria-label="Tilstand"><option value={true}>når tagget er til</option><option value={false}>når tagget er fra</option></select>
    {:else if t}
      <span class="row nowrap">
        <select bind:value={a.cmp} aria-label="Sammenligning"><option value="">—</option><option value="ge">≥</option><option value="le">≤</option><option value="eq">=</option></select>
        <input type="number" step="any" bind:value={a.value} aria-label="Grænseværdi" />
        <span class="small muted">{t.unit}</span>
      </span>
    {/if}
  </div>
{/each}
{#if questions.length}<p class="small muted">{branchCount > 1 ? 'Inden for en gren skal alle betingelser være opfyldt (OG); et fælles stykke lyser, når mindst én gren er aktiv.' : 'Alle betingelser skal være opfyldt (OG).'}</p>{/if}

<style>
  .warn { color: var(--warn); }
  .field { display: flex; flex-direction: column; gap: .15rem; font-size: .85rem; margin-bottom: .35rem; }
  .nowrap { flex-wrap: nowrap; gap: .3rem; display: flex; align-items: center; }
  .nowrap select { flex: 1; min-width: 0; }
  .q { display: flex; flex-direction: column; gap: .25rem; padding: .35rem 0; border-bottom: 1px dashed var(--line); }
  .q input[type='number'] { width: 6rem; }
  .explain { background: #fff; border: 1px solid var(--line); border-radius: var(--radius); padding: .4rem; margin-bottom: .4rem; }
  .explain textarea { width: 100%; box-sizing: border-box; resize: vertical; font: inherit; }
  .ai { font-size: .7rem; background: var(--accent); color: #fff; border-radius: 3px; padding: 0 .3rem; margin-left: .3rem; }
  .dot { display: inline-block; width: .7rem; height: .7rem; border-radius: 50%; margin-right: .3rem; vertical-align: middle; }
  .chip { font-size: .72rem; background: #eceff1; border: 1px solid var(--line); border-radius: 999px; padding: 0 .4rem; margin: 0 .2rem; }
</style>
