<script lang="ts">
  import { onMount } from 'svelte';
  import { del, get, patch, post } from '../lib/api';

  let { canEdit = false }: { canEdit?: boolean } = $props();

  interface DrawingRow { id: string; name: string; active_version: number; version_count: number; updated_at: number }
  interface Version { version: number; comment: string; size: number; width: number | null; height: number | null; created_at: number }
  interface Detail { id: string; name: string; active_version: number; versions: Version[] }
  interface Report { removed_elements: Record<string, number>; removed_attributes: Record<string, number>; element_count: number; orphaned_bindings?: string[] }

  let rows = $state<DrawingRow[]>([]);
  let error = $state('');
  let busy = $state(false);
  let name = $state('');
  let comment = $state('');
  let file = $state<File | null>(null);
  let report = $state<{ title: string; report: Report } | null>(null);
  let open = $state<Detail | null>(null);
  let versionFile = $state<File | null>(null);

  async function refresh(): Promise<void> {
    try {
      rows = await get<DrawingRow[]>('/api/drawings');
    } catch (e) {
      error = (e as Error).message;
    }
  }

  async function readFile(f: File): Promise<string> {
    if (f.size > 5 * 1024 * 1024) throw new Error(`Filen er for stor (${Math.round(f.size / 1024)} KB) — max 5 MB`);
    return f.text();
  }

  async function upload(): Promise<void> {
    if (!file) return;
    error = '';
    busy = true;
    try {
      const svg = await readFile(file);
      const res = await post<{ drawing: Detail; report: Report }>('/api/drawings', {
        name: name.trim() || file.name.replace(/\.svg$/i, ''),
        svg,
        comment,
      });
      report = { title: `"${res.drawing.name}" er uploadet`, report: res.report };
      name = comment = '';
      file = null;
      await refresh();
    } catch (e) {
      error = `Upload fejlede: ${(e as Error).message}`;
    } finally {
      busy = false;
    }
  }

  async function show(id: string): Promise<void> {
    error = '';
    try {
      open = await get<Detail>(`/api/drawings/${encodeURIComponent(id)}`);
    } catch (e) {
      error = (e as Error).message;
    }
  }

  async function uploadVersion(): Promise<void> {
    if (!open || !versionFile) return;
    error = '';
    busy = true;
    try {
      const svg = await readFile(versionFile);
      const res = await post<{ drawing: Detail; version: number; report: Report }>(
        `/api/drawings/${encodeURIComponent(open.id)}/versions`, { svg, comment: '' });
      report = { title: `Version ${res.version} af "${open.name}" er uploadet og aktiv`, report: res.report };
      open = res.drawing;
      versionFile = null;
      await refresh();
    } catch (e) {
      error = `Upload fejlede: ${(e as Error).message}`;
    } finally {
      busy = false;
    }
  }

  async function activate(version: number): Promise<void> {
    if (!open) return;
    try {
      open = await patch<Detail>(`/api/drawings/${encodeURIComponent(open.id)}`, { active_version: version });
      await refresh();
    } catch (e) {
      error = (e as Error).message;
    }
  }

  async function remove(row: DrawingRow): Promise<void> {
    if (!confirm(`Slet tegningen "${row.name}" med alle ${row.version_count} versioner og bindinger?`)) return;
    try {
      await del(`/api/drawings/${encodeURIComponent(row.id)}`);
      if (open?.id === row.id) open = null;
      await refresh();
    } catch (e) {
      error = (e as Error).message;
    }
  }

  const fmtDate = (ts: number) => new Date(ts * 1000).toLocaleString('da-DK');
  const entries = (o: Record<string, number>) => Object.entries(o).map(([k, v]) => `${k} ×${v}`).join(', ');

  onMount(refresh);
</script>

{#if canEdit}
<section class="panel">
  <h2>Upload tegning</h2>
  <p class="muted small">
    SVG fra fx Inkscape, Visio eller draw.io. Giv elementer et <code>id</code> (eller Inkscape-label) der er lig et
    tag-navn, så bindes de automatisk: tekst viser værdien, figurer farves efter til/fra.
    Scripts, event-handlere og eksterne referencer fjernes ved upload.
  </p>
  <div class="grid-form">
    <label>SVG-fil<input type="file" accept=".svg,image/svg+xml" onchange={(e) => (file = (e.currentTarget as HTMLInputElement).files?.[0] ?? null)} /></label>
    <label>Navn<input bind:value={name} placeholder="(filnavnet)" maxlength="80" /></label>
    <label>Kommentar<input bind:value={comment} maxlength="200" /></label>
    <div><button class="primary" disabled={!file || busy} onclick={upload}>Upload</button></div>
  </div>
</section>
{/if}

{#if error}<div class="error">{error}</div>{/if}

{#if report}
  <div class="notice">
    <strong>{report.title}.</strong> {report.report.element_count} elementer med id.
    {#if Object.keys(report.report.removed_elements).length}<br />Fjernet: {entries(report.report.removed_elements)}{/if}
    {#if Object.keys(report.report.removed_attributes).length}<br />Fjernede attributter: {entries(report.report.removed_attributes)}{/if}
    {#if report.report.orphaned_bindings?.length}<br />Bindinger uden element i den nye version: {report.report.orphaned_bindings.join(', ')}{/if}
    <button class="small" onclick={() => (report = null)}>OK</button>
  </div>
{/if}

<section class="panel">
  <h2>Tegninger</h2>
  {#if rows.length}
    <div class="table-wrap">
      <table>
        <thead><tr><th>Navn</th><th>Aktiv version</th><th>Versioner</th><th>Opdateret</th><th></th></tr></thead>
        <tbody>
          {#each rows as r}
            <tr>
              <td><a href={'#overview/' + r.id}>{r.name}</a></td>
              <td>v{r.active_version}</td>
              <td>{r.version_count}</td>
              <td class="small">{fmtDate(r.updated_at)}</td>
              <td>
                <div class="row">
                  <button onclick={() => show(r.id)}>Versioner</button>
                  {#if canEdit}<button class="danger" onclick={() => remove(r)}>Slet</button>{/if}
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    <p class="muted">Ingen tegninger endnu.</p>
  {/if}
</section>

{#if open}
  <section class="panel">
    <div class="row" style="justify-content: space-between">
      <h2>Versioner af "{open.name}"</h2>
      <button onclick={() => (open = null)}>Luk</button>
    </div>
    {#if canEdit}
      <div class="row">
        <input type="file" accept=".svg,image/svg+xml" onchange={(e) => (versionFile = (e.currentTarget as HTMLInputElement).files?.[0] ?? null)} />
        <button class="primary" disabled={!versionFile || busy} onclick={uploadVersion}>Upload ny version</button>
      </div>
    {/if}
    <div class="table-wrap">
      <table>
        <thead><tr><th>Version</th><th>Kommentar</th><th>Størrelse</th><th>Uploadet</th><th></th></tr></thead>
        <tbody>
          {#each open.versions as v}
            <tr>
              <td>v{v.version}{v.version === open.active_version ? ' (aktiv)' : ''}</td>
              <td>{v.comment}</td>
              <td class="small">{Math.round(v.size / 1024)} KB{v.width ? ` · ${Math.round(v.width)}×${Math.round(v.height ?? 0)}` : ''}</td>
              <td class="small">{fmtDate(v.created_at)}</td>
              <td>
                {#if canEdit && v.version !== open.active_version}<button onclick={() => activate(v.version)}>Gør aktiv</button>{/if}
                <a href={`/api/drawings/${open.id}/svg?version=${v.version}`} target="_blank" rel="noopener">Vis SVG</a>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </section>
{/if}
