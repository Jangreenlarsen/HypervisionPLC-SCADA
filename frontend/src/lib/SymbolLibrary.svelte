<script lang="ts">
  // Opsætning › Symboler › Bibliotek (v3.31.0): organisér hele symbolbiblioteket — egne sektioner (opret, omdøb, slet,
  // rækkefølge), flyt og ordn symboler, omdøb/slet egne symboler — og importér/eksportér (SVG-filer, bibliotekspakke).
  // Opdelingen gemmes samlet med revision (services/library.py), så samtidige ændringer afvises i stedet for at overskrive.
  import { onMount } from 'svelte';
  import { ask } from './ask';
  import LibraryImport from './LibraryImport.svelte';
  import { moveSymbol, moveSymbols, newSectionId, sections, symbolsIn, type Layout } from './library';
  import { defs, deleteOwn, deleteOwnMany, exportPackage, library, loadLibrary, saveLayout, updateOwn } from './libraryStore.svelte';

  let current = $state('egne');
  let busy = $state(false);
  let error = $state('');
  let info = $state('');
  let importKind = $state<'svg' | 'package' | null>(null);
  let newName = $state('');
  let renaming = $state<string | null>(null);    // sektions-id eller symboltype
  let renameText = $state('');
  let renameHint = $state('');

  const secs = $derived(sections(library.layout));
  const cur = $derived(secs.find((s) => s.id === current) ?? secs[0]);
  const list = $derived(cur ? symbolsIn(defs(), library.layout, cur.id) : []);
  const own = (id: string) => id.startsWith('u_');
  const ownRow = (id: string) => library.own.find((s) => s.type === id);

  // Flervalg (v3.35.0): afkryds symboler i sektionen (Shift-klik vælger et interval) og flyt eller slet dem samlet.
  let selected = $state<string[]>([]);
  let lastPick = -1;
  const sel = $derived(selected.filter((id) => list.some((d) => d.id === id)));
  const selOwn = $derived(sel.filter(own));
  const allOn = $derived(list.length > 0 && sel.length === list.length);
  $effect(() => { void current; selected = []; lastPick = -1; });   // ny sektion → nyt valg

  function pick(id: string, i: number, e: MouseEvent): void {
    const on = !selected.includes(id);
    const ids = e.shiftKey && lastPick >= 0 ? list.slice(Math.min(lastPick, i), Math.max(lastPick, i) + 1).map((d) => d.id) : [id];
    selected = on ? [...new Set([...selected, ...ids])] : selected.filter((x) => !ids.includes(x));
    lastPick = i;
  }

  async function moveSelected(section: string): Promise<void> {
    const n = sel.length;
    if (await commit(moveSymbols(defs(), library.layout, sel, section), `${n} symbol${n === 1 ? '' : 'er'} flyttet til ${secs.find((s) => s.id === section)?.label ?? section}`)) {
      selected = [];
    }
  }

  async function removeSelected(): Promise<void> {
    const n = selOwn.length;
    const skip = sel.length - n;
    const names = selOwn.map((id) => list.find((d) => d.id === id)?.label ?? id);
    if (!(await ask(`Slet ${n} eg${n === 1 ? 'et symbol' : 'ne symboler'} fra biblioteket (${names.slice(0, 8).join(', ')}${n > 8 ? ' …' : ''})?`
      + (skip ? ` ${skip} indbygget symbol${skip === 1 ? '' : 'er'} i valget kan ikke slettes og bliver stående.` : '')
      + ' Tegninger, der bruger dem, beholder deres kopi.', { ok: `Slet ${n}`, danger: true }))) return;
    busy = true;
    error = info = '';
    try {
      const r = await deleteOwnMany(selOwn);
      const used = Object.values(r.used_in).flat();
      const drawings = new Set(used).size;
      info = `${r.deleted} symbol${r.deleted === 1 ? '' : 'er'} er slettet.${drawings ? ` ${Object.keys(r.used_in).length} af dem står stadig i ${drawings} tegning${drawings === 1 ? '' : 'er'} — som en kopi.` : ''}`;
      selected = [];
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  onMount(() => { void loadLibrary(); });

  /** Forhåndsvisningen tilpasses symbolets egen størrelse (getBBox), som i Symboltest. */
  function fit(node: SVGSVGElement, _svg: string) {
    const run = () => {
      try {
        const b = (node.firstElementChild as SVGGraphicsElement).getBBox();
        const pad = Math.max(b.width, b.height) * 0.08 + 2, size = Math.max(b.width, b.height) + 2 * pad;
        node.setAttribute('viewBox', `${b.x + b.width / 2 - size / 2} ${b.y + b.height / 2 - size / 2} ${size} ${size}`);
      } catch { /* ikke tegnet endnu — standardvinduet bruges */ }
    };
    run();
    return { update: run };
  }

  /** Gem en ændret opdeling; ved konflikt hentes biblioteket igen, og fejlen vises. */
  async function commit(next: Layout, msg = ''): Promise<boolean> {
    busy = true;
    error = info = '';
    try {
      await saveLayout(next);
      info = msg;
      return true;
    } catch (e) {
      error = (e as Error).message;
      await loadLibrary();
      return false;
    } finally {
      busy = false;
    }
  }

  function moveSection(id: string, d: -1 | 1): void {
    const ids = secs.map((s) => s.id);
    const i = ids.indexOf(id);
    const j = i + d;
    if (i < 0 || j < 0 || j >= ids.length) return;
    [ids[i], ids[j]] = [ids[j], ids[i]];
    void commit({ ...library.layout, order: ids });
  }

  async function addSection(): Promise<void> {
    const label = newName.trim();
    if (!label) return;
    if (secs.some((s) => s.label.toLowerCase() === label.toLowerCase())) { error = `Sektionen "${label}" findes allerede`; return; }
    const id = newSectionId(library.layout);
    if (await commit({ ...library.layout, sections: [...library.layout.sections, { id, label }], order: [...secs.map((s) => s.id), id] },
      `Sektionen "${label}" er oprettet`)) {
      newName = '';
      current = id;
    }
  }

  async function renameSection(id: string): Promise<void> {
    const label = renameText.trim();
    if (!label) return;
    if (await commit({ ...library.layout, sections: library.layout.sections.map((s) => (s.id === id ? { ...s, label } : s)) })) renaming = null;
  }

  async function deleteSection(id: string, label: string): Promise<void> {
    const n = symbolsIn(defs(), library.layout, id).length;
    if (!(await ask(`Slet sektionen "${label}"?${n ? ` Dens ${n} symboler flyttes: egne til "Egne symboler", indbyggede tilbage til deres kategori.` : ''}`,
      { ok: 'Slet sektion', danger: true }))) return;
    if (await commit({ ...library.layout, sections: library.layout.sections.filter((s) => s.id !== id), order: secs.map((s) => s.id).filter((x) => x !== id) },
      `Sektionen "${label}" er slettet`)) current = 'egne';
  }

  function moveTo(id: string, section: string, index: number): void {
    void commit(moveSymbol(defs(), library.layout, id, section, index));
  }

  async function saveOwn(type: string): Promise<void> {
    busy = true;
    error = info = '';
    try {
      await updateOwn(type, renameText.trim(), renameHint.trim());
      renaming = null;
      info = 'Symbolet er gemt';
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  async function removeOwn(type: string, label: string): Promise<void> {
    if (!(await ask(`Slet "${label}" fra biblioteket? Tegninger, der bruger det, beholder deres kopi.`, { ok: 'Slet symbol', danger: true }))) return;
    busy = true;
    error = info = '';
    try {
      const used = await deleteOwn(type);
      info = `"${label}" er slettet.${used.length ? ` Det står stadig i ${used.length} tegning${used.length === 1 ? '' : 'er'} (${used.slice(0, 5).join(', ')}${used.length > 5 ? ' …' : ''}) — som en kopi.` : ''}`;
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  async function download(): Promise<void> {
    busy = true;
    error = info = '';
    try {
      const pkg = await exportPackage();
      const n = (pkg as { symbols: unknown[] }).symbols.length;
      if (!n) { info = 'Der er ingen egne symboler at eksportere'; return; }
      const url = URL.createObjectURL(new Blob([JSON.stringify(pkg, null, 1)], { type: 'application/json' }));
      const a = Object.assign(document.createElement('a'), { href: url, download: `symboler-${new Date().toISOString().slice(0, 10)}.hvlib.json` });
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      info = `${n} egne symboler eksporteret (uden tags)`;
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }
</script>

<div class="row tools">
  <button onclick={() => (importKind = 'svg')} disabled={busy}>Importér SVG …</button>
  <button onclick={() => (importKind = 'package')} disabled={busy}>Importér pakke …</button>
  <button onclick={download} disabled={busy || !library.own.length}>Eksportér pakke</button>
  <span class="muted small">{library.own.length} egne symboler</span>
</div>
{#if library.error}<p class="error small">{library.error}</p>{/if}
{#if error}<p class="error" role="alert">{error}</p>{/if}
{#if info}<p class="notice">{info}</p>{/if}

<div class="layout">
  <aside class="panel">
    <h3>Sektioner</h3>
    <ul class="secs">
      {#each secs as s, i (s.id)}
        <li class:on={s.id === cur?.id}>
          {#if renaming === s.id}
            <input bind:value={renameText} maxlength="40" aria-label="Sektionens navn"
                   onkeydown={(e) => e.key === 'Enter' && renameSection(s.id)} />
            <button onclick={() => renameSection(s.id)} disabled={busy}>Gem</button>
            <button onclick={() => (renaming = null)}>✕</button>
          {:else}
            <button class="name" onclick={() => (current = s.id)}>{s.label} <span class="muted small">({symbolsIn(defs(), library.layout, s.id).length})</span></button>
            <button class="ic" title="Flyt op" aria-label="Flyt {s.label} op" onclick={() => moveSection(s.id, -1)} disabled={busy || i === 0}>▲</button>
            <button class="ic" title="Flyt ned" aria-label="Flyt {s.label} ned" onclick={() => moveSection(s.id, 1)} disabled={busy || i === secs.length - 1}>▼</button>
            {#if !s.builtin}
              <button class="ic" title="Omdøb" aria-label="Omdøb {s.label}" onclick={() => { renaming = s.id; renameText = s.label; }} disabled={busy}>Omdøb</button>
              <button class="ic" title="Slet" aria-label="Slet {s.label}" onclick={() => deleteSection(s.id, s.label)} disabled={busy}>Slet</button>
            {/if}
          {/if}
        </li>
      {/each}
    </ul>
    <div class="row add">
      <input bind:value={newName} maxlength="40" placeholder="Ny sektion" aria-label="Navn på ny sektion"
             onkeydown={(e) => e.key === 'Enter' && addSection()} />
      <button onclick={addSection} disabled={busy || !newName.trim()}>Opret</button>
    </div>
  </aside>

  <section class="panel">
    <h3>{cur?.label} <span class="muted small">— {list.length} symboler</span></h3>
    {#if list.length}
      <div class="row selbar">
        <label class="chk"><input type="checkbox" checked={allOn} indeterminate={sel.length > 0 && !allOn} disabled={busy}
                                  onchange={() => { selected = allOn ? [] : list.map((d) => d.id); lastPick = -1; }} /> Vælg alle</label>
        {#if sel.length}
          <span class="small"><strong>{sel.length}</strong> valgt</span>
          <select aria-label="Flyt de valgte til sektion" disabled={busy} value=""
                  onchange={(e) => { const v = (e.currentTarget as HTMLSelectElement).value; (e.currentTarget as HTMLSelectElement).value = ''; if (v) void moveSelected(v); }}>
            <option value="">Flyt valgte til …</option>
            {#each secs as s (s.id)}{#if s.id !== cur.id}<option value={s.id}>{s.label}</option>{/if}{/each}
          </select>
          <button class="danger-btn" onclick={removeSelected} disabled={busy || !selOwn.length}
                  title={selOwn.length ? 'Slet de valgte egne symboler' : 'Kun egne symboler kan slettes'}>Slet valgte ({selOwn.length})</button>
          <button onclick={() => (selected = [])} disabled={busy}>Fravælg</button>
        {:else}
          <span class="muted small">Afkryds symboler for at flytte eller slette flere på én gang (Shift-klik vælger et interval).</span>
        {/if}
      </div>
    {/if}
    {#if !list.length}<p class="muted small">Ingen symboler i sektionen. Flyt symboler hertil fra en anden sektion, eller importér SVG-filer.</p>{/if}
    <ul class="syms">
      {#each list as d, i (d.id)}
        {@const row = ownRow(d.id)}
        <li class:picked={sel.includes(d.id)}>
          <input type="checkbox" class="pick" checked={sel.includes(d.id)} disabled={busy} aria-label="Vælg {d.label}"
                 onclick={(e) => pick(d.id, i, e)} />
          <svg class="pv" viewBox="0 0 100 100" aria-hidden="true" use:fit={d.svg}>{@html d.svg}</svg>
          <div class="info">
            {#if renaming === d.id}
              <input bind:value={renameText} maxlength="40" aria-label="Symbolets navn" />
              <input bind:value={renameHint} maxlength="200" placeholder="Forklaring" aria-label="Forklaring" />
              <span class="row"><button class="primary" onclick={() => saveOwn(d.id)} disabled={busy || !renameText.trim()}>Gem</button>
                <button onclick={() => (renaming = null)}>Annullér</button></span>
            {:else}
              <strong>{d.label}</strong>
              {#if row}<span class="tag" title="Gemt af {row.updated_by}">eget · v{row.version}</span>{/if}
              <div class="muted small">{d.hint}</div>
            {/if}
          </div>
          <div class="acts">
            <button class="ic" title="Flyt op" aria-label="Flyt {d.label} op" onclick={() => moveTo(d.id, cur.id, i - 1)} disabled={busy || i === 0}>▲</button>
            <button class="ic" title="Flyt ned" aria-label="Flyt {d.label} ned" onclick={() => moveTo(d.id, cur.id, i + 1)} disabled={busy || i === list.length - 1}>▼</button>
            <select aria-label="Flyt {d.label} til sektion" disabled={busy} value={cur.id}
                    onchange={(e) => moveTo(d.id, (e.currentTarget as HTMLSelectElement).value, 100000)}>
              {#each secs as s (s.id)}<option value={s.id}>{s.id === cur.id ? 'Flyt til …' : s.label}</option>{/each}
            </select>
            {#if own(d.id) && row}
              <button class="ic" title="Omdøb" aria-label="Omdøb {d.label}" onclick={() => { renaming = d.id; renameText = row.label; renameHint = row.hint; }} disabled={busy}>Omdøb</button>
              <button class="ic" title="Slet" aria-label="Slet {d.label}" onclick={() => removeOwn(d.id, d.label)} disabled={busy}>Slet</button>
            {/if}
          </div>
        </li>
      {/each}
    </ul>
  </section>
</div>

{#if importKind}
  <LibraryImport kind={importKind} onclose={() => (importKind = null)} ondone={(m) => (info = m)} />
{/if}

<style>
  .tools { gap: .5rem; align-items: center; flex-wrap: wrap; margin-bottom: .6rem; }
  .layout { display: grid; grid-template-columns: 320px minmax(0, 1fr); gap: 1rem; align-items: start; }
  @media (max-width: 860px) { .layout { grid-template-columns: 1fr; } }
  h3 { margin: 0 0 .5rem; }
  .secs, .syms { list-style: none; margin: 0; padding: 0; }
  .secs li { display: flex; gap: 2px; align-items: center; padding: 2px 4px; border-radius: 4px; }
  .secs li.on { background: #dbe8ff; }
  .secs .name { flex: 1; text-align: left; border: 0; background: transparent; padding: 4px 2px; }
  .secs input { flex: 1; min-width: 0; }
  .ic { padding: 1px 6px; min-width: 0; font-size: .8rem; }
  .add { gap: .4rem; margin-top: .6rem; }
  .add input { flex: 1; min-width: 0; }
  .syms li { display: flex; gap: .7rem; align-items: center; padding: 6px 2px; border-bottom: 1px solid var(--line); }
  .pv { width: 56px; height: 56px; flex: 0 0 56px; background: #fff; border: 1px solid var(--line); border-radius: 4px; }
  .info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: .15rem; }
  .info input { width: 100%; box-sizing: border-box; }
  .acts { display: flex; gap: 3px; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
  .acts select { max-width: 9rem; font-size: .8rem; }
  .selbar { gap: .5rem; align-items: center; flex-wrap: wrap; padding: 4px 2px 6px; border-bottom: 1px solid var(--line); }
  .selbar select { font-size: .85rem; }
  .chk { display: inline-flex; gap: .3rem; align-items: center; }
  .pick { flex: 0 0 auto; width: 1rem; height: 1rem; }
  .syms li.picked { background: #eef4ff; }
  .danger-btn:not(:disabled) { background: #b3261e; border-color: #b3261e; color: #fff; }
  .tag { font-size: .7rem; padding: 0 6px; border-radius: 8px; background: #e7f3e8; color: #2e7d32; border: 1px solid #a9d3ab; align-self: flex-start; }
</style>
