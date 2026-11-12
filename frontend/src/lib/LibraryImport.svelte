<script lang="ts">
  // Import til symbolbiblioteket (v3.31.0): SVG-filer (én fil = ét symbol, navnet er filnavnet) eller en bibliotekspakke
  // (.hvlib.json fra "Eksportér pakke"). Rensning og udtræk sker på serveren (services/library.py); her vælges filer,
  // sektion og hvad der sker, hvis et navn findes, og resultatet vises pr. fil.
  import { OWN_SECTION, sections } from './library';
  import { importPackage, importSvgFiles, library, type Conflict, type ImportSummary } from './libraryStore.svelte';

  let { kind = 'svg', onclose, ondone }: {
    kind?: 'svg' | 'package';
    onclose: () => void;
    ondone?: (msg: string) => void;
  } = $props();

  const MAX_FILES = 50;
  const MAX_BYTES = 10 * 1024 * 1024;
  let files = $state<File[]>([]);
  let section = $state(OWN_SECTION);
  let conflict = $state<Conflict>('rename');
  let busy = $state(false);
  let error = $state('');
  let result = $state<ImportSummary | null>(null);

  const total = $derived(files.reduce((n, f) => n + f.size, 0));
  const STATUS: Record<string, string> = {
    created: 'Oprettet', version: 'Ny version', renamed: 'Oprettet med nyt navn', skipped: 'Sprunget over', error: 'Fejl',
  };

  function pick(e: Event): void {
    const list = Array.from((e.currentTarget as HTMLInputElement).files ?? []);
    files = list;
    result = null;
    error = '';
    if (kind === 'svg' && list.length > MAX_FILES) error = `Højst ${MAX_FILES} filer ad gangen (du valgte ${list.length})`;
    else if (list.reduce((n, f) => n + f.size, 0) > MAX_BYTES) error = 'Filerne fylder mere end 10 MB tilsammen';
  }

  async function run(): Promise<void> {
    if (!files.length || error) return;
    busy = true;
    error = '';
    result = null;
    try {
      if (kind === 'svg') {
        const payload = await Promise.all(files.map(async (f) => ({ name: f.name, svg: await f.text() })));
        result = await importSvgFiles(payload, section, conflict);
      } else {
        let pkg: unknown;
        try {
          pkg = JSON.parse(await files[0].text());
        } catch {
          throw new Error('Filen er ikke gyldig JSON — vælg en .hvlib.json fra "Eksportér pakke"');
        }
        result = await importPackage(pkg, conflict);
      }
      const c = result.count;
      const ok = c.created + c.version + c.renamed;
      ondone?.(`${ok} symbol${ok === 1 ? '' : 'er'} importeret${c.error ? `, ${c.error} med fejl` : ''}${c.skipped ? `, ${c.skipped} sprunget over` : ''}`);
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={() => !busy && onclose()}>
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="panel dlg" role="dialog" aria-modal="true" aria-label={kind === 'svg' ? 'Importér SVG-symboler' : 'Importér bibliotekspakke'}
       tabindex="-1" onclick={(e) => e.stopPropagation()}>
    <header class="row head">
      <h2>{kind === 'svg' ? 'Importér SVG-symboler' : 'Importér bibliotekspakke'}</h2>
      <button class="close" onclick={onclose} disabled={busy} aria-label="Luk">✕</button>
    </header>
    <div class="body">
      {#if kind === 'svg'}
        <p class="small muted">Hver SVG-fil bliver ét symbol i biblioteket med filnavnet som navn. Elementer med <code>id</code> bliver dele,
          der kan animeres hver for sig. Filen renses for scripts og eksterne links, og store tegninger skaleres ned til 240 punkter.</p>
        <label class="field">SVG-filer (højst {MAX_FILES}, 10 MB i alt)
          <input type="file" accept=".svg,image/svg+xml" multiple onchange={pick} disabled={busy} />
        </label>
        <label class="field">Sektion
          <select bind:value={section} disabled={busy}>
            {#each sections(library.layout) as s (s.id)}<option value={s.id}>{s.label}</option>{/each}
          </select>
        </label>
      {:else}
        <p class="small muted">En pakke (<code>.hvlib.json</code>) fra "Eksportér pakke" på en anden SCADA. Symbolerne får deres grafik og
          standardopsætning — uden tags — og lægges i pakkens sektioner, som oprettes, hvis de mangler.</p>
        <label class="field">Pakke
          <input type="file" accept=".json,application/json" onchange={pick} disabled={busy} />
        </label>
      {/if}
      <label class="field">Hvis et symbol med samme navn findes
        <select bind:value={conflict} disabled={busy}>
          <option value="rename">Opret med nyt navn ("Navn 2")</option>
          <option value="version">Gem som ny version af det eksisterende</option>
          <option value="skip">Spring over</option>
        </select>
      </label>
      {#if files.length}<p class="small muted">{files.length} fil{files.length === 1 ? '' : 'er'}, {Math.ceil(total / 1024)} KB</p>{/if}
      {#if error}<p class="small error" role="alert">{error}</p>{/if}
      {#if result}
        <table class="res">
          <thead><tr><th>Fil / symbol</th><th>Resultat</th></tr></thead>
          <tbody>
            {#each result.results as r, i (i)}
              <tr class={r.status}>
                <td>{r.file}{#if r.label && r.label !== r.file.replace(/\.svg$/i, '')}<span class="muted"> → {r.label}</span>{/if}</td>
                <td>
                  {STATUS[r.status]}{#if r.version && r.status !== 'skipped'}{` (v${r.version})`}{/if}
                  {#if r.parts?.length}<span class="muted small">{` · ${r.parts.length} ${r.parts.length === 1 ? 'del' : 'dele'}`}</span>{/if}
                  {#if r.error}<div class="small error">{r.error}</div>{/if}
                  {#each r.warnings ?? [] as w}<div class="small muted">⚠ {w}</div>{/each}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </div>
    <footer class="row">
      <span class="spacer"></span>
      <button onclick={onclose} disabled={busy}>{result ? 'Luk' : 'Annullér'}</button>
      <button class="primary" onclick={run} disabled={busy || !files.length || !!error}>{busy ? 'Importerer …' : 'Importér'}</button>
    </footer>
  </div>
</div>

<style>
  .backdrop { position: fixed; inset: 0; background: rgba(0, 0, 0, .35); display: flex; align-items: flex-start; justify-content: center; padding: 6vh 16px 0; z-index: 38; }
  .dlg { width: 100%; max-width: 640px; max-height: 90vh; display: flex; flex-direction: column; box-shadow: 0 8px 30px rgba(0, 0, 0, .25); }
  .head { align-items: baseline; gap: .8rem; }
  .head h2 { margin: 0; }
  .close { margin-left: auto; }
  .body { overflow-y: auto; padding: .2rem 0 .4rem; }
  .field { display: flex; flex-direction: column; gap: .2rem; margin: 0 0 .55rem; font-size: .9rem; }
  .field input, .field select { width: 100%; box-sizing: border-box; }
  .res { width: 100%; border-collapse: collapse; font-size: .88rem; margin-top: .4rem; }
  .res th, .res td { text-align: left; padding: 3px 6px; border-bottom: 1px solid var(--line); vertical-align: top; }
  .res tr.error td:first-child { color: #b00020; }
  .res tr.skipped { opacity: .7; }
  .spacer { flex: 1; }
</style>
