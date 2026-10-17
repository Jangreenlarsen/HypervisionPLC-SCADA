<script lang="ts">
  // "Anvend på flere …" fra symbolguiden (v0.59.0): kopiér symbolets gemte opsætning (tag + animationer) til andre symboler.
  // Serveren oversætter delene efter navn og validerer hver kopi som et almindeligt gem; hver kopi kan rettes enkeltvis bagefter.
  import { onMount } from 'svelte';
  import { get, post } from './api';
  import { candidates, pipes, rowLabel, sameType, summary, typeLabel, type CopyResponse, type SymbolRow } from './symbolCopy';

  let { drawingId, element, name, type, onclose }: {
    drawingId: string; element: string; name: string; type: string;
    onclose: () => void;
  } = $props();

  const enc = encodeURIComponent;
  let rows = $state<SymbolRow[]>([]);
  let loading = $state(true);
  let error = $state('');
  let query = $state('');
  let chosen = $state<Set<string>>(new Set());
  let overwrite = $state(false);
  let busy = $state(false);
  let result = $state<CopyResponse | null>(null);

  const shown = $derived(candidates(rows, element, query));
  const byId = $derived(new Map(rows.map((r) => [r.element, r])));
  const same = $derived(sameType(rows, element, type));
  const pipeIds = $derived(pipes(rows, element));
  const configuredChosen = $derived([...chosen].filter((id) => byId.get(id)?.configured).length);

  async function load(): Promise<void> {
    try {
      rows = await get<SymbolRow[]>(`/api/drawings/${enc(drawingId)}/symbols`);
    } catch (e) {
      error = (e as Error).message;
    } finally {
      loading = false;
    }
  }
  onMount(load);

  function toggle(id: string): void {
    const s = new Set(chosen);
    if (s.has(id)) s.delete(id); else s.add(id);
    chosen = s;
  }
  const add = (ids: string[]) => (chosen = new Set([...chosen, ...ids]));

  async function run(): Promise<void> {
    busy = true;
    error = '';
    try {
      result = await post<CopyResponse>(`/api/drawings/${enc(drawingId)}/symbols/${enc(element)}/copy`, { targets: [...chosen], overwrite });
      chosen = new Set();
      await load();   // opdatér "har opsætning"-mærkerne
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }
  const STATUS = { ok: '✓ Kopieret', skipped: '– Sprunget over', error: '✕ Fejl' } as const;
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={() => !busy && onclose()}>
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="panel dlg" role="dialog" aria-modal="true" aria-label="Anvend opsætningen på flere symboler" tabindex="-1" onclick={(e) => e.stopPropagation()}>
    <header class="row head">
      <h2>Anvend opsætningen på flere</h2>
      <span class="muted small">fra {name}</span>
      <button class="close" onclick={onclose} disabled={busy} aria-label="Luk">✕</button>
    </header>

    <div class="body">
      <p class="small muted">Hvert valgt symbol får sin <strong>egen kopi</strong> af opsætningen (tag og animationer), som du bagefter kan rette enkeltvis i guiden.
        Animationer på en bestemt del følger kun med, hvis symbolet har en del med samme navn. Nøglelåsen kopieres ikke.</p>

      {#if loading}
        <p class="muted">Henter symboler…</p>
      {:else}
        <div class="row wrap tools">
          <input bind:value={query} placeholder="Søg navn eller type" />
          {#if same.length}<button class="small" onclick={() => add(same)}>Alle af samme type ({typeLabel(type)}, {same.length})</button>{/if}
          {#if pipeIds.length}<button class="small" onclick={() => add(pipeIds)}>Alle rør og fittings ({pipeIds.length})</button>{/if}
          <button class="small" onclick={() => add(shown.map((r) => r.element))} disabled={!shown.length}>Vælg viste ({shown.length})</button>
          <button class="small" onclick={() => (chosen = new Set())} disabled={!chosen.size}>Ryd</button>
        </div>
        {#if shown.length}
          <ul class="list">
            {#each shown as r (r.element)}
              <li>
                <label class="opt">
                  <input type="checkbox" checked={chosen.has(r.element)} onchange={() => toggle(r.element)} />
                  <span class="nm">{rowLabel(r)}</span>
                  <span class="muted small">{typeLabel(r.type)}</span>
                  {#if r.configured}<span class="badge small">har opsætning</span>{/if}
                </label>
              </li>
            {/each}
          </ul>
        {:else}
          <p class="muted small">{rows.length > 1 ? `Ingen symboler matcher "${query}".` : 'Tegningen har ingen andre symboler (giv delene et navn eller indsæt symboler fra biblioteket).'}</p>
        {/if}
        {#if configuredChosen}
          <label class="opt warnbox small"><input type="checkbox" bind:checked={overwrite} />
            Overskriv den eksisterende opsætning på {configuredChosen} af de valgte (ellers springes de over)</label>
        {/if}
      {/if}

      {#if result}
        <h4>Resultat: {summary(result)}</h4>
        <table class="small">
          <tbody>
            {#each result.results as r (r.element)}
              <tr class={r.status}>
                <td>{STATUS[r.status]}</td>
                <td>{byId.get(r.element) ? rowLabel(byId.get(r.element)!) : r.element}</td>
                <td>{r.message}{#each r.notes as n}<div class="muted">{n}</div>{/each}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
      {#if error}<p class="error">{error}</p>{/if}
    </div>

    <footer class="row">
      <span class="small muted">{chosen.size} valgt</span>
      <span class="spacer"></span>
      <button onclick={onclose} disabled={busy}>{result ? 'Luk' : 'Annullér'}</button>
      <button class="primary" onclick={run} disabled={!chosen.size || busy}>{busy ? 'Kopierer…' : `Kopiér til ${chosen.size}`}</button>
    </footer>
  </div>
</div>

<style>
  .backdrop { position: fixed; inset: 0; background: rgba(0, 0, 0, .35); display: flex; align-items: flex-start; justify-content: center; padding: 6vh 16px 0; z-index: 30; }
  .dlg { width: 100%; max-width: 640px; max-height: 88vh; display: flex; flex-direction: column; box-shadow: 0 8px 30px rgba(0, 0, 0, .25); }
  .head { align-items: baseline; gap: .8rem; }
  .head h2 { margin: 0; }
  .close { margin-left: auto; }
  .body { overflow-y: auto; padding: .2rem 0 .4rem; }
  .tools { gap: .4rem; margin: .4rem 0; }
  .tools input { flex: 1; min-width: 12rem; }
  .list { list-style: none; margin: 0; padding: 0; border: 1px solid var(--line); border-radius: var(--radius); max-height: 40vh; overflow-y: auto; }
  .list li { padding: .1rem .5rem; border-bottom: 1px solid var(--line); }
  .list li:last-child { border-bottom: 0; }
  .opt { display: flex; gap: .5rem; align-items: baseline; margin: .2rem 0; }
  .nm { flex: 1; }
  .badge { background: var(--panel-2); border: 1px solid var(--line); border-radius: 999px; padding: 0 .45rem; }
  .warnbox { color: #8a4b00; background: #fff4e0; border: 1px solid #f0c27a; border-radius: var(--radius); padding: .35rem .6rem; margin-top: .5rem; }
  h4 { margin: .8rem 0 .3rem; }
  table { width: 100%; border-collapse: collapse; }
  td { padding: .2rem .4rem; border-bottom: 1px solid var(--line); vertical-align: top; }
  td:first-child { white-space: nowrap; }
  tr.ok td:first-child { color: #2e7d32; }
  tr.error td:first-child { color: #c62828; }
  footer { margin-top: .6rem; padding-top: .6rem; border-top: 1px solid var(--line); align-items: center; }
  .spacer { flex: 1; }
</style>
