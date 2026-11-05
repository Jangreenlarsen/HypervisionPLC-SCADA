<script lang="ts">
  // "Gem som symbol" (v3.28.0): det valgte objekt/den valgte gruppe gemmes i symbolbiblioteket med grafik, navngivne dele
  // og standardopsætning. Selve udtrækket sker på serveren (services/library.py) ud fra tegningens gemte version.
  import { post } from './api';
  import { OWN_SECTION, sections, type OwnSymbol } from './library';
  import { library, loadLibrary } from './libraryStore.svelte';
  import { sanitizeSvgFragment } from './svg';

  let { drawingId, version, element, box, markup, suggested, onclose, ondone }: {
    drawingId: string;
    version: number | null;
    element: string;
    /** Objektets boks i tegningen (med egen drejning) — symbolet flyttes til (0,0) */
    box: { x: number; y: number; w: number; h: number };
    /** Objektets SVG til forhåndsvisningen */
    markup: string;
    suggested: string;
    onclose: () => void;
    ondone: (msg: string) => void;
  } = $props();

  // svelte-ignore state_referenced_locally — forslaget er kun startværdien
  let label = $state(suggested);
  let hint = $state('');
  let section = $state(OWN_SECTION);
  let keepTags = $state(false);
  let busy = $state(false);
  let error = $state('');

  // Et symbol kendes på sit navn (et omdøbt symbol beholder sin type)
  const existing = $derived<OwnSymbol | undefined>(library.own.find((s) => s.label.toLowerCase() === label.trim().replace(/\s+/g, ' ').toLowerCase()));
  const preview = $derived(sanitizeSvgFragment(markup));
  const viewBox = $derived(`${box.x - 4} ${box.y - 4} ${box.w + 8} ${box.h + 8}`);

  async function save(): Promise<void> {
    error = '';
    if (!label.trim()) {
      error = 'Giv symbolet et navn';
      return;
    }
    busy = true;
    try {
      const r = await post<OwnSymbol & { warnings: string[]; parts: string[] }>('/api/library/symbols', {
        drawing_id: drawingId, version, element, box, label: label.trim(), hint: hint.trim(), section, keep_tags: keepTags, replace: !!existing,
      });
      await loadLibrary();
      const what = r.version > 1 ? `som version ${r.version}` : 'som nyt symbol';
      const cfg = r.preset ? `med standardopsætning (${r.preset.anims.length} animation${r.preset.anims.length === 1 ? '' : 'er'}${r.preset.op !== 'view' ? ', betjening' : ''})` : 'uden opsætning';
      const warn = r.warnings.length ? ` Bemærk: ${r.warnings.join(' · ')}` : '';
      const upd = r.version > 1 ? ' Tegninger, der bruger en ældre version, ændres ikke — opdatér dem med "Erstat med symbol".' : '';
      ondone(`"${r.label}" er gemt i biblioteket ${what}, ${r.parts.length} navngivne dele, ${cfg}.${upd}${warn}`);
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={onclose}>
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="panel dlg" role="dialog" aria-modal="true" aria-label="Gem som symbol" tabindex="-1" onclick={(e) => e.stopPropagation()}>
    <header class="row head">
      <h2>Gem som symbol</h2>
      <span class="muted small">{Math.round(box.w)} × {Math.round(box.h)}</span>
      <button class="close" onclick={onclose} aria-label="Luk">✕</button>
    </header>
    <div class="body">
      <div class="cols">
        <div class="pv"><svg {viewBox} aria-label="Forhåndsvisning">{@html preview}</svg></div>
        <div class="form">
          <label class="field">Navn i biblioteket
            <input bind:value={label} maxlength="40" placeholder="fx Pumpestation" />
          </label>
          {#if existing}
            <p class="small notice">"{existing.label}" findes allerede (version {existing.version}, gemt af {existing.updated_by}). Den gemmes som <strong>version {existing.version + 1}</strong> — tegninger med den gamle version ændres ikke.</p>
          {/if}
          <label class="field">Forklaring (vises i paletten)
            <input bind:value={hint} maxlength="200" placeholder="fx Pumpe med kontraventil og manometer" />
          </label>
          <label class="field">Sektion
            <select bind:value={section}>
              {#each sections(library.layout) as s (s.id)}<option value={s.id}>{s.label}</option>{/each}
            </select>
          </label>
          <label class="opt"><input type="checkbox" bind:checked={keepTags} /> Behold tags i opsætningen (ellers vælges de, når symbolet sættes op)</label>
        </div>
      </div>
      <p class="small muted">Med i symbolet: grafikken, delene med id (de kan animeres hver for sig), gradienter og opsætningen fra guiden —
        også animationerne fra symboler inde i gruppen. Højst ét symbol i gruppen må have betjening. Tegningen gemmes og udgives først.</p>
      {#if error}<p class="small error" role="alert">{error}</p>{/if}
    </div>
    <footer class="row">
      <span class="spacer"></span>
      <button onclick={onclose}>Annullér</button>
      <button class="primary" onclick={save} disabled={busy || !label.trim()}>{existing ? `Gem som version ${existing.version + 1}` : 'Gem i biblioteket'}</button>
    </footer>
  </div>
</div>

<style>
  .backdrop { position: fixed; inset: 0; background: rgba(0, 0, 0, .35); display: flex; align-items: flex-start; justify-content: center; padding: 6vh 16px 0; z-index: 20; }
  .dlg { width: 100%; max-width: 680px; max-height: 90vh; display: flex; flex-direction: column; box-shadow: 0 8px 30px rgba(0, 0, 0, .25); }
  .head { align-items: baseline; gap: .8rem; }
  .head h2 { margin: 0; }
  .close { margin-left: auto; }
  .body { overflow-y: auto; padding: .2rem 0 .4rem; }
  .cols { display: flex; gap: 1rem; flex-wrap: wrap; }
  .pv { flex: 0 0 180px; height: 160px; border: 1px solid var(--line); border-radius: var(--radius); background: #fff; display: flex; }
  .pv svg { width: 100%; height: 100%; }
  .form { flex: 1 1 300px; min-width: 0; }
  .field { display: flex; flex-direction: column; gap: .2rem; margin: 0 0 .55rem; font-size: .9rem; }
  .field input, .field select { width: 100%; box-sizing: border-box; }
  .opt { display: flex; gap: .4rem; align-items: baseline; margin: .35rem 0; }
  .spacer { flex: 1; }
</style>
