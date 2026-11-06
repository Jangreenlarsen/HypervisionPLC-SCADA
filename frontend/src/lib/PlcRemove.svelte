<script lang="ts">
  // Fjern en PLC (v3.34.0): oversigt over hvad der rammes, og valget mellem at flytte tagsene til en anden PLC eller at
  // fjerne alt (backup først, bekræft med PLC'ens nøgle). Selve arbejdet sker på serveren (services/plc_removal.py).
  import { onMount } from 'svelte';
  import { ApiError, get, post } from './api';

  let { plc, onclose, ondone }: {
    plc: { key: string; name: string };
    onclose: () => void;
    ondone: (msg: string) => void;
  } = $props();

  interface Usage {
    tags: number; tag_names: string[]; history: number; symbols: number; alarms: number;
    drawings: { id: string; name: string; bindings: number; symbols: number }[];
    schedules: string[]; trend_views: string[]; api_keys: string[];
    targets: { key: string; name: string; enabled: boolean; has_password: boolean }[];
  }
  let usage = $state<Usage | null>(null);
  let mode = $state<'move' | 'all'>('move');
  let target = $state('');
  let confirm = $state('');
  let busy = $state(false);
  let error = $state('');
  let problems = $state<string[]>([]);

  onMount(async () => {
    try {
      usage = await get<Usage>(`/api/plcs/${encodeURIComponent(plc.key)}/usage`);
      target = usage.targets[0]?.key ?? '';
      if (!usage.targets.length) mode = 'all';
    } catch (e) {
      error = (e as Error).message;
    }
  });

  const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

  async function run(): Promise<void> {
    busy = true;
    error = '';
    problems = [];
    try {
      // uden tags er der intet at bekræfte ud over selve knappen
      const body = !usage?.tags ? { mode: 'all', confirm: plc.key } : mode === 'move' ? { mode, target } : { mode, confirm: confirm.trim() };
      const r = await post<{ tags: number; backup?: string; history_backup?: string | null; history_failed?: number; warnings?: string[] }>(
        `/api/plcs/${encodeURIComponent(plc.key)}/remove`, body);
      const warn = [...(r.warnings ?? []), ...(r.history_failed ? [`historikken for ${r.history_failed} tag(s) kunne ikke slettes (se loggen)`] : [])];
      ondone((!usage?.tags
        ? `PLC'en ${plc.name} er fjernet.`
        : mode === 'move'
          ? `PLC'en ${plc.name} er fjernet — ${plural(r.tags, 'tag', 'tags')} er flyttet til ${target}.`
          : `PLC'en ${plc.name} er fjernet med ${plural(r.tags, 'tag', 'tags')} og alle henvisninger. Backup: ${r.backup}${r.history_backup ? ` og ${r.history_backup}` : ''} (System › Backup).`)
        + (warn.length ? ` ⚠ ${warn.join(' · ')}` : ''));
    } catch (e) {
      error = (e as Error).message;
      const body = e instanceof ApiError ? (e.body as { problems?: string[] } | undefined) : undefined;
      problems = Array.isArray(body?.problems) ? body.problems : [];
    } finally {
      busy = false;
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={() => !busy && onclose()}>
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="panel dlg" role="dialog" aria-modal="true" aria-label="Fjern PLC" tabindex="-1" onclick={(e) => e.stopPropagation()}>
    <header class="row head">
      <h2>Fjern PLC'en {plc.name}</h2>
      <button class="close" onclick={onclose} disabled={busy} aria-label="Luk">✕</button>
    </header>
    <div class="body">
      {#if !usage && !error}<p class="muted">Henter, hvad der bruger PLC'en …</p>{/if}
      {#if usage}
        {#if !usage.tags}
          <p>PLC'en har ingen tags. Den fjernes, og intet andet ændres.</p>
        {:else}
          <p><strong>{plural(usage.tags, 'tag', 'tags')}</strong> hører til PLC'en{usage.history ? ` (${usage.history} med historik)` : ''}. De bruges her:</p>
          <ul class="impact">
            {#each usage.drawings as d (d.id)}
              <li>Tegningen <strong>{d.name}</strong>: {plural(d.bindings, 'binding', 'bindinger')}, {plural(d.symbols, 'symbolopsætning', 'symbolopsætninger')}</li>
            {/each}
            {#if usage.schedules.length}<li>Ugeprogrammer: {usage.schedules.join(', ')}</li>{/if}
            {#if usage.trend_views.length}<li>Trendvisninger: {usage.trend_views.join(', ')}</li>{/if}
            {#if usage.api_keys.length}<li>API-nøgler (adgang til tagsene): {usage.api_keys.join(', ')}</li>{/if}
            {#if usage.alarms}<li>{plural(usage.alarms, 'aktiv alarm', 'aktive alarmer')}</li>{/if}
            {#if !usage.drawings.length && !usage.schedules.length && !usage.trend_views.length && !usage.api_keys.length}<li class="muted">Intet andet bruger tagsene.</li>{/if}
          </ul>
          <details><summary class="small">Vis tagsene</summary><p class="small muted">{usage.tag_names.join(', ')}{usage.tags > usage.tag_names.length ? ' …' : ''}</p></details>

          <fieldset>
            <label class="opt">
              <input type="radio" bind:group={mode} value="move" disabled={busy || !usage.targets.length} />
              <span><strong>Flyt tagsene til en anden PLC</strong> — fx når PLC'en er skiftet ud. Tagsene får samme adresse eller
                variabel på den nye PLC; navne, bindinger, symbolopsætninger, ugeprogrammer og historik bevares.
                {#if !usage.targets.length}<em class="muted"> (der er ingen anden PLC)</em>{/if}</span>
            </label>
            {#if mode === 'move' && usage.targets.length}
              {@const tg = usage.targets.find((t) => t.key === target)}
              <label class="sub">Flyt til
                <select bind:value={target} disabled={busy}>
                  {#each usage.targets as t (t.key)}<option value={t.key}>{t.name} ({t.key}){!t.enabled ? ' — slået fra' : !t.has_password ? ' — mangler adgangskode' : ''}</option>{/each}
                </select>
              </label>
              {#if tg && (!tg.enabled || !tg.has_password)}
                <p class="sub warn">⚠ {tg.name} {!tg.enabled ? 'er slået fra' : 'har ingen adgangskode'} — tagsene viser ingen værdier, før det er rettet.</p>
              {/if}
            {/if}
            <label class="opt">
              <input type="radio" bind:group={mode} value="all" disabled={busy} />
              <span><strong>Fjern alt</strong> — PLC'en, dens tags og alt, der bruger dem: bindinger, tagsene i symbolopsætningerne
                (symbolerne skal sættes op igen), ugeprogrammer, historik og tagsene i trendvisninger og API-nøgler.
                Alarmhændelserne bevares som historik. Der tages først en backup af opsætningen og af historikken
                (System › Backup).</span>
            </label>
            {#if mode === 'all'}
              <label class="sub"><span>Skriv PLC'ens nøgle <code>{plc.key}</code> for at bekræfte</span>
                <input bind:value={confirm} disabled={busy} autocomplete="off" />
              </label>
            {/if}
          </fieldset>
        {/if}
      {/if}
      {#if error}<p class="error" role="alert">{error}</p>{/if}
      {#if problems.length}
        <ul class="problems small">{#each problems as p (p)}<li>{p}</li>{/each}</ul>
      {/if}
    </div>
    <footer class="row">
      <span class="spacer"></span>
      <button onclick={onclose} disabled={busy}>Annullér</button>
      {#if usage}
        <button class="primary" class:alt={mode === 'all' && !!usage.tags} onclick={run}
                disabled={busy || (usage.tags > 0 && (mode === 'move' ? !target : confirm.trim() !== plc.key))}>
          {busy ? 'Arbejder …' : !usage.tags ? 'Fjern PLC' : mode === 'move' ? 'Flyt tags og fjern PLC' : 'Fjern alt'}
        </button>
      {/if}
    </footer>
  </div>
</div>

<style>
  .backdrop { position: fixed; inset: 0; background: rgba(0, 0, 0, .35); display: flex; align-items: flex-start; justify-content: center; padding: 6vh 16px 0; z-index: 20; }
  .dlg { width: 100%; max-width: 640px; max-height: 90vh; display: flex; flex-direction: column; box-shadow: 0 8px 30px rgba(0, 0, 0, .25); }
  .head { align-items: baseline; gap: .8rem; }
  .head h2 { margin: 0; font-size: 1.2rem; }
  .close { margin-left: auto; }
  .body { overflow-y: auto; padding: .2rem 0 .4rem; }
  .impact { margin: .3rem 0 .5rem; padding-left: 1.2rem; }
  fieldset { border: 1px solid var(--line); border-radius: var(--radius); padding: .5rem .7rem; margin: .6rem 0; }
  .opt { display: flex; gap: .5rem; align-items: flex-start; margin: .35rem 0; }
  .opt input[type='radio'] { margin-top: .3rem; width: 1rem; height: 1rem; flex: 0 0 1rem; appearance: auto; accent-color: #1f5fa8; }
  .primary.alt { background: #b3261e; border-color: #b3261e; color: #fff; }
  .sub { display: flex; flex-direction: column; gap: .2rem; margin: .2rem 0 .5rem 1.6rem; font-size: .9rem; }
  .problems { color: #b00020; max-height: 10rem; overflow-y: auto; }
  .warn { color: #8a5a00; margin-top: 0; }
  .spacer { flex: 1; }
</style>
