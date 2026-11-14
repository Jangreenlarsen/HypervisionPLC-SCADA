<script lang="ts">
  // Forbindelsernes animationer (v6.1.0 forbindelsesgrupper; v6.12.0 Til/Fra, Jan: "en general config af de animationer for on/off
  // som forbindelser skal bruge"). Hele tegningen har én opsætning: **Til** (der er flow) og **Fra** (intet flow). Egne grupper er
  // **undtagelser** med deres egen Til/Fra. Animationer, der ikke kan vises som Til/Fra, redigeres under *Avanceret*.
  // Ligger i et vindue over tegningen (FloatWin), åbnet fra menuen Forbindelser.
  import { del, get, post, put } from './api';
  import { ask } from './ask';
  import {
    CONN_ANIM_TXT, MAX_CONN_ANIMS, connAnimError, defaultOnOff, describeOnOff, fromOnOff, newConnAnim, pickConnections, toOnOff,
    type ConnAnim, type ConnAnimType, type ConnList, type OnOff,
  } from './connGroups';

  let { drawingId, ready, selected, select, ensureSaved }: {
    drawingId: string; ready: boolean; selected: string[];
    select: (ids: string[]) => void;
    ensureSaved: () => Promise<boolean>;
  } = $props();

  interface Editing {
    id: number | 'default';
    mode: 'onoff' | 'adv';
    m: OnOff;                         // Til/Fra (mode onoff)
    offMode: 'drawn' | 'color';       // Fra: som tegnet eller en farve (farven huskes, når man skifter frem og tilbage)
    offColor: string;
    anims: ConnAnim[];                // listen (mode adv)
  }

  let data = $state<ConnList | null>(null);
  let error = $state('');
  let info = $state('');
  let busy = $state(false);
  let newName = $state('');
  let editing = $state<Editing | null>(null);
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
  const create = () => run(() => post(base, { name: newName.trim(), members: chosen, anims: fromOnOff(defaultOnOff()) }),
    `Undtagelsen "${newName.trim()}" er oprettet med ${chosen.length} forbindelser — tryk Redigér for at give den sin egen Til/Fra.`)
    .then(() => { if (!error) newName = ''; });
  const addSel = (id: number, members: string[]) => run(() => put(`${base}/${id}`, { members: [...new Set([...members, ...chosen])] }),
    `${chosen.length} forbindelser er lagt i undtagelsen.`);
  const removeSel = (id: number, members: string[]) => run(() => put(`${base}/${id}`, { members: members.filter((m) => !chosen.includes(m)) }),
    'De valgte forbindelser følger nu hele tegningen igen.');
  async function remove(id: number, name: string): Promise<void> {
    if (!(await ask(`Slet undtagelsen "${name}"? Dens forbindelser følger så hele tegningens Til/Fra.`, { ok: 'Slet', danger: true }))) return;
    await run(() => del(`${base}/${id}`), `Undtagelsen "${name}" er slettet.`);
  }
  async function rename(id: number, old: string): Promise<void> {
    const name = window.prompt('Undtagelsens nye navn', old)?.trim();
    if (name && name !== old) await run(() => put(`${base}/${id}`, { name }), `Undtagelsen hedder nu "${name}".`);
  }

  function edit(id: number | 'default', anims: ConnAnim[]): void {
    const list = structuredClone($state.snapshot(anims)) as ConnAnim[];
    const m = toOnOff(list);
    editing = {
      id, mode: m ? 'onoff' : 'adv', m: m ?? defaultOnOff(),
      offMode: m?.off.color ? 'color' : 'drawn', offColor: m?.off.color || '#9e9e9e', anims: list,
    };
  }
  /** Fra Avanceret tilbage til Til/Fra — kun hvis listen kan vises sådan (ellers ville noget gå tabt). */
  const advAsOnOff = $derived(editing?.mode === 'adv' ? toOnOff(editing.anims) : null);
  function toOnOffMode(): void {
    if (!editing || !advAsOnOff) return;
    Object.assign(editing, { mode: 'onoff', m: advAsOnOff, offMode: advAsOnOff.off.color ? 'color' : 'drawn', offColor: advAsOnOff.off.color || editing.offColor });
  }
  function toAdvanced(): void {
    if (!editing) return;
    editing.anims = fromOnOff(currentOnOff(editing));
    editing.mode = 'adv';
  }
  const currentOnOff = (e: Editing): OnOff => ({ on: { ...e.m.on }, off: { ...e.m.off, color: e.offMode === 'color' ? e.offColor : '' } });
  const animsToSave = (e: Editing): ConnAnim[] => (e.mode === 'onoff' ? fromOnOff(currentOnOff(e)) : e.anims);
  const editError = $derived(editing ? animsToSave(editing).map(connAnimError).find(Boolean) ?? null : null);
  async function saveAnims(): Promise<void> {
    if (!editing || editError) return;
    const e = editing;
    const anims = animsToSave(e);
    await run(() => (e.id === 'default' ? put(`${base}/default`, { anims }) : put(`${base}/${e.id}`, { anims })),
      'Animationerne er gemt — de ses på Overview og i simulatoren.');
    if (!error) editing = null;
  }
  function addAnim(t: ConnAnimType): void {
    if (editing && editing.anims.length < MAX_CONN_ANIMS) editing.anims = [...editing.anims, newConnAnim(t)];
  }
