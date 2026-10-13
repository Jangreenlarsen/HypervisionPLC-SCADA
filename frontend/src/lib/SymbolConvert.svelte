<script lang="ts">
  // Symbolstandard fase 8: "Konvertér alle" — tør-kørsel med rapport, derefter konvertering af de symboler der kan.
  // Den gamle model fjernes ikke her (kræver godkendelse); hvert symbol kan fortrydes med "Fjern konfiguration" i guiden.
  import { post } from './api';

  interface Row { drawing: string; element: string; name: string | null; type: string; status: Status; reasons: string[]; notes: string[] }
  type Status = 'ready' | 'converted' | 'manual' | 'configured' | 'none';
  interface Result { apply: boolean; counts: Record<Status, number>; symbols: Row[] }

  let { names = {} }: { names?: Record<string, string> } = $props();

  const TXT: Record<Status, string> = {
    ready: 'Kan konverteres', converted: 'Konverteret', manual: 'Kræver manuel handling', configured: 'Allerede sat op', none: 'Ingen bindinger',
  };
  let result = $state<Result | null>(null);
  let busy = $state(false);
  let error = $state('');
  let showAll = $state(false);
  const shown = $derived((result?.symbols ?? []).filter((r) => showAll || r.status === 'ready' || r.status === 'manual' || r.status === 'converted'));

  async function run(apply: boolean): Promise<void> {
    if (apply && !confirm(`Konvertér ${result?.counts.ready ?? 0} symboler til symbolstandarden? Deres gamle bindinger bruges derefter ikke (kan fortrydes pr. symbol i guiden).`)) return;
    busy = true;
    error = '';
    try {
      result = await post<Result>('/api/drawings/convert-symbols', { apply });
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }
</script>

<section class="panel">
  <h2>Symbolstandard: konvertér alle</h2>
  <p class="small muted">
    Finder bibliotekssymboler med bindinger fra før symbolstandarden og laver en opsætning til hver, som guiden under Bindinger
    ville foreslå. <strong>Tør-kørslen gemmer intet</strong> — den viser hvad der vil ske. Bagefter kan de symboler der kan
    konverteres, konverteres i ét hug; resten skal sættes op i guiden.
  </p>
  <div class="row">
    <button onclick={() => run(false)} disabled={busy}>{busy && !result ? 'Kører…' : 'Tør-kørsel'}</button>
    {#if result && !result.apply && result.counts.ready > 0}
      <button class="primary" onclick={() => run(true)} disabled={busy}>Konvertér {result.counts.ready} symboler</button>
    {/if}
  </div>
  {#if error}<p class="error">{error}</p>{/if}
  {#if result}
    <p class="small">
      {result.apply ? 'Resultat:' : 'Tør-kørsel:'}
      {#each Object.entries(TXT) as [k, t]}{#if result.counts[k as Status]}<span class="chip {k}">{t}: {result.counts[k as Status]}</span>{/if}{/each}
      <label class="opt"><input type="checkbox" bind:checked={showAll} /> Vis også allerede sat op / uden bindinger</label>
    </p>
    {#if shown.length}
      <table class="grid">
        <thead><tr><th>Tegning</th><th>Symbol</th><th>Status</th><th>Bemærkninger</th></tr></thead>
        <tbody>
          {#each shown as r}
            <tr>
              <td>{names[r.drawing] ?? r.drawing}</td>
              <td><a href={`#editor/${encodeURIComponent(r.drawing)}/${encodeURIComponent(r.element)}`}>{r.name || r.element}</a>
                <span class="muted small">{r.type}</span></td>
              <td><span class="chip {r.status}">{TXT[r.status]}</span></td>
              <td class="small">{[...r.reasons, ...r.notes.filter((n) => !r.reasons.includes(n))].join(' · ')}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {:else}
      <p class="small muted">Ingen symboler at konvertere.</p>
    {/if}
  {/if}
</section>

<style>
  .grid { border-collapse: collapse; width: 100%; margin-top: .4rem; }
  .grid th, .grid td { border: 1px solid var(--line); padding: .25rem .4rem; text-align: left; vertical-align: top; }
  .chip { display: inline-block; padding: 0 .45rem; border-radius: 9px; font-size: .8rem; margin-right: .35rem; background: var(--panel-2); border: 1px solid var(--line); }
  .chip.ready, .chip.converted { background: #e8f5e9; border-color: #a5d6a7; }
  .chip.manual { background: #fff3e0; border-color: #ffcc80; }
  .opt { display: inline-flex; align-items: center; gap: .3rem; margin-left: .6rem; }
  .error { color: var(--alarm); }
</style>
