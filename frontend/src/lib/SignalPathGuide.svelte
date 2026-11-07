<script lang="ts">
  // Signalveje i Tegn (v4.2.0, PLAN.md › Signalvej): vælg start og slut, find rørvejen, svar på ét spørgsmål pr. ventil/pumpe
  // på vejen, og alle rør på vejen får løbelys, der kører, når betingelsen er opfyldt. Grafen og vejen beregnes her ud fra
  // tegningen (signalPath.ts); backend validerer og gemmer opsætningerne samlet (api/signal_paths.py).
  import { onDestroy, untrack } from 'svelte';
  import { ApiError, del, get, post, put } from './api';
  import { ask as askUser } from './ask';
  import { postStream } from './assist';
  import { assist } from './assistStore.svelte';
  import {
    ASKS, QUESTION, answerFrom, conditionsFrom, describe, endpoints, findPaths, pickNext, suggestAnswer, summary,
    type Answer, type Condition, type Graph, type PathRow, type Pt, type Step, type TagInfo,
  } from './signalPath';

  interface Saved {
    id: number; name: string; start: string; end: string; elements: { element: string; flows: { part: string; reverse: boolean }[] }[];
    conditions: Condition[]; style: { light: string; speed: number; dash: number }; missing: string[]; updated_by: string;
  }
  interface ElInfo { element: string; name?: string; type?: string; configured?: boolean; tags?: TagInfo[]; flows?: string[]; missing?: boolean }

  let { drawingId, ready, selected, graph, highlight, ensureSaved, onchanged }: {
    drawingId: string;
    ready: boolean;
    selected: string[];
    graph: () => Graph | null;
    highlight: (lines: Pt[][], boxes: string[]) => void;
    ensureSaved: () => Promise<boolean>;
    onchanged?: (text: string) => void;
  } = $props();

  let paths = $state<Saved[]>([]);
  let error = $state('');
  let busy = $state(false);
  let editing = $state<{ id: number | null } | null>(null);
  let name = $state('');
  let start = $state('');
  let end = $state('');
  let light = $state('#8fc8ea');
  let speed = $state(40);
  let g = $state<Graph | null>(null);
  let candidates = $state<Step[][]>([]);
  let chosen = $state(0);
  let rows = $state<PathRow[]>([]);
  let info = $state<Map<string, ElInfo>>(new Map());
  let allTags = $state<TagInfo[]>([]);
  let answers = $state<Answer[]>([]);
  let searched = $state(false);
  // "Forklar med egne ord" (v4.3.0): hjælperen udfylder svarene som forslag — intet gemmes, før brugeren trykker Gem
  let explain = $state('');
  let thinking = $state(false);
  let thinkStart = $state(0);
  let thinkSecs = $state(0);
  let thinkNote = $state('');
  let aiSet = $state<Set<string>>(new Set());
  let unfilled = $state<string[]>([]);
  let thinkCtl: AbortController | null = null;
  $effect(() => {
    if (!thinking) return;
    const t = setInterval(() => (thinkSecs = Math.round((Date.now() - thinkStart) / 1000)), 1000);
    return () => clearInterval(t);
  });

  type SuggestEvent = { type: 'queued'; waiting: number } | { type: 'error'; message: string }
    | { type: 'done'; suggestions: Answer[]; unfilled: string[]; ms: number };

  async function suggest(): Promise<void> {
    error = '';
    if (!explain.trim() || !asked.length) return;
    thinking = true;
    thinkStart = Date.now();
    thinkSecs = 0;
    thinkNote = 'Hjælperen læser vejen og din beskrivelse …';
    thinkCtl = new AbortController();
    try {
      await postStream<SuggestEvent>(`${base}/suggest`, {
        text: explain.trim(), questions: asked.map((r) => ({ element: r.id, role: r.role })),
      }, (ev) => {
        if (ev.type === 'queued') thinkNote = `I kø — ${ev.waiting} foran …`;
        else if (ev.type === 'error') error = ev.message;
        else if (ev.type === 'done') {
          const got = new Map(ev.suggestions.map((a) => [a.element, a]));
          answers = answers.map((a) => got.get(a.element) ?? a);
          aiSet = new Set(got.keys());
          unfilled = ev.unfilled;
          thinkNote = `Udfyldt på ${Math.round(ev.ms / 1000)} s — tjek forslagene, før du gemmer.`;
        }
      }, thinkCtl.signal);
    } catch (e) {
      if ((e as Error).name !== 'AbortError') error = (e as Error).message;
      else thinkNote = 'Stoppet.';
    } finally {
      thinking = false;
      thinkCtl = null;
    }
  }

  const base = $derived(`/api/drawings/${encodeURIComponent(drawingId)}/signal-paths`);
  const ends = $derived(g ? endpoints(g) : []);
  const asked = $derived(rows.filter((r) => ASKS.includes(r.role)));
  const noFlow = $derived(rows.filter((r) => r.role === 'pipe' && !r.flows.length));
  const taken = $derived(rows.filter((r) => r.flows.some((f) => info.get(r.id)?.flows?.includes(f.part))));
  const label = (id: string) => ends.find((e) => e.id === id)?.label ?? (info.get(id)?.name || id);

  $effect(() => { void drawingId; load(); });
  onDestroy(() => highlight([], []));

  /** Vis vejen i tegningen: orange langs rørene (de dele, der får løbelys), ramme om resten. */
  function show(list: PathRow[]): void {
    const byId = new Map((g?.nodes ?? []).map((n) => [n.id, n]));
    const lines: Pt[][] = [];
    const boxes: string[] = [];
    for (const r of list) {
      const n = byId.get(r.id);
      const parts = r.flows.map((f) => n?.lines.find((l) => l.part === f.part)).filter((l) => l !== undefined);
      if (parts.length) parts.forEach((l) => lines.push(l.pts ?? [l.a, l.b]));
      else boxes.push(r.id);
    }
    highlight(lines, boxes);
  }

  async function load(): Promise<void> {
    try {
      paths = await get<Saved[]>(base);
    } catch (e) {
      error = (e as Error).message;
    }
  }

  async function begin(p: Saved | null): Promise<void> {
    error = '';
    if (!(await ensureSaved())) return;
    g = graph();
    if (!g) {
      error = 'Tegningen er ikke klar endnu';
      return;
    }
    editing = { id: p?.id ?? null };
    name = p?.name ?? '';
    start = p?.start ?? '';
    end = p?.end ?? '';
    light = p?.style.light ?? '#8fc8ea';
    speed = p?.style.speed ?? 40;
    candidates = [];
    rows = [];
    searched = false;
    answers = (p?.conditions ?? []).map(answerFrom);
    explain = '';
    thinkNote = '';
    aiSet = new Set();
    unfilled = [];
    if (p) await find(p.elements.map((e) => e.element));
  }

  // Vælg start og slut ved at klikke i tegningen (v4.5.0): første klik = start, andet = slut, så findes vejen af sig selv
  let picking = $state<'start' | 'end' | null>(null);
  let pickNote = $state('');
  let pickBase = '';
  function startPick(): void {
    error = '';
    candidates = [];
    rows = [];
    searched = false;
    start = end = '';
    picking = 'start';
    pickBase = selected.join(',');   // det, der allerede er valgt, tæller ikke — kun et nyt klik
    pickNote = 'Klik på startsymbolet i tegningen …';
    highlight([], []);
  }
  function stopPick(): void {
    picking = null;
    pickNote = '';
  }
  $effect(() => {
    const sel = selected;
    const key = sel.join(',');
    untrack(() => {
      if (!picking || !sel.length || key === pickBase) return;
      pickBase = key;
      const r = pickNext(picking, sel, new Set(ends.map((e) => e.id)), start);
      if (r.error) {
        pickNote = r.error;
        return;
      }
      if (picking === 'start') {
        start = r.id!;
        picking = 'end';
        pickNote = `Start: ${label(start)} — klik nu på slutsymbolet …`;
        highlight([], [start]);
      } else {
        end = r.id!;
        stopPick();
        void find();
      }
    });
  });

  function fromSelection(which: 'start' | 'end'): void {
    const id = selected.find((s) => ends.some((e) => e.id === s));
    if (!id) {
      error = 'Vælg et symbol i tegningen først (ikke et rør)';
      return;
    }
    error = '';
    if (which === 'start') start = id;
    else end = id;
  }

  async function find(prefer: string[] | null = null): Promise<void> {
    error = '';
    if (!g || !start || !end || start === end) {
      error = 'Vælg to forskellige symboler som start og slut';
      return;
    }
    candidates = findPaths(g, start, end, 3);
    searched = true;
    if (!candidates.length) {
      rows = [];
      highlight([], [start, end]);
      return;
    }
    const want = prefer?.join('>');
    const idx = want ? candidates.findIndex((c) => c.map((s) => s.id).join('>') === want) : -1;
    await choose(idx >= 0 ? idx : 0);
  }

  async function choose(i: number): Promise<void> {
    chosen = i;
    rows = describe(g!, candidates[i]);
    show(rows);
    busy = true;
    try {
      const r = await post<{ elements: ElInfo[]; tags: TagInfo[] }>(`${base}/info`, { elements: rows.map((x) => x.id) });
      info = new Map(r.elements.map((e) => [e.element, e]));
      allTags = r.tags.slice().sort((a, b) => a.name.localeCompare(b.name, 'da'));
      // Svar: behold dem der passer til vejen, foreslå nye ud fra symbolets egne tags
      const old = new Map(answers.map((a) => [a.element, a]));
      answers = rows.filter((x) => ASKS.includes(x.role)).map((x) => old.get(x.id) ?? suggestAnswer(x.id, info.get(x.id)?.tags ?? []));
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  const tagOf = (n: string) => allTags.find((t) => t.name === n);

  async function save(replace = false): Promise<void> {
    error = '';
    const { conditions, errors } = conditionsFrom(answers, allTags);
    if (errors.length) {
      error = errors.join(' · ');
      return;
    }
    if (!name.trim()) {
      error = 'Giv signalvejen et navn';
      return;
    }
    const body = {
      name: name.trim(), start, end, replace, conditions,
      elements: rows.map((r) => ({ element: r.id, flows: r.flows })),
      style: { light, speed, dash: 12 },
    };
    busy = true;
    try {
      const id = editing?.id;
      if (id) await put(`${base}/${id}`, body);
      else await post(base, body);
      onchanged?.(`Signalvejen "${body.name}" er gemt — ${rows.filter((r) => r.flows.length).length} rør har fået løbelys.`);
      editing = null;
      highlight([], []);
      await load();
    } catch (e) {
      const conflicts = e instanceof ApiError && e.status === 409 ? (e.body as { conflicts?: { element: string }[] })?.conflicts : undefined;
      if (conflicts?.length && !replace) {
        busy = false;
        const which = conflicts.map((c) => label(c.element)).join(', ');
        if (await askUser(`${conflicts.length} rør har allerede løbelys (${which}). Skal det erstattes af signalvejens løbelys?`,
          { ok: 'Erstat' })) await save(true);
        return;
      }
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  async function remove(p: Saved): Promise<void> {
    if (!(await askUser(`Slet signalvejen "${p.name}"? Løbelyset og betingelsen fjernes fra rørene; resten af deres opsætning bevares.`,
      { ok: 'Slet', danger: true }))) return;
    busy = true;
    try {
      await del(`${base}/${p.id}`);
      onchanged?.(`Signalvejen "${p.name}" er slettet.`);
      await load();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  function cancel(): void {
    editing = null;
    error = '';
    highlight([], []);
  }
</script>

{#if error}<p class="error small">{error}</p>{/if}

{#if !editing}
  <p class="small muted">En signalvej sætter løbelys på alle rør mellem to symboler på én gang — styret af ventiler og pumper undervejs.</p>
  <div class="row"><button class="primary" onclick={() => begin(null)} disabled={!ready || busy}>Ny signalvej …</button></div>
  {#each paths as p (p.id)}
    <div class="item">
      <div class="grow">
        <strong>{p.name}</strong>
        <div class="small muted">{p.elements.length} dele · {p.conditions.length} betingelser</div>
        {#if p.missing.length}<div class="small warn">{p.missing.length} dele findes ikke længere — ret vejen</div>{/if}
      </div>
      <button class="small" onclick={() => begin(p)} disabled={!ready || busy}>Ret</button>
      <button class="small" onclick={() => remove(p)} disabled={busy} aria-label="Slet {p.name}">Slet</button>
    </div>
  {/each}
{:else}
  <div class="step">
    <h4>1. Start og slut</h4>
    <div class="row">
      {#if picking}
        <button onclick={stopPick}>Afbryd valg</button>
      {:else}
        <button class="primary" onclick={startPick} disabled={busy} title="Klik på startsymbolet og derefter slutsymbolet i tegningen">Vælg på tegningen</button>
      {/if}
    </div>
    {#if pickNote}<p class="small pick" role="status">{pickNote}</p>{/if}
    <p class="small muted">… eller vælg i listerne:</p>
    <label class="field">Start
      <span class="row nowrap">
        <select bind:value={start}><option value="">— vælg —</option>{#each ends as e (e.id)}<option value={e.id}>{e.label}</option>{/each}</select>
        <button class="small" onclick={() => fromSelection('start')} title="Brug symbolet, der er valgt i tegningen">← valgt</button>
      </span>
    </label>
    <label class="field">Slut
      <span class="row nowrap">
        <select bind:value={end}><option value="">— vælg —</option>{#each ends as e (e.id)}<option value={e.id}>{e.label}</option>{/each}</select>
        <button class="small" onclick={() => fromSelection('end')} title="Brug symbolet, der er valgt i tegningen">← valgt</button>
      </span>
    </label>
    <div class="row"><button onclick={() => find()} disabled={busy || !start || !end}>Find vej</button></div>
  </div>

  {#if searched}
    <div class="step">
      <h4>2. Vejen</h4>
      {#if !candidates.length}
        <p class="small warn">Der er ingen sammenhængende vej mellem {label(start)} og {label(end)}. Tjek at rørene sidder fast i
          symbolerne (grønne ender, når røret er valgt), og at T-stykker er sat ind, hvor rør mødes.</p>
      {:else}
        {#each candidates as c, i (i)}
          <label class="opt"><input type="radio" name="sp-vej" checked={chosen === i} onchange={() => choose(i)} />
            {summary(describe(g!, c))}</label>
        {/each}
        <p class="small muted">Vejen er markeret i tegningen.</p>
        {#if noFlow.length}<p class="small warn">Kan ikke få løbelys: {noFlow.map((r) => r.name || r.id).join(', ')}.</p>{/if}
        {#if taken.length}<p class="small warn">Har allerede løbelys (erstattes, hvis du bekræfter): {taken.map((r) => r.name || r.id).join(', ')}.</p>{/if}
      {/if}
    </div>
  {/if}

  {#if rows.length}
    <div class="step">
      <h4>3. Hvornår går der flow?</h4>
      {#if !asked.length}<p class="small muted">Ingen ventiler eller pumper på vejen — løbelyset kører altid.</p>{/if}
      {#if asked.length && assist.available && assist.canAsk}
        <div class="explain">
          <label class="field">Forklar med egne ord <span class="small muted">(hjælperen udfylder forslag)</span>
            <textarea bind:value={explain} rows="2" maxlength="400" disabled={thinking}
                      placeholder="fx når pumpe 5 kører og MVS1 står over 50 %"></textarea>
          </label>
          <div class="row">
            {#if thinking}
              <button onclick={() => thinkCtl?.abort()}>Stop</button>
              <span class="small muted">{thinkNote} {thinkSecs} s</span>
            {:else}
              <button onclick={suggest} disabled={!explain.trim() || busy}>Udfyld med hjælperen</button>
              {#if thinkNote}<span class="small muted">{thinkNote}</span>{:else}<span class="small muted">tager typisk 1–3 min</span>{/if}
            {/if}
          </div>
          {#if unfilled.length && !thinking}
            <p class="small warn">Ikke udfyldt af hjælperen: {unfilled.map((id) => rows.find((r) => r.id === id)?.name || id).join(', ')} — vælg selv.</p>
          {/if}
        </div>
      {/if}
      {#each answers as a (a.element)}
        {@const r = rows.find((x) => x.id === a.element)}
        {@const own = info.get(a.element)?.tags ?? []}
        {@const t = tagOf(a.src)}
        <div class="q">
          <div><strong>{r?.name || a.element}</strong> <span class="small muted">{r ? QUESTION[r.role] : ''}</span>
            {#if aiSet.has(a.element)}<span class="ai" title="Udfyldt af hjælperen — tjek det">forslag</span>{/if}</div>
          <select bind:value={a.src} aria-label="Tag for {r?.name || a.element}">
            <option value="">— ingen betingelse (altid) —</option>
            {#if own.length}<optgroup label="Symbolets egne tags">{#each own as o (o.name)}<option value={o.name}>{o.name}</option>{/each}</optgroup>{/if}
            <optgroup label="Alle tags">{#each allTags as o (o.name)}<option value={o.name}>{o.name}{o.unit ? ` [${o.unit}]` : ''}</option>{/each}</optgroup>
          </select>
          {#if t?.is_bool}
            <select bind:value={a.on} aria-label="Tilstand"><option value={true}>når tagget er til</option><option value={false}>når tagget er fra</option></select>
          {:else if t}
            <span class="row nowrap">
              <select bind:value={a.cmp} aria-label="Sammenligning"><option value="">—</option><option value="ge">≥</option><option value="le">≤</option><option value="eq">=</option></select>
              <input type="number" step="any" bind:value={a.value} aria-label="Grænseværdi" />
              <span class="small muted">{t.unit}</span>
            </span>
          {/if}
        </div>
      {/each}
      {#if asked.length}<p class="small muted">Alle betingelser skal være opfyldt (OG).</p>{/if}
    </div>

    <div class="step">
      <h4>4. Navn og udseende</h4>
      <label class="field">Navn <input bind:value={name} maxlength="60" placeholder="fx Kedel → radiatorer" /></label>
      <span class="row nowrap">
        <label class="field">Lysfarve <input type="color" bind:value={light} /></label>
        <label class="field">Fart <input type="number" min="5" max="500" bind:value={speed} /></label>
      </span>
      <div class="row">
        <button class="primary" onclick={() => save(false)} disabled={busy || !name.trim()}>Gem signalvej</button>
        <button onclick={cancel} disabled={busy}>Annullér</button>
      </div>
    </div>
  {:else}
    <div class="row"><button onclick={cancel}>Annullér</button></div>
  {/if}
{/if}

<svelte:window onkeydown={(e) => { if (e.key === 'Escape' && picking) stopPick(); }} />

<style>
  .pick { background: #fff4e0; border: 1px solid #ff8f00; border-radius: var(--radius); padding: .3rem .45rem; }
  .item { display: flex; align-items: center; gap: .4rem; padding: .35rem 0; border-top: 1px solid var(--line); }
  .grow { flex: 1; min-width: 0; }
  .step { border-top: 1px solid var(--line); padding: .4rem 0; }
  .step h4 { margin: .1rem 0 .35rem; font-size: .9rem; }
  .field { display: flex; flex-direction: column; gap: .15rem; font-size: .85rem; margin-bottom: .35rem; }
  .field select, .field input:not([type='color']) { min-width: 0; }
  .nowrap { flex-wrap: nowrap; gap: .3rem; display: flex; align-items: center; }
  .nowrap select { flex: 1; min-width: 0; }
  .opt { display: flex; gap: .35rem; align-items: flex-start; font-size: .85rem; margin: .2rem 0; }
  .q { display: flex; flex-direction: column; gap: .25rem; padding: .35rem 0; border-bottom: 1px dashed var(--line); }
  .q input[type='number'] { width: 6rem; }
  .warn { color: var(--warn); }
  .explain { background: #fff; border: 1px solid var(--line); border-radius: var(--radius); padding: .4rem; margin-bottom: .4rem; }
  .explain textarea { width: 100%; box-sizing: border-box; resize: vertical; font: inherit; }
  .ai { font-size: .7rem; background: var(--accent); color: #fff; border-radius: 3px; padding: 0 .3rem; margin-left: .3rem; }
</style>
