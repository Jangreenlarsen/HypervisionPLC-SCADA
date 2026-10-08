<script lang="ts">
  import { onMount } from 'svelte';
  import { get, post } from '../lib/api';

  interface ServerFile { name: string; size: number; created: number; kind: string }
  interface Summary { created: string; created_by: string; app_version: string; plcs: number; tags: number; drawings: number; versions: number; bindings: number }
  interface Result { plcs: number; tags: number; drawings: number; versions: number; bindings: number; missing_passwords: string[]; pre_restore_backup: string }

  let files = $state<ServerFile[]>([]);
  let error = $state('');
  let pending = $state<{ data: unknown; summary: Summary; filename: string } | null>(null);
  let confirmed = $state(false);
  let busy = $state(false);
  let result = $state<Result | null>(null);

  async function refresh(): Promise<void> {
    try {
      files = await get<ServerFile[]>('/api/backup/files');
    } catch (e) {
      error = (e as Error).message;
    }
  }

  /** Læs filen og vis hvad den indeholder, før noget sendes til serveren. */
  async function choose(file: File | undefined): Promise<void> {
    error = '';
    result = null;
    pending = null;
    confirmed = false;
    if (!file) return;
    if (file.size > 64 * 1024 * 1024) {
      error = `Filen er for stor (${Math.round(file.size / 1024 / 1024)} MB) — max 64 MB`;
      return;
    }
    let data: any;
    try {
      data = JSON.parse(await file.text());
    } catch {
      error = 'Filen er ikke gyldig JSON';
      return;
    }
    if (data?.format !== 'hypervisionplc-scada-backup') {
      error = 'Filen er ikke en HypervisionPLC SCADA-backup';
      return;
    }
    const len = (x: unknown) => (Array.isArray(x) ? x.length : 0);
    pending = {
      data,
      filename: file.name,
      summary: {
        created: data.created ?? '?', created_by: data.created_by ?? '?', app_version: data.app_version ?? '?',
        plcs: len(data.plcs), tags: len(data.tags), drawings: len(data.drawings),
        versions: (data.drawings ?? []).reduce((n: number, d: any) => n + len(d.versions), 0),
        bindings: len(data.bindings),
      },
    };
  }

  async function restore(): Promise<void> {
    if (!pending) return;
    busy = true;
    error = '';
    try {
      result = await post<Result>('/api/backup/restore', pending.data);
      pending = null;
      await refresh();
    } catch (e) {
      error = (e as Error).message; // serverens liste over valideringsfejl vises som den er
    } finally {
      busy = false;
    }
  }

  const fmtDate = (ts: number) => new Date(ts * 1000).toLocaleString('da-DK');
  const fmtIso = (iso: string) => (Number.isNaN(Date.parse(iso)) ? iso : new Date(iso).toLocaleString('da-DK'));

  onMount(refresh);
</script>

{#if error}<div class="error">{error}</div>{/if}

<section class="panel">
  <h2>Tag backup</h2>
  <p class="muted small">
    Backuppen indeholder PLC-forbindelser, tags, alle tegninger (med alle versioner) og bindinger.
    Den indeholder <strong>ikke</strong> PLC-adgangskoder eller brugere.
  </p>
  <a class="btn" href="/api/backup" download>Hent backup</a>
</section>

<section class="panel">
  <h2>Gendan backup</h2>
  <p class="muted small">
    Gendannelse <strong>erstatter</strong> alle nuværende PLC-forbindelser, tags, tegninger og bindinger.
    Brugere bevares. Der gemmes automatisk en backup af den nuværende tilstand først.
  </p>
  <input type="file" accept=".json,application/json" onchange={(e) => choose((e.currentTarget as HTMLInputElement).files?.[0])} />

  {#if pending}
    <div class="notice">
      <strong>{pending.filename}</strong><br />
      Lavet {fmtIso(pending.summary.created)} af {pending.summary.created_by} (version {pending.summary.app_version})<br />
      {pending.summary.plcs} PLC'er · {pending.summary.tags} tags · {pending.summary.drawings} tegninger
      ({pending.summary.versions} versioner) · {pending.summary.bindings} bindinger
    </div>
    <label class="row"><input type="checkbox" bind:checked={confirmed} /> Jeg forstår, at den nuværende opsætning bliver erstattet</label>
    <div class="row" style="margin-top: .5rem">
      <button class="primary" onclick={restore} disabled={!confirmed || busy}>{busy ? 'Gendanner …' : 'Gendan'}</button>
      <button onclick={() => (pending = null)} disabled={busy}>Annullér</button>
    </div>
  {/if}

  {#if result}
    <div class="notice ok-box">
      Gendannet: {result.plcs} PLC'er, {result.tags} tags, {result.drawings} tegninger ({result.versions} versioner),
      {result.bindings} bindinger. Den tidligere tilstand er gemt som <code>{result.pre_restore_backup}</code>.
    </div>
    {#if result.missing_passwords.length}
      <div class="notice">
        Disse PLC'er mangler adgangskode og kører ikke, før den er sat under <a href="#plcs">PLC'er</a>:
        <strong>{result.missing_passwords.join(', ')}</strong>
      </div>
    {/if}
  {/if}
</section>

<section class="panel">
  <h2>Backups på serveren</h2>
  <p class="muted small">Automatiske backups (de seneste gemmes) og backups taget lige før en gendannelse.</p>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Fil</th><th>Type</th><th>Tidspunkt</th><th>Størrelse</th><th></th></tr></thead>
      <tbody>
        {#each files as f (f.name)}
          <tr>
            <td class="mono small">{f.name}</td>
            <td>{f.kind}</td>
            <td class="small">{fmtDate(f.created)}</td>
            <td class="small">{Math.max(1, Math.round(f.size / 1024))} KB</td>
            <td><a class="btn" href={`/api/backup/files/${encodeURIComponent(f.name)}`} download>Hent</a></td>
          </tr>
        {:else}
          <tr><td colspan="5" class="muted">Ingen endnu — den første automatiske backup tages 5 minutter efter opstart.</td></tr>
        {/each}
      </tbody>
    </table>
  </div>
</section>

<style>
  .ok-box { background: #e8f5e9; border-color: #a5d6a7; }
</style>