</script>

{#snippet onOffEditor(e: Editing)}
  <div class="onoff">
    <fieldset class="box">
      <legend><span class="dot on"></span>Til — der er flow</legend>
      <div class="seg" role="radiogroup" aria-label="Til vises som">
        {#each [['flow', 'Løbelys'], ['color', 'Farve'], ['none', 'Som tegnet']] as [v, t] (v)}
          <button class="small" class:sel={e.m.on.show === v} role="radio" aria-checked={e.m.on.show === v}
            onclick={() => (e.m.on.show = v as OnOff['on']['show'])}>{t}</button>
        {/each}
      </div>
      <div class="grid" class:dim={e.m.on.show !== 'flow'}>
        <span>Lys</span><input type="color" bind:value={e.m.on.light} disabled={e.m.on.show !== 'flow'} aria-label="Løbelysets farve" />
        <span>Rør</span><input type="color" bind:value={e.m.on.base} disabled={e.m.on.show !== 'flow'} aria-label="Rørets farve under lyset" />
        <span title="Lysets fart ved fuldt flow; mindre flow løber langsommere">Fart</span><span class="unit"><input type="number" min="5" max="500" bind:value={e.m.on.speed} disabled={e.m.on.show !== 'flow'} aria-label="Fart ved fuldt flow" title="Lysets fart ved fuldt flow (tegningens enheder pr. sekund); mindre flow løber langsommere" /> enh./s</span>
        <span title="Flowet, hvor lyset løber med fuld fart (0 = tegningens største pumpe)">Fuldt flow</span><span class="unit"><input type="number" min="0" max="65535" bind:value={e.m.on.full} disabled={e.m.on.show !== 'flow'} aria-label="Fuldt flow" title="Flowet, hvor lyset løber med fuld fart (0 = tegningens største pumpe)" /> l/min</span>
      </div>
      <div class="grid" class:dim={e.m.on.show !== 'color'}>
        <span>Farve</span><input type="color" bind:value={e.m.on.color} disabled={e.m.on.show !== 'color'} aria-label="Farven, når der er flow" />
      </div>
      <div class="blinkrow">
        <label><input type="checkbox" bind:checked={e.m.on.blink} /> Blink</label>
        <select bind:value={e.m.on.rate} disabled={!e.m.on.blink} aria-label="Blinkets fart (Til)">
          <option value="slow">langsomt</option><option value="normal">normalt</option><option value="fast">hurtigt</option></select>
      </div>
    </fieldset>
    <fieldset class="box">
      <legend><span class="dot"></span>Fra — intet flow</legend>
      <div class="seg" role="radiogroup" aria-label="Fra vises som">
        {#each [['drawn', 'Som tegnet'], ['color', 'Farve']] as [v, t] (v)}
          <button class="small" class:sel={e.offMode === v} role="radio" aria-checked={e.offMode === v}
            onclick={() => (e.offMode = v as Editing['offMode'])}>{t}</button>
        {/each}
      </div>
      <div class="grid" class:dim={e.offMode !== 'color'}>
        <span>Farve</span><input type="color" bind:value={e.offColor} disabled={e.offMode !== 'color'} aria-label="Farven, når der intet flow er" />
      </div>
      <div class="blinkrow">
        <label><input type="checkbox" bind:checked={e.m.off.blink} /> Blink</label>
        <select bind:value={e.m.off.rate} disabled={!e.m.off.blink || e.m.on.blink} aria-label="Blinkets fart (Fra)">
          <option value="slow">langsomt</option><option value="normal">normalt</option><option value="fast">hurtigt</option></select>
      </div>
    </fieldset>
  </div>
  <p class="small muted note">{e.m.on.blink && e.m.off.blink ? 'Blink i både Til og Fra: forbindelsen blinker altid (med Til-afsnittets fart).'
    : 'Til = mindst 0,1 l/min gennem forbindelsen. Ved kommunikationsfejl vises forbindelsen som tegnet.'}</p>
{/snippet}

{#snippet animEditor()}
  {#if editing}
    <div class="editor">
      {#if editing.mode === 'onoff'}
        {@render onOffEditor(editing)}
      {:else}
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
              <label class="small">Under første grænse <input type="color" value={a.off || '#9e9e9e'} oninput={(ev) => (a.off = ev.currentTarget.value)} /></label>
              {#each a.limits ?? [] as l, k (k)}
                <div class="row small">fra <input type="number" min="0" step="any" bind:value={l.value} aria-label="Grænse {k + 1}" /> l/min
                  <input type="color" value={l.color || '#43a047'} oninput={(ev) => (l.color = ev.currentTarget.value)} aria-label="Farve {k + 1}" />
                  <button class="small" onclick={() => (a.limits = (a.limits ?? []).filter((_, j) => j !== k))}>−</button></div>
              {/each}
              {#if (a.limits ?? []).length < 8}<button class="small" onclick={() => (a.limits = [...(a.limits ?? []), { value: ((a.limits ?? []).at(-1)?.value ?? 0) + 10, color: '#43a047' }])}>+ Grænse</button>{/if}
            {:else if a.type === 'blink'}
              <div class="row small">Blink når flowet er
                <select value={a.at_least != null ? 'least' : 'most'} onchange={(ev) => { if (ev.currentTarget.value === 'least') { a.at_least = a.at_most ?? 1; a.at_most = null; } else { a.at_most = a.at_least ?? 0; a.at_least = null; } }}>
                  <option value="most">højst</option><option value="least">mindst</option></select>
                {#if a.at_least != null}<input type="number" min="0" step="any" bind:value={a.at_least} />{:else}<input type="number" min="0" step="any" bind:value={a.at_most} />{/if} l/min
                <select bind:value={a.rate}><option value="slow">langsomt</option><option value="normal">normalt</option><option value="fast">hurtigt</option></select></div>
            {:else}
              <label class="small">Farve <input type="color" bind:value={a.color} /></label>
            {/if}
          </div>
        {/each}
        {#if !editing.anims.length}<p class="small muted">Ingen animation: forbindelserne vises som tegnet.</p>{/if}
        {#if editing.anims.length < MAX_CONN_ANIMS}
          <select aria-label="Tilføj animation" onchange={(ev) => { addAnim(ev.currentTarget.value as ConnAnimType); ev.currentTarget.value = ''; }}>
            <option value="">+ Animation …</option>{#each Object.entries(CONN_ANIM_TXT) as [t, txt]}<option value={t}>{txt}</option>{/each}
          </select>
        {/if}
      {/if}
      <div class="row wrap">
        {#if editing.mode === 'onoff'}
          <button class="small" onclick={toAdvanced} title="Animationerne som liste: flere farvegrænser, blink ved et bestemt flow, fast farve">Avanceret …</button>
        {:else}
          <button class="small" onclick={toOnOffMode} disabled={!advAsOnOff}
            title={advAsOnOff ? 'Tilbage til Til og Fra' : 'Listen kan ikke vises som Til og Fra (fx flere farvegrænser eller en fast farve)'}>Til/Fra</button>
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
  <p class="small muted">Hvordan rør og rørstykker viser flowet på <strong>Overview</strong> og i simulatoren: <strong>Til</strong> når der er
    flow, <strong>Fra</strong> når der ikke er. Flowet beregnes ud fra pumper og ventiler (symbol-guidens trin 4 › <em>Flow</em>).</p>
  {#if error}<p class="msg err">{error}</p>{/if}
  {#if info}<p class="msg ok">{info}</p>{/if}
  {#if data}
    {#if data.flow?.unbound}<p class="msg">Tegningen har ingen gemte forbindelser. Slå <strong>Tjek forbindelser</strong> til og tryk
      <strong>Bind forbindelser</strong> (menuen Forbindelser), og gem tegningen — flowet beregnes kun gennem gemte forbindelser.</p>{/if}
    {#each data.flow?.notes ?? [] as n}<p class="msg">{n}</p>{/each}

    <div class="grp">
      <div class="row"><strong>Hele tegningen</strong> <span class="muted small">({data.default.members.length} forbindelser)</span><span class="grow"></span>
        <button class="small" onclick={() => select(data!.default.members)} disabled={!ready}>Vis</button>
        <button class="small" class:on={editing?.id === 'default'} onclick={() => (editing?.id === 'default' ? (editing = null) : edit('default', data!.default.anims))} disabled={busy}>Redigér</button></div>
      <div class="small muted">{describeOnOff(data.default.anims)} · bruges, når tegningen har en pumpe (uden pumpe er der intet flow)</div>
      {#if editing?.id === 'default'}{@render animEditor()}{/if}
    </div>

    <div class="head"><strong>Undtagelser</strong> <span class="small muted">— forbindelser, der skal vise noget andet end resten af tegningen</span></div>
    {#each data.groups as g (g.id)}
      <div class="grp">
        <div class="row"><strong>{g.name}</strong> <span class="muted small">({g.members.length})</span><span class="grow"></span>
          <button class="small" onclick={() => select(g.members)} disabled={!ready || !g.members.length}>Vis</button>
          <button class="small" class:on={editing?.id === g.id} onclick={() => (editing?.id === g.id ? (editing = null) : edit(g.id, g.anims))} disabled={busy}>Redigér</button>
          <button class="small" onclick={() => rename(g.id, g.name)} disabled={busy}>Omdøb</button>
          <button class="small danger" onclick={() => remove(g.id, g.name)} disabled={busy}>Slet</button></div>
        <div class="small muted">{describeOnOff(g.anims)}{g.missing?.length ? ` · ${g.missing.length} findes ikke længere i tegningen` : ''}</div>
        <div class="row small">
          <button class="small" onclick={() => addSel(g.id, g.members)} disabled={busy || !chosen.length}>+ Valgte ({chosen.length})</button>
          <button class="small" onclick={() => removeSel(g.id, g.members)} disabled={busy || !chosen.some((c) => g.members.includes(c))}>− Valgte</button>
        </div>
        {#if editing?.id === g.id}{@render animEditor()}{/if}
      </div>
    {:else}
      <p class="small muted">Ingen undtagelser: alle forbindelser følger hele tegningen.</p>
    {/each}

    <div class="new">
      <strong>Ny undtagelse</strong>
      <p class="small muted">Vælg rør og rørstykker på tegningen (Skift+klik eller træk en ramme). {chosen.length
        ? `Valgt: ${chosen.slice(0, 6).map(nameOf).join(', ')}${chosen.length > 6 ? ` … (${chosen.length})` : ''}` : 'Ingen forbindelser er valgt.'}</p>
      <div class="row">
        <input placeholder="Navn, fx Retur" bind:value={newName} aria-label="Ny undtagelses navn" maxlength="60" />
        <button class="primary" onclick={create} disabled={busy || !newName.trim() || !chosen.length}>Opret af valgte</button>
      </div>
    </div>
    {#if data.flow?.stats}<p class="small muted">Beregning: {data.flow.stats.pumping} af {data.flow.stats.pumps} pumper kører · {data.flow.stats.edges} forbindelser i nettet.</p>{/if}
  {:else if !error}<p class="small muted">Henter …</p>{/if}
</div>

<style>
  .cg { display: flex; flex-direction: column; gap: .5rem; }
  .grp, .new { border: 1px solid var(--line); border-radius: 6px; padding: .4rem .55rem; display: flex; flex-direction: column; gap: .25rem; }
  .head { margin-top: .2rem; }
  .row { display: flex; align-items: center; gap: .35rem; }
  .row.wrap { flex-wrap: wrap; }
  .grow { flex: 1; }
  button.on { outline: 2px solid var(--accent, #1565c0); outline-offset: -1px; }
  .editor { border-top: 1px dashed var(--line); margin-top: .3rem; padding-top: .3rem; display: flex; flex-direction: column; gap: .4rem; }
  .onoff { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; }
  .box { border: 1px solid var(--line); border-radius: 6px; padding: .35rem .5rem .45rem; margin: 0; display: flex; flex-direction: column; gap: .4rem; min-width: 0; }
  .box legend { font-weight: 600; padding: 0 .25rem; display: flex; align-items: center; gap: .35rem; }
  .dot { width: .6rem; height: .6rem; border-radius: 50%; background: #9e9e9e; display: inline-block; }
  .dot.on { background: #43a047; }
  .seg { display: flex; }
  .seg button { flex: 1; border-radius: 0; margin: 0; }
  .seg button:first-child { border-radius: 4px 0 0 4px; }
  .seg button:last-child { border-radius: 0 4px 4px 0; }
  .seg button.sel { background: var(--accent, #1565c0); color: #fff; border-color: var(--accent, #1565c0); }
  .grid { display: grid; grid-template-columns: 4.5rem 1fr; align-items: center; gap: .25rem .4rem; font-size: .85rem; }
  .grid.dim > span { opacity: .45; }
  .grid input[type='number'] { width: 4.5rem; }
  .unit { white-space: nowrap; }
  .grid input[type='color'] { width: 3rem; height: 1.6rem; padding: 0; }
  .blinkrow { display: flex; align-items: center; gap: .4rem; font-size: .85rem; margin-top: auto; }
  .note { margin: 0; min-height: 1.2em; }
  .anim { display: flex; flex-direction: column; gap: .2rem; background: var(--panel-2, #f6f6f6); border-radius: 5px; padding: .3rem .45rem; }
  .anim input[type='number'] { width: 5.5rem; }
  .msg { padding: .35rem .5rem; background: #fff8e1; border: 1px solid #e0b062; border-radius: 6px; margin: 0; }
  .msg.err, .err { color: #b71c1c; }
  .msg.ok { background: #e8f5e9; border-color: #81c784; }
  .new input { flex: 1; }
</style>
