<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { api, get, post } from '../lib/api';
  import { RELATION_TEXT, canInstall, fmtSize, isFinished, progressText, resultOf, type Staged, type UpdateStatus } from '../lib/updateUi';

  let status = $state<UpdateStatus | null>(null);
  let error = $state('');
  let info = $state('');
  let uploading = $state(false);
  let reinstall = $state(false);
  let unreachable = $state(false);   // serveren genstarter (kald fejler) — det hører til forløbet
  let watching = $state(false);      // vi har selv startet en opdatering og følger den
  let startedAt = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let stopped = false;

  const fmtTs = (ts: number) => new Date(ts * 1000).toLocaleString('da-DK');

  async function refresh(): Promise<void> {
    try {
      status = await get<UpdateStatus>('/api/system/update');
      unreachable = false;
    } catch (e) {
      if (!watching) error = (e as Error).message;
      else unreachable = true;      // under en opdatering er et fejlet kald forventet (genstart)
    }
  }

  /** Følg opdateringen: hent status hvert 2. sekund til hjælperen melder færdig — også gennem serverens genstart. */
  async function follow(): Promise<void> {
    await refresh();
    if (stopped) return;
    if (watching && isFinished(status, startedAt)) {
      watching = false;
      const r = resultOf(status?.last ?? null);
      info = r?.kind === 'ok' ? 'Opdateringen er færdig. Genindlæs siden for at få den nye version.' : '';
      return;
    }
    timer = setTimeout(follow, 2000);
  }

  async function upload(file: File | undefined): Promise<void> {
    error = info = '';
    if (!file) return;
    uploading = true;
    try {
      await api('POST', '/api/system/update/upload', file);
      reinstall = false;
      await refresh();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      uploading = false;
    }
  }

  async function install(): Promise<void> {
    const s = status?.staged;
    if (!s) return;
    if (!confirm(`Installér ${s.version} build ${s.build} og genstart SCADA'en?\n\nDer tages en backup først. Svarer den nye version ikke, rulles der automatisk tilbage til ${status?.current.version}.\nOverview og live-data er væk et øjeblik under genstarten.`)) return;
    error = info = '';
    try {
      startedAt = Math.floor(Date.now() / 1000);
      watching = true;
      await post('/api/system/update/apply', { sha256: s.sha256, reinstall });
      timer = setTimeout(follow, 1500);
    } catch (e) {
      watching = false;
      error = (e as Error).message;
    }
  }

  async function discard(): Promise<void> {
    error = '';
    try {
      await api('DELETE', '/api/system/update/staged');
      await refresh();
    } catch (e) {
      error = (e as Error).message;
    }
  }

  onMount(async () => {
    await refresh();
    if (status?.busy) {          // siden blev åbnet midt i en opdatering
      watching = true;
      startedAt = Math.floor(Date.now() / 1000) - 3600;
      follow();
    }
  });
  onDestroy(() => {
    stopped = true;
    if (timer) clearTimeout(timer);
  });

  const result = $derived(resultOf(status?.last ?? null));
  const progress = $derived(watching ? progressText(status, unreachable) : '');
  const staged = $derived(status?.staged as Staged | null | undefined);
</script>

{#if error}<div class="error">{error}</div>{/if}

<section class="panel">
  <h2>Opdatering</h2>
  {#if status}
    <p>Installeret version: <strong>{status.current.version}</strong> build <strong>{status.current.build}</strong></p>
    {#if !status.enabled}
      <div class="notice">
        Opdatering fra web-siden er ikke aktiveret på denne server. Kør installationen én gang som root
        (<code>sh deploy/install.sh</code> fra en udpakket pakke) — herefter kan nye versioner uploades her.
      </div>
    {/if}
  {:else}
    <p class="muted">Henter …</p>
  {/if}
  {#if progress}<div class="notice" aria-live="polite"><strong>{progress}</strong></div>{/if}
  {#if info}<div class="notice ok-box">{info}</div>{/if}
  {#if result && !watching}
    <div class="notice {result.kind === 'ok' ? 'ok-box' : result.kind === 'warn' ? '' : 'error'}">
      {result.text}{#if status?.last} <span class="muted small">({fmtTs(status.last.ts)}, {status.last.by})</span>{/if}
    </div>
  {/if}
</section>

{#if status?.enabled}
  <section class="panel">
    <h2>Ny version</h2>
    <p class="muted small">
      Upload en opdateringspakke (<code>.tar</code>, <code>.tar.gz</code> eller <code>.tgz</code>), lavet med <code>sh deploy/make-package.sh</code>.
      Pakken kontrolleres først og installeres først, når du har bekræftet. Din opsætning (tags, tegninger, brugere) bevares.
    </p>
    <input type="file" accept=".tar,.gz,.tgz,application/x-tar,application/gzip" disabled={uploading || status.busy}
      onchange={(e) => upload((e.currentTarget as HTMLInputElement).files?.[0])} />
    {#if uploading}<p class="muted small">Uploader og kontrollerer …</p>{/if}

    {#if staged && !status.busy}   <!-- under en opdatering er pakken i brug: ingen knapper at trykke på -->
      <div class="notice">
        <strong>Version {staged.version} build {staged.build}</strong> — {RELATION_TEXT[staged.relation]}<br />
        <span class="small">{fmtSize(staged.size)} · {staged.files} filer · uploadet af {staged.uploaded_by} {fmtTs(staged.uploaded_at)}</span><br />
        <span class="small muted">Kontrolsum (SHA-256): <code>{staged.sha256}</code></span>
      </div>
      {#if staged.relation === 'older'}
        <div class="error">Pakken er ældre end den installerede version. Nedgradering understøttes ikke, fordi databasen kan være opgraderet.</div>
      {/if}
      {#if staged.relation === 'same'}
        <label class="row"><input type="checkbox" bind:checked={reinstall} /> Samme version — geninstallér alligevel</label>
      {/if}
      <div class="row" style="margin-top: .5rem">
        <button class="primary" onclick={install} disabled={!canInstall(status, reinstall)}>Installér og genstart</button>
        <button onclick={discard} disabled={status.busy}>Kassér pakken</button>
      </div>
    {/if}
  </section>

  {#if status.log.length}
    <section class="panel">
      <details>
        <summary><strong>Log fra seneste opdatering</strong></summary>
        <pre class="log">{status.log.join('\n')}</pre>
      </details>
    </section>
  {/if}
{/if}

<style>
  .ok-box { background: #e8f5e9; border-color: #a5d6a7; }
  .log { max-height: 20rem; overflow: auto; font-size: .78rem; background: var(--panel-2); padding: .5rem; border-radius: var(--radius); white-space: pre-wrap; }
  code { word-break: break-all; }
</style>
