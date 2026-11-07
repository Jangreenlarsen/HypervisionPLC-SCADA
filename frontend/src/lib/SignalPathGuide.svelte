<script lang="ts">
  // Signalveje i Tegn (v4.2.0, PLAN.md › Signalvej): vælg start og slut, find rørvejen, svar på ét spørgsmål pr. ventil/pumpe
  // på vejen, og alle rør på vejen får løbelys, der kører, når betingelsen er opfyldt. Grafen og vejen beregnes her ud fra
  // tegningen (signalPath.ts); backend validerer og gemmer opsætningerne samlet (api/signal_paths.py).
  import { onDestroy } from 'svelte';
  import { ApiError, del, get, post, put } from './api';
  import { ask as askUser } from './ask';
  import {
    ASKS, QUESTION, answerFrom, conditionsFrom, describe, endpoints, findPaths, suggestAnswer, summary,
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
    if (p) await find(p.elements.map((e) => e.element));
  }

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
      {#each answers as a (a.element)}
        {@const r = rows.find((x) => x.id === a.element)}
        {@const own = info.get(a.element)?.tags ?? []}
        {@const t = tagOf(a.src)}
        <div class="q">
          <div><strong>{r?.name || a.element}</strong> <span class="small muted">{r ? QUESTION[r.role] : ''}</span></div>
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

<style>
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
</style>
