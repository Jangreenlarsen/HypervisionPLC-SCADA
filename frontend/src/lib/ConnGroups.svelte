<script lang="ts">
  // Flow i Tegn (v6.1.0): forbindelsesgrupperne — hvordan rør og rørstykker viser det beregnede flow på Overview. Alle forbindelser
  // er fra start i "Alle forbindelser" (løbelys); vælg forbindelser på tegningen og lav en egen gruppe med andre animationer.
  // Ligger i et vindue over tegningen (FloatWin), ikke i sidemenuen.
  import { del, get, post, put } from './api';
  import { ask } from './ask';
  import {
    CONN_ANIM_TXT, MAX_CONN_ANIMS, connAnimError, describeConnAnims, newConnAnim, pickConnections,
    type ConnAnim, type ConnAnimType, type ConnList,
  } from './connGroups';

  let { drawingId, ready, selected, select, ensureSaved }: {
    drawingId: string; ready: boolean; selected: string[];
    select: (ids: string[]) => void;
    ensureSaved: () => Promise<boolean>;
  } = $props();

  let data = $state<ConnList | null>(null);
  let error = $state('');
  let info = $state('');
  let busy = $state(false);
  let newName = $state('');
  let editing = $state<{ id: number | 'default'; anims: ConnAnim[] } | null>(null);
  const base = $derived(`/api/drawings/${encodeURIComponent(drawingId)}/connection-groups`);

  async function load(): Promise<void> {
    try {
      data = await get<ConnList>(base);
      error = '';
    } catch (e) {
      error = (e as Error).message;
    }
  }
  $effect(() => { void drawingId; void load(); });

  const chosen = $derived(data ? pickConnections(selected, data.connections) : []);
  const nameOf = (id: string) => data?.connections.find((c) => c.id === id)?.name || id;

  async function run(fn: () => Promise<unknown>, done: string): Promise<void> {
    error = ''; info = '';
    busy = true;
    try {
      if (!(await ensureSaved())) return;
      await fn();
      info = done;
      await load();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }
  const create = () => run(() => post(base, { name: newName.trim(), members: chosen, anims: [newConnAnim('flow')] }),
    `Gruppen "${newName.trim()}" er oprettet med ${chosen.length} forbindelser.`).then(() => { if (!error) newName = ''; });
  const addSel = (id: number, members: string[]) => run(() => put(`${base}/${id}`, { members: [...new Set([...members, ...chosen])] }),
    `${chosen.length} forbindelser er lagt i gruppen.`);
  const removeSel = (id: number, members: string[]) => run(() => put(`${base}/${id}`, { members: members.filter((m) => !chosen.includes(m)) }),
    'De valgte forbindelser er tilbage i "Alle forbindelser".');
  async function remove(id: number, name: string): Promise<void> {
    if (!(await ask(`Slet gruppen "${name}"? Forbindelserne kommer tilbage i "Alle forbindelser".`, { ok: 'Slet', danger: true }))) return;
    await run(() => del(`${base}/${id}`), `Gruppen "${name}" er slettet.`);
  }
  async function rename(id: number, old: string): Promise<void> {
    const name = window.prompt('Gruppens nye navn', old)?.trim();
    if (name && name !== old) await run(() => put(`${base}/${id}`, { name }), `Gruppen hedder nu "${name}".`);
  }
  function edit(id: number | 'default', anims: ConnAnim[]): void {
    editing = { id, anims: structuredClone($state.snapshot(anims)) as ConnAnim[] };
  }
  const editError = $derived(editing ? editing.anims.map(connAnimError).find(Boolean) ?? null : null);
  async function saveAnims(): Promise<void> {
    if (!editing || editError) return;
    const e = editing;
    await run(() => (e.id === 'default' ? put(`${base}/default`, { anims: e.anims }) : put(`${base}/${e.id}`, { anims: e.anims })),
      'Animationerne er gemt — de ses på Overview.');
    if (!error) editing = null;
  }
  function addAnim(t: ConnAnimType): void {
    if (editing && editing.anims.length < MAX_CONN_ANIMS) editing.anims = [...editing.anims, newConnAnim(t)];
  }
</script>

{#snippet animEditor()}
  {#if editing}
    <div class="editor">
      {#each editing.anims as a, i (i)}
        <div class="anim">
          <div class="row"><strong>{CONN_ANIM_TXT[a.type]}</strong><span class="grow"></span>
            <button class="small" onclick={() => editing && (editing.anims = editing.anims.filter((_, k) => k !== i))} aria-label="Fjern animation {i + 1}">Fjern</button></div>
          {#if a.type === 'flow'}
            <label class="small">Fart ved fuldt flow <input type="number" min="5" max="500" bind:value={a.speed} /> enheder/s</label>
            <label class="small">Fuldt flow <input type="number" min="0" max="65535" bind:value={a.full} /> l/min (0 = største pumpe)</label>
            <label class="small">Lys <input type="color" bind:value={a.light} /></label>
            <label class="small">Rør <input type="color" bind:value={a.base} /></label>
          {:else if a.type === 'color'}
            <label class="small">Under første grænse <input type="color" bind:value={a.off} /></label>
            {#each a.limits ?? [] as l, k (k)}
              <div class="row small">fra <input type="number" min="0" step="any" bind:value={l.value} aria-label="Grænse {k + 1}" /> l/min
                <input type="color" bind:value={l.color} aria-label="Farve {k + 1}" />
                <button class="small" onclick={() => (a.limits = (a.limits ?? []).filter((_, j) => j !== k))}>−</button></div>
            {/each}
            {#if (a.limits ?? []).length < 8}<button class="small" onclick={() => (a.limits = [...(a.limits ?? []), { value: ((a.limits ?? []).at(-1)?.value ?? 0) + 10, color: '#43a047' }])}>+ Grænse</button>{/if}
          {:else if a.type === 'blink'}
            <div class="row small">Blink når flowet er
              <select value={a.at_least != null ? 'least' : 'most'} onchange={(e) => { if (e.currentTarget.value === 'least') { a.at_least = a.at_most ?? 1; a.at_most = null; } else { a.at_most = a.at_least ?? 0; a.at_least = null; } }}>
                <option value="most">højst</option><option value="least">mindst</option></select>
              {#if a.at_least != null}<input type="number" min="0" step="any" bind:value={a.at_least} />{:else}<input type="number" min="0" step="any" bind:value={a.at_most} />{/if} l/min
              <select bind:value={a.rate}><option value="slow">langsomt</option><option value="normal">normalt</option><option value="fast">hurtigt</option></select></div>
          {:else}
            <label class="small">Farve <input type="color" bind:value={a.color} /></label>
          {/if}
        </div>
      {/each}
      {#if !editing.anims.length}<p class="small muted">Ingen animation: forbindelserne vises som tegnet.</p>{/if}
      <div class="row wrap">
        {#if editing.anims.length < MAX_CONN_ANIMS}
          <select aria-label="Tilføj animation" onchange={(e) => { addAnim(e.currentTarget.value as ConnAnimType); e.currentTarget.value = ''; }}>
            <option value="">+ Animation …</option>{#each Object.entries(CONN_ANIM_TXT) as [t, txt]}<option value={t}>{txt}</option>{/each}
          </select>
        {/if}
        <span class="grow"></span>
        <button onclick={() => (editing = null)} disabled={busy}>Fortryd</button>
        <button class="primary" onclick={saveAnims} disabled={busy || !!editError} title={editError ?? ''}>Gem</button>
      </div>
      {#if editError}<p class="small err">{editError}</p>{/if}
    </div>
  {/if}
{/snippet}

<div class="cg">
  <p class="small muted">Serveren beregner flowet gennem de forbundne symboler (pumper, ventiler, restriktion — sættes op i symbol-guidens
    trin 4 under <em>Flow</em>). Her bestemmer du, hvordan forbindelserne viser det på Overview.</p>
  {#if error}<p class="msg err">{error}</p>{/if}
  {#if info}<p class="msg ok">{info}</p>{/if}
  {#if data}
    {#if data.flow?.unbound}<p class="msg">Tegningen har ingen gemte forbindelser. Slå <strong>Tjek forbindelser</strong> til og tryk
      <strong>Bind forbindelser</strong> (Vis-menuen), og gem tegningen — flowet beregnes kun gennem gemte forbindelser.</p>{/if}
    {#each data.flow?.notes ?? [] as n}<p class="msg">{n}</p>{/each}
    {#if data.flow?.stats}<p class="small muted">Beregning: {data.flow.stats.pumping} af {data.flow.stats.pumps} pumper kører · {data.flow.stats.edges} forbindelser i nettet.</p>{/if}

    <div class="grp">
      <div class="row"><strong>Alle forbindelser</strong> <span class="muted small">({data.default.members.length})</span><span class="grow"></span>
        <button class="small" onclick={() => select(data!.default.members)} disabled={!ready}>Vis</button>
        <button class="small" onclick={() => edit('default', data!.default.anims)} disabled={busy}>Animationer</button></div>
      <div class="small muted">{describeConnAnims(data.default.anims)} · bruges kun på tegninger med en pumpe</div>
      {#if editing?.id === 'default'}{@render animEditor()}{/if}
    </div>

    {#each data.groups as g (g.id)}
      <div class="grp">
        <div class="row"><strong>{g.name}</strong> <span class="muted small">({g.members.length})</span><span class="grow"></span>
          <button class="small" onclick={() => select(g.members)} disabled={!ready || !g.members.length}>Vis</button>
          <button class="small" onclick={() => edit(g.id, g.anims)} disabled={busy}>Animationer</button>
          <button class="small" onclick={() => rename(g.id, g.name)} disabled={busy}>Omdøb</button>
          <button class="small danger" onclick={() => remove(g.id, g.name)} disabled={busy}>Slet</button></div>
        <div class="small muted">{describeConnAnims(g.anims)}{g.missing?.length ? ` · ${g.missing.length} findes ikke længere i tegningen` : ''}</div>
        <div class="row small">
          <button class="small" onclick={() => addSel(g.id, g.members)} disabled={busy || !chosen.length}>+ Valgte ({chosen.length})</button>
          <button class="small" onclick={() => removeSel(g.id, g.members)} disabled={busy || !chosen.some((c) => g.members.includes(c))}>− Valgte</button>
        </div>
        {#if editing?.id === g.id}{@render animEditor()}{/if}
      </div>
    {/each}

    <div class="new">
      <strong>Ny gruppe</strong>
      <p class="small muted">Vælg rør og rørstykker på tegningen (Skift+klik eller træk en ramme). {chosen.length
        ? `Valgt: ${chosen.slice(0, 6).map(nameOf).join(', ')}${chosen.length > 6 ? ` … (${chosen.length})` : ''}` : 'Ingen forbindelser er valgt.'}</p>
      <div class="row">
        <input placeholder="Gruppens navn" bind:value={newName} aria-label="Ny gruppes navn" maxlength="60" />
        <button class="primary" onclick={create} disabled={busy || !newName.trim() || !chosen.length}>Opret af valgte</button>
      </div>
    </div>
  {:else if !error}<p class="small muted">Henter …</p>{/if}
</div>

<style>
  .cg { display: flex; flex-direction: column; gap: .5rem; }
  .grp, .new { border: 1px solid var(--line); border-radius: 6px; padding: .4rem .55rem; display: flex; flex-direction: column; gap: .25rem; }
  .row { display: flex; align-items: center; gap: .35rem; }
  .row.wrap { flex-wrap: wrap; }
  .grow { flex: 1; }
  .editor { border-top: 1px dashed var(--line); margin-top: .3rem; padding-top: .3rem; display: flex; flex-direction: column; gap: .4rem; }
  .anim { display: flex; flex-direction: column; gap: .2rem; background: var(--panel-2, #f6f6f6); border-radius: 5px; padding: .3rem .45rem; }
  .anim input[type='number'] { width: 5.5rem; }
  .msg { padding: .35rem .5rem; background: #fff8e1; border: 1px solid #e0b062; border-radius: 6px; margin: 0; }
  .msg.err, .err { color: #b71c1c; }
  .msg.ok { background: #e8f5e9; border-color: #81c784; }
  .new input { flex: 1; }
</style>
