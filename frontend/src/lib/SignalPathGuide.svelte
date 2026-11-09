<script lang="ts">
  // Signalveje i Tegn (v4.2.0; v4.13.0: grene, ventilvalg, ind/ud fra symbolerne og en interaktiv editor — PLAN.md › Signalveje 2).
  // Arbejdsgang: 1) vælg start og slutpunkter (klik i tegningen), 2) vejen beregnes med det samme og vises i tegningen — skift en
  // 3-vejsventils vej, og vejen beregnes forfra — og låses med "Brug denne vej", 3) svar på hvornår der går flow, 4) navn og udseende.
  // Grafen og vejen beregnes her ud fra tegningen (signalPath.ts); backend validerer og gemmer opsætningerne samlet.
  import { onDestroy, untrack } from 'svelte';
  import { ApiError, del, get, post, put } from './api';
  import { ask as askUser } from './ask';
  import { postStream } from './assist';
  import { assist } from './assistStore.svelte';
  import {
    MAX_ENDS, QUESTION, TOL, answerFrom, conditionsFrom, describeNet, endpoints, findPaths, graphKey, pickNext, questionsOf, suggestAnswer,
    type Answer, type Condition, type Graph, type Net, type NetRow, type Pt, type Question, type Step, type TagInfo,
  } from './signalPath';
  import { mergeDefs, parseWay, wayKey, wayLabel, waysOf, type FlowDefs } from './symbolFlow';

  interface Saved {
    id: number; name: string; start: string; end: string; ends: string[]; ui: { forced?: Record<string, Record<string, string>>; picks?: number[] };
    elements: { element: string; flows: { part: string; reverse: boolean }[]; branches?: number[] }[];
    conditions: (Condition & { branches?: number[] })[]; style: { light: string; speed: number; dash: number }; missing: string[]; updated_by: string;
  }
  interface ElInfo { element: string; name?: string; type?: string; configured?: boolean; tags?: TagInfo[]; flows?: string[]; missing?: boolean }
  type QAnswer = Answer & { key: string; branches: number[] };

  let { drawingId, ready, rev = 0, selected, graph, highlight, select, ensureSaved, onchanged }: {
    drawingId: string;
    ready: boolean;
    rev?: number;           // tælles op, hver gang tegningen ændres (flyt, ret, fortryd): vejen regnes så forfra
    selected: string[];
    graph: () => Graph | null;
    highlight: (lines: { pts: Pt[]; color: string; flow: number }[], boxes: { id: string; color: string }[], focus?: string[]) => void;
    select?: (ids: string[]) => void;
    ensureSaved: () => Promise<boolean>;
    onchanged?: (text: string) => void;
  } = $props();

  const COLORS = ['#ff8f00', '#1e88e5', '#43a047', '#8e24aa'];       // en farve pr. gren i tegningen
  const SHARED = '#6d4c41';                                           // stykker, flere grene går igennem
  const branchColor = (b: number) => COLORS[b % COLORS.length];

  let paths = $state<Saved[]>([]);
  let error = $state('');
  let busy = $state(false);
  let editing = $state<{ id: number | null } | null>(null);
  let name = $state('');
  let start = $state('');
  let endIds = $state<string[]>([]);
  let light = $state('#8fc8ea');
  let speed = $state(40);
  let g = $state<Graph | null>(null);
  let defs = $state<FlowDefs>(mergeDefs(null));
  let forced = $state<Record<number, Record<string, string>>>({});   // gren → knude → vej ("AB>A")
  let cands = $state<Step[][][]>([]);                                  // gren → forslag
  let picks = $state<number[]>([]);                                    // gren → valgt forslag
  let net = $state<Net | null>(null);
  let locked = $state(false);
  let info = $state<Map<string, ElInfo>>(new Map());
  let allTags = $state<TagInfo[]>([]);
  let answers = $state<QAnswer[]>([]);
  let saved = $state<Saved['conditions']>([]);                         // betingelserne fra en gemt vej, der rettes
  let focusId = $state('');                                            // rækken, musen peger på
  let activeRow = $state('');                                          // rækken, der er valgt i tegningen
  let ai = $state({ text: '', thinking: false, start: 0, secs: 0, note: '', set: new Set<string>(), unfilled: [] as string[] });
  let thinkCtl: AbortController | null = null;
  $effect(() => {
    if (!ai.thinking) return;
    const t = setInterval(() => (ai.secs = Math.round((Date.now() - ai.start) / 1000)), 1000);
    return () => clearInterval(t);
  });

  type SuggestEvent = { type: 'queued'; waiting: number } | { type: 'error'; message: string }
    | { type: 'done'; suggestions: Answer[]; unfilled: string[]; ms: number };

  const base = $derived(`/api/drawings/${encodeURIComponent(drawingId)}/signal-paths`);
  const choices = $derived(g ? endpoints(g) : []);
  const byId = $derived(new Map((g?.nodes ?? []).map((n) => [n.id, n])));
  const label = (id: string) => choices.find((e) => e.id === id)?.label ?? (info.get(id)?.name || byId.get(id)?.name || id);
  const questions = $derived<Question[]>(net ? questionsOf(net.rows) : []);
  const noFlow = $derived((net?.rows ?? []).filter((r) => r.role === 'pipe' && !r.flows.length));
  const taken = $derived((net?.rows ?? []).filter((r) => r.flows.some((f) => info.get(r.id)?.flows?.includes(f.part))));
  const missingEnds = $derived(endIds.map((e, b) => ({ e, b })).filter(({ b }) => !cands[b]?.length));
  const complete = $derived(!!net && endIds.length > 0 && !missingEnds.length);
  /** Elementer, AI-forslag kan udfylde: kun dem med ét spørgsmål (en flervejs-ventil har ét pr. vej). */
  const askedOnce = $derived(questions.filter((q) => questions.filter((x) => x.element === q.element).length === 1));

  $effect(() => { void drawingId; load(); });
  onDestroy(() => { clearTimeout(revTimer); highlight([], []); });

  // Flytter man et rør eller et symbol, mens guiden er åben, er grafen (og markeringen i tegningen) forældet: regn vejen forfra.
  // Samlet over et kort øjeblik (flere ændringer i træk), og kun hvis tegningens geometri faktisk er ændret.
  let revTimer: ReturnType<typeof setTimeout> | undefined;
  let seenKey = '';
  $effect(() => {
    void rev;
    untrack(() => {
      if (!editing) return;
      clearTimeout(revTimer);
      revTimer = setTimeout(() => {
        const fresh = graph();
        if (!fresh || !editing) return;
        const key = graphKey(fresh);
        if (key === seenKey) return;
        seenKey = key;
        g = fresh;
        recompute(null, true);
      }, 300);
    });
  });

  // ---------------------------------------------------------------- tegningen: grene i hver sin farve, retning som animation
  function show(): void {
    const lines: { pts: Pt[]; color: string; flow: number }[] = [];
    const boxes: { id: string; color: string }[] = [];
    if (!net) {
      highlight([], [start, ...endIds].filter(Boolean).map((id, i) => ({ id, color: i ? branchColor(i - 1) : '#455a64' })), focusId ? [focusId] : []);
      return;
    }
    for (const r of net.rows) {
      const n = byId.get(r.id);
      const color = r.branches.length > 1 ? SHARED : branchColor(r.branches[0] ?? 0);
      const parts = r.flows.map((f) => ({ f, l: n?.lines.find((l) => l.part === f.part) })).filter((x) => x.l !== undefined);
      if (parts.length) for (const { f, l } of parts) lines.push({ pts: l!.pts ?? [l!.a, l!.b], color, flow: f.reverse ? -1 : 1 });
      else boxes.push({ id: r.id, color });
    }
    highlight(lines, boxes, focusId ? [focusId] : []);
  }
  $effect(() => { void focusId; void net; untrack(show); });

  async function load(): Promise<void> {
    try {
      paths = await get<Saved[]>(base);
    } catch (e) {
      error = (e as Error).message;
    }
  }

  // ---------------------------------------------------------------- beregning (hver ændring beregner forfra, med det samme)
  const sig = (p: Step[] | undefined) => p?.map((s) => s.id).sort().join('>') ?? '';
  let wantSig: string[] = [];     // den vej, brugeren selv har valgt pr. gren — kommer tilbage, når tegningen igen tillader den

  /** Find vejene (en pr. slutpunkt) og vælg forslag: det, der var valgt, ellers det, der ligner `prefer`, ellers det korteste. */
  function recompute(prefer: (string[] | null)[] | null = null, fromDrawing = false): void {
    if (!g || !start || !endIds.length) {
      cands = [];
      picks = [];
      net = null;
      return;
    }
    // Efter en ændring i tegningen (flyt/fortryd) søges det, brugeren valgte — ikke det, der blev valgt, da vejen en kort stund var brudt
    const keep = fromDrawing ? wantSig.slice() : picks.map((i, b) => sig(cands[b]?.[i]));
    cands = endIds.map((e, b) => (e && e !== start ? findPaths(g!, start, e, 3, TOL, { defs, forced: forced[b] ?? {} }) : []));
    picks = cands.map((c, b) => {
      const want = prefer?.[b]?.slice().sort().join('>') ?? keep[b];
      const i = want ? c.findIndex((x) => sig(x) === want) : -1;
      return i >= 0 ? i : 0;
    });
    if (!fromDrawing) wantSig = picks.map((i, b) => sig(cands[b]?.[i]));
    refresh();
  }

  function refresh(): void {
    if (!g) return;
    const chosen = cands.map((c, b) => c[picks[b]] ?? []);
    net = chosen.some((p) => p.length) ? describeNet(g, chosen, defs) : null;
    void loadInfo();
  }

  async function loadInfo(): Promise<void> {
    if (!net) {
      answers = [];
      return;
    }
    const mine = net;
    try {
      const r = await post<{ elements: ElInfo[]; tags: TagInfo[] }>(`${base}/info`, { elements: mine.rows.map((x) => x.id) });
      if (mine !== net) return;     // en nyere beregning er overtaget
      info = new Map(r.elements.map((e) => [e.element, e]));
      allTags = r.tags.slice().sort((a, b) => a.name.localeCompare(b.name, 'da'));
      const old = new Map(answers.map((a) => [a.key, a]));
      answers = questionsOf(mine.rows).map((q): QAnswer => {
        const o = old.get(q.key);
        if (o) return { ...o, branches: q.branches };
        const s = saved.find((c) => c.element === q.element && sameSet(c.branches ?? mine.rows.find((x) => x.id === q.element)?.branches ?? [0], q.branches));
        const a = s ? answerFrom(s) : suggestAnswer(q.element, info.get(q.element)?.tags ?? []);
        return { ...a, key: q.key, branches: q.branches };
      });
    } catch (e) {
      error = (e as Error).message;
    }
  }
  const sameSet = (a: number[], b: number[]) => a.length === b.length && a.every((x) => b.includes(x));

  function choose(b: number, i: number): void {
    picks = picks.map((p, k) => (k === b ? i : p));
    wantSig[b] = sig(cands[b]?.[i]);
    refresh();
  }

  /** En 3-vejsventils vej for en gren: vejen beregnes forfra, så tegningen viser den nye vej. */
  function setWay(b: number, id: string, key: string): void {
    const f = { ...(forced[b] ?? {}) };
    if (key) f[id] = key;
    else delete f[id];
    forced = { ...forced, [b]: f };
    recompute();
  }

  // ---------------------------------------------------------------- start og slutpunkter (klik i tegningen)
  type Pick = 'start' | number | 'add' | null;
  let picking = $state<Pick>(null);
  let pickNote = $state('');
  let pickBase = '';
  function startPick(what: Pick): void {
    error = '';
    picking = what;
    select?.([]);        // markeringen fjernes, så et klik på netop det symbol, der var valgt, også tæller som et valg
    pickBase = '';
    if (what === 'start') {
      start = '';
      endIds = [];
      forced = {};
      recompute();
      pickNote = 'Klik på startsymbolet i tegningen …';
    } else pickNote = what === 'add' ? 'Klik på det nye slutpunkt i tegningen …' : 'Klik på slutsymbolet i tegningen …';
  }
  function stopPick(): void {
    picking = null;
    pickNote = '';
  }
  $effect(() => {
    const sel = selected;
    const key = sel.join(',');
    untrack(() => {
      if (!sel.length || key === pickBase) return;
      pickBase = key;
      if (picking === null) {      // ikke i gang med at vælge (OBS: 0 = det første slutpunkt er i gang): et klik på et element på vejen vælger dets række
        const hit = sel.length === 1 ? net?.rows.find((r) => r.id === sel[0]) : undefined;
        if (hit) {
          activeRow = hit.id;
          document.getElementById(`sp-row-${hit.id}`)?.scrollIntoView({ block: 'nearest' });
        }
        return;
      }
      const r = pickNext(picking === 'start' ? 'start' : 'end', sel, new Set(choices.map((e) => e.id)), start);
      if (r.error) {
        pickNote = r.error;
        return;
      }
      if (picking === 'start') {
        start = r.id!;
        picking = 0;
        pickNote = `Start: ${label(start)} — klik nu på slutsymbolet …`;
        highlight([], [{ id: start, color: '#455a64' }]);
        return;
      }
      if (endIds.includes(r.id!)) {
        pickNote = `${label(r.id!)} er allerede et slutpunkt`;
        return;
      }
      const at = picking;
      if (at === 'add' || (typeof at === 'number' && at >= endIds.length)) endIds = [...endIds, r.id!];
      else endIds = endIds.map((e, i) => (i === at ? r.id! : e));
      stopPick();
      forced = {};
      recompute();
    });
  });

  function setEnd(i: number, id: string): void {
    endIds = id ? endIds.map((e, k) => (k === i ? id : e)) : endIds.filter((_, k) => k !== i);
    forced = {};
    recompute();
  }
  function removeEnd(i: number): void {
    endIds = endIds.filter((_, k) => k !== i);
    forced = {};
    recompute();
  }
  function addEnd(id: string): void {
    if (!id || endIds.includes(id) || id === start) return;
    endIds = [...endIds, id];
    recompute();
  }
  function swap(): void {
    if (endIds.length !== 1) return;
    [start, endIds[0]] = [endIds[0], start];
    forced = {};
    recompute();
  }
  function setStart(id: string): void {
    start = id;
    forced = {};
    recompute();
  }
  function fromSelection(): string | null {
    const id = selected.find((s) => choices.some((e) => e.id === s));
    if (!id) error = 'Vælg et symbol i tegningen først (ikke et rør)';
    else error = '';
    return id ?? null;
  }

  // ---------------------------------------------------------------- start/ret en vej
  async function begin(p: Saved | null): Promise<void> {
    error = '';
    if (!(await ensureSaved())) return;
    g = graph();
    if (!g) {
      error = 'Tegningen er ikke klar endnu';
      return;
    }
    try {
      defs = mergeDefs(await get<FlowDefs>('/api/symbol-flow'));
    } catch {
      defs = mergeDefs(null);      // uden rettede definitioner bruges standarderne
    }
    editing = { id: p?.id ?? null };
    seenKey = graphKey(g);
    name = p?.name ?? '';
    light = p?.style.light ?? '#8fc8ea';
    speed = p?.style.speed ?? 40;
    start = p?.start ?? '';
    endIds = p ? (p.ends?.length ? p.ends : [p.end]) : [];
    forced = Object.fromEntries(Object.entries(p?.ui?.forced ?? {}).map(([k, v]) => [Number(k), v]));
    picks = [];
    cands = [];
    net = null;
    answers = [];
    saved = p?.conditions ?? [];
    locked = false;
    activeRow = '';
    ai = { text: '', thinking: false, start: 0, secs: 0, note: '', set: new Set(), unfilled: [] };
    if (p) {
      // forslagene, der ligner den gemte vej, vælges igen (elementerne pr. gren)
      const want = endIds.map((_, b) => p.elements.filter((e) => (e.branches ?? [0]).includes(b)).map((e) => e.element));
      recompute(want);
      locked = !!net && !missingEnds.length;
    }
  }

  // ---------------------------------------------------------------- "Forklar med egne ord" (v4.3.0)
  async function suggest(): Promise<void> {
    error = '';
    if (!ai.text.trim() || !askedOnce.length) return;
    ai = { ...ai, thinking: true, start: Date.now(), secs: 0, note: 'Hjælperen læser vejen og din beskrivelse …' };
    thinkCtl = new AbortController();
    try {
      await postStream<SuggestEvent>(`${base}/suggest`, {
        text: ai.text.trim(), questions: askedOnce.map((q) => ({ element: q.element, role: q.role })),
      }, (ev) => {
        if (ev.type === 'queued') ai.note = `I kø — ${ev.waiting} foran …`;
        else if (ev.type === 'error') error = ev.message;
        else if (ev.type === 'done') {
          const got = new Map(ev.suggestions.map((a) => [a.element, a]));
          answers = answers.map((a) => (got.has(a.element) && questions.filter((q) => q.element === a.element).length === 1 ? { ...got.get(a.element)!, key: a.key, branches: a.branches } : a));
          ai.set = new Set(got.keys());
          ai.unfilled = ev.unfilled;
          ai.note = `Udfyldt på ${Math.round(ev.ms / 1000)} s — tjek forslagene, før du gemmer.`;
        }
      }, thinkCtl.signal);
    } catch (e) {
      if ((e as Error).name !== 'AbortError') error = (e as Error).message;
      else ai.note = 'Stoppet.';
    } finally {
      ai.thinking = false;
      thinkCtl = null;
    }
  }

  const tagOf = (n: string) => allTags.find((t) => t.name === n);

  async function save(replace = false): Promise<void> {
    error = '';
    if (!net || !complete) {
      error = 'Der er ikke fundet en vej til alle slutpunkter';
      return;
    }
    const conditions: (Condition & { branches: number[] })[] = [];
    const errors: string[] = [];
    for (const a of answers) {
      const r = conditionsFrom([a], allTags);
      errors.push(...r.errors);
      if (r.conditions[0]) conditions.push({ ...r.conditions[0], branches: a.branches });
    }
    if (errors.length) {
      error = errors.join(' · ');
      return;
    }
    if (!name.trim()) {
      error = 'Giv signalvejen et navn';
      return;
    }
    const body = {
      name: name.trim(), start, end: endIds[0], ends: endIds.slice(1), replace, conditions,
      elements: net.rows.map((r) => ({ element: r.id, flows: r.flows, branches: r.branches })),
      style: { light, speed, dash: 12 }, ui: { forced, picks },
    };
    busy = true;
    try {
      const id = editing?.id;
      if (id) await put(`${base}/${id}`, body);
      else await post(base, body);
      onchanged?.(`Signalvejen "${body.name}" er gemt — ${net.rows.filter((r) => r.flows.length).length} dele har fået løbelys.`);
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
    stopPick();
    highlight([], []);
  }

  // ---------------------------------------------------------------- visning af vejen pr. gren
  /** Elementerne på en gren i rækkefølge: symboler (ikke rør), og hvor mange rør der ligger imellem. */
  function steps(b: number): { id: string; name: string; type: string; role: string; pipes: number }[] {
    const p = cands[b]?.[picks[b]];
    if (!p) return [];
    const order = net?.flipped[b] ? p.slice().reverse() : p;
    const out: { id: string; name: string; type: string; role: string; pipes: number }[] = [];
    let pipes = 0;
    for (const s of order) {
      const r = net?.rows.find((x) => x.id === s.id);
      if (!r) continue;
      if (r.role === 'pipe') {
        pipes++;
        continue;
      }
      out.push({ id: r.id, name: r.name || r.id, type: r.type, role: r.role, pipes });
      pipes = 0;
    }
    return out;
  }
  const ROLE_TXT: Record<string, string> = { valve: 'ventil', threeway: '3-vejsventil', pump: 'pumpe', switch: 'kontakt', check: 'kontraventil', unit: '' };
  const hasWays = (type: string) => waysOf(defs[type]).length > 0;
  /** Hvilken vej en gren bruger gennem et flervejs-element lige nu. */
  const usedWay = (r: NetRow | undefined, b: number) => r?.uses.find((u) => u.branch === b)?.way ?? '';
  const summaryOf = (b: number, i: number): string => {
    const p = cands[b]?.[i];
    if (!p || !g) return '';
    const named = describeNet(g, [p], defs).rows.filter((r, k, all) => k === 0 || k === all.length - 1 || (r.role !== 'pipe' && r.name));
    return `${named.map((r) => r.name || r.id).join(' → ')} (${p.length} dele)`;
  };
  const asked = $derived(answers);
  const rowOf = (id: string) => net?.rows.find((r) => r.id === id);
</script>

{#if error}<p class="error small">{error}</p>{/if}

{#if !editing}
  <p class="small muted">En signalvej sætter løbelys på alle rør mellem symboler på én gang — styret af ventiler og pumper undervejs. Vejen kan dele sig i flere grene.</p>
  <div class="row"><button class="primary" onclick={() => begin(null)} disabled={!ready || busy}>Ny signalvej …</button></div>
  {#each paths as p (p.id)}
    <div class="item">
      <div class="grow">
        <strong>{p.name}</strong>
        <div class="small muted">{p.elements.length} dele · {(p.ends?.length ?? 1) > 1 ? `${p.ends.length} grene · ` : ''}{p.conditions.length} betingelser</div>
        {#if p.missing.length}<div class="small warn">{p.missing.length} dele findes ikke længere — ret vejen</div>{/if}
      </div>
      <button class="small" onclick={() => begin(p)} disabled={!ready || busy}>Ret</button>
      <button class="small" onclick={() => remove(p)} disabled={busy} aria-label="Slet {p.name}">Slet</button>
    </div>
  {/each}
{:else}
  <div class="step">
    <h4>1. Start og slutpunkter</h4>
    <div class="row">
      {#if picking !== null}
        <button onclick={stopPick}>Afbryd valg</button>
      {:else}
        <button class="primary" onclick={() => startPick('start')} disabled={busy} title="Klik på startsymbolet og derefter slutsymbolet i tegningen">Vælg på tegningen</button>
        {#if start && endIds.length}<button onclick={() => startPick('add')} disabled={busy || endIds.length >= MAX_ENDS} title="Vejen deler sig: tilføj endnu et slutpunkt">+ Slutpunkt</button>{/if}
      {/if}
    </div>
    {#if pickNote}<p class="small pick" role="status">{pickNote}</p>{/if}
    <label class="field">Start
      <span class="row nowrap">
        <select value={start} onchange={(e) => setStart(e.currentTarget.value)}><option value="">— vælg —</option>{#each choices as e (e.id)}<option value={e.id}>{e.label}</option>{/each}</select>
        <button class="small" onclick={() => { const id = fromSelection(); if (id) setStart(id); }} title="Brug symbolet, der er valgt i tegningen">← valgt</button>
      </span>
    </label>
    {#each endIds as e, i (i)}
      <label class="field"><span><span class="dot" style="background:{branchColor(i)}"></span>{endIds.length > 1 ? `Slut ${i + 1}` : 'Slut'}</span>
        <span class="row nowrap">
          <select value={e} onchange={(ev) => setEnd(i, ev.currentTarget.value)}><option value="">— fjern —</option>{#each choices as c (c.id)}<option value={c.id}>{c.label}</option>{/each}</select>
          <button class="small" onclick={() => { const id = fromSelection(); if (id) setEnd(i, id); }} title="Brug symbolet, der er valgt i tegningen">← valgt</button>
          {#if endIds.length > 1}<button class="small" onclick={() => removeEnd(i)} aria-label="Fjern slutpunkt {i + 1}" title="Fjern slutpunktet">✕</button>{/if}
        </span>
      </label>
    {/each}
    {#if endIds.length && endIds.length < MAX_ENDS}
      <label class="field">Flere slutpunkter (vejen deler sig)
        <select value="" onchange={(e) => { addEnd(e.currentTarget.value); e.currentTarget.value = ''; }} aria-label="Tilføj slutpunkt">
          <option value="">+ tilføj et slutpunkt …</option>{#each choices.filter((c) => c.id !== start && !endIds.includes(c.id)) as c (c.id)}<option value={c.id}>{c.label}</option>{/each}
        </select>
      </label>
    {/if}
    {#if !endIds.length && start}
      <label class="field">Slut
        <span class="row nowrap">
          <select value="" onchange={(e) => addEnd(e.currentTarget.value)} aria-label="Slut"><option value="">— vælg —</option>{#each choices.filter((c) => c.id !== start) as c (c.id)}<option value={c.id}>{c.label}</option>{/each}</select>
          <button class="small" onclick={() => { const id = fromSelection(); if (id) addEnd(id); }} title="Brug symbolet, der er valgt i tegningen">← valgt</button>
        </span>
      </label>
      {#if picking === null}<div class="row"><button onclick={() => startPick(0)} disabled={busy} title="Klik på slutsymbolet i tegningen">Vælg slut på tegningen</button></div>{/if}
    {/if}
    {#if start && endIds.length === 1}<div class="row"><button class="small" onclick={swap} title="Byt start og slut (retningen følger i øvrigt pumpen)">⇄ Byt om</button></div>{/if}
  </div>

  {#if start && endIds.length}
    <div class="step">
      <h4>2. Vejen {#if locked}<button class="small" onclick={() => (locked = false)}>Ret vejen</button>{/if}</h4>
      {#if missingEnds.length}
        {#each missingEnds as m (m.b)}
          <p class="small warn"><span class="dot" style="background:{branchColor(m.b)}"></span>Der er ingen sammenhængende vej til {label(m.e)}{(forced[m.b] && Object.keys(forced[m.b]).length) ? ' med de valgte veje gennem ventilerne — skift en ventils vej eller vælg "automatisk"' : ''}.
            Tjek ellers at rørene sidder fast i symbolerne (grønne ender, når røret er valgt), og at T-stykker er sat ind, hvor rør mødes.</p>
        {/each}
      {/if}
      {#each endIds as e, b (b)}
        {#if cands[b]?.length}
          <div class="branch" style="border-left-color:{branchColor(b)}">
            {#if endIds.length > 1}<div class="small"><strong>Gren {b + 1}</strong> → {label(e)}</div>{/if}
            {#if net?.flipped[b]}<div class="small ok">↻ Vejen er vendt, så flowet følger {net.by[b].join(', ')} (ind → ud).</div>
            {:else if net?.by[b]?.length}<div class="small ok">Flowet følger {net.by[b].join(', ')} (ind → ud).</div>{/if}
            {#if !locked}
              {#each cands[b] as _, i (i)}
                <!-- forslag, der nævner de samme symboler (de ligger bare i andre rørstykker), vises kun én gang -->
                {#if cands[b].findIndex((_x, k) => summaryOf(b, k) === summaryOf(b, i)) === i}
                  <label class="opt"><input type="radio" name="sp-vej-{b}" checked={summaryOf(b, picks[b]) === summaryOf(b, i)} onchange={() => choose(b, i)} />{summaryOf(b, i)}</label>
                {/if}
              {/each}
            {/if}
            <ol class="steps">
              {#each steps(b) as s (s.id)}
                {@const r = rowOf(s.id)}
                <li id={b === 0 ? `sp-row-${s.id}` : undefined} class:active={activeRow === s.id} onmouseenter={() => (focusId = s.id)} onmouseleave={() => (focusId = '')}>
                  {#if s.pipes}<span class="pipes small muted">{s.pipes} rør</span>{/if}
                  <button class="link" onclick={() => { activeRow = s.id; select?.([s.id]); }} title="Vælg i tegningen">{s.name}</button>
                  {#if ROLE_TXT[s.role]}<span class="small muted">{ROLE_TXT[s.role]}</span>{/if}
                  {#if hasWays(s.type) && s.id !== start && !endIds.includes(s.id)}
                    <select class="way" value={forced[b]?.[s.id] ?? ''} onchange={(ev) => setWay(b, s.id, ev.currentTarget.value)} aria-label="Vej gennem {s.name}" disabled={locked}>
                      <option value="">automatisk{usedWay(r, b) ? ` (${wayLabel(parseWay(usedWay(r, b))!)})` : ''}</option>
                      {#each waysOf(defs[s.type]) as w (wayKey(w))}<option value={wayKey(w)}>{wayLabel(w)}</option>{/each}
                    </select>
                  {/if}
                </li>
              {/each}
            </ol>
          </div>
        {/if}
      {/each}
      {#if net?.warnings.length}{#each net.warnings as w (w)}<p class="small warn">⚠ {w}</p>{/each}{/if}
      {#if complete}
        <p class="small muted">Vejen er markeret i tegningen — {endIds.length > 1 ? 'hver gren i sin farve, ' : ''}de hvide streger viser, hvilken vej flowet løber. Peg på en række for at se symbolet i tegningen.</p>
        {#if noFlow.length}<p class="small warn">Kan ikke få løbelys: {noFlow.map((r) => r.name || r.id).join(', ')}.</p>{/if}
        {#if taken.length}<p class="small warn">Har allerede løbelys (erstattes, hvis du bekræfter): {taken.map((r) => r.name || r.id).join(', ')}.</p>{/if}
        {#if !locked}<div class="row"><button class="primary" onclick={() => (locked = true)}>Brug denne vej →</button></div>{/if}
      {/if}
    </div>
  {/if}

  {#if complete && locked}
    <div class="step">
      <h4>3. Hvornår går der flow?</h4>
      {#if !questions.length}<p class="small muted">Ingen ventiler eller pumper på vejen — løbelyset kører altid.</p>{/if}
      {#if askedOnce.length && assist.available && assist.canAsk}
        <div class="explain">
          <label class="field">Forklar med egne ord <span class="small muted">(hjælperen udfylder forslag)</span>
            <textarea bind:value={ai.text} rows="2" maxlength="400" disabled={ai.thinking}
                      placeholder="fx når pumpe 5 kører og MVS1 står over 50 %"></textarea>
          </label>
          <div class="row">
            {#if ai.thinking}
              <button onclick={() => thinkCtl?.abort()}>Stop</button>
              <span class="small muted">{ai.note} {ai.secs} s</span>
            {:else}
              <button onclick={suggest} disabled={!ai.text.trim() || busy}>Udfyld med hjælperen</button>
              {#if ai.note}<span class="small muted">{ai.note}</span>{:else}<span class="small muted">tager typisk 1–3 min</span>{/if}
            {/if}
          </div>
          {#if ai.unfilled.length && !ai.thinking}
            <p class="small warn">Ikke udfyldt af hjælperen: {ai.unfilled.map((id) => rowOf(id)?.name || id).join(', ')} — vælg selv.</p>
          {/if}
        </div>
      {/if}
      {#each asked as a (a.key)}
        {@const r = rowOf(a.element)}
        {@const q = questions.find((x) => x.key === a.key)}
        {@const own = info.get(a.element)?.tags ?? []}
        {@const t = tagOf(a.src)}
        <div class="q" onmouseenter={() => (focusId = a.element)} onmouseleave={() => (focusId = '')} role="group" aria-label="Betingelse for {r?.name || a.element}">
          <div><strong>{r?.name || a.element}</strong>
            {#if q?.way}<span class="chip">{wayLabel(parseWay(q.way)!)}</span>{/if}
            {#each a.branches as b (b)}{#if endIds.length > 1}<span class="dot" style="background:{branchColor(b)}" title="Gren {b + 1}"></span>{/if}{/each}
            <span class="small muted">{q ? (q.way ? `Hvornår leder ventilen ${wayLabel(parseWay(q.way)!)}?` : QUESTION[q.role]) : ''}</span>
            {#if ai.set.has(a.element)}<span class="ai" title="Udfyldt af hjælperen — tjek det">forslag</span>{/if}</div>
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
      {#if questions.length}<p class="small muted">{endIds.length > 1 ? 'Inden for en gren skal alle betingelser være opfyldt (OG); et fælles stykke lyser, når mindst én gren er aktiv.' : 'Alle betingelser skal være opfyldt (OG).'}</p>{/if}
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

<svelte:window onkeydown={(e) => { if (e.key === 'Escape' && picking !== null) stopPick(); }} />

<style>
  .pick { background: #fff4e0; border: 1px solid #ff8f00; border-radius: var(--radius); padding: .3rem .45rem; }
  .item { display: flex; align-items: center; gap: .4rem; padding: .35rem 0; border-top: 1px solid var(--line); }
  .grow { flex: 1; min-width: 0; }
  .step { border-top: 1px solid var(--line); padding: .4rem 0; }
  .step h4 { margin: .1rem 0 .35rem; font-size: .9rem; display: flex; align-items: center; gap: .5rem; }
  .field { display: flex; flex-direction: column; gap: .15rem; font-size: .85rem; margin-bottom: .35rem; }
  .field select, .field input:not([type='color']) { min-width: 0; }
  .nowrap { flex-wrap: nowrap; gap: .3rem; display: flex; align-items: center; }
  .nowrap select { flex: 1; min-width: 0; }
  .opt { display: flex; gap: .35rem; align-items: flex-start; font-size: .85rem; margin: .2rem 0; }
  .q { display: flex; flex-direction: column; gap: .25rem; padding: .35rem 0; border-bottom: 1px dashed var(--line); }
  .q input[type='number'] { width: 6rem; }
  .warn { color: var(--warn); }
  .ok { color: #2e7d32; }
  .explain { background: #fff; border: 1px solid var(--line); border-radius: var(--radius); padding: .4rem; margin-bottom: .4rem; }
  .explain textarea { width: 100%; box-sizing: border-box; resize: vertical; font: inherit; }
  .ai { font-size: .7rem; background: var(--accent); color: #fff; border-radius: 3px; padding: 0 .3rem; margin-left: .3rem; }
  .dot { display: inline-block; width: .7rem; height: .7rem; border-radius: 50%; margin-right: .3rem; vertical-align: middle; }
  .branch { border-left: 4px solid var(--line); padding: .15rem 0 .15rem .5rem; margin: .35rem 0; }
  .steps { margin: .25rem 0; padding-left: 1.1rem; font-size: .85rem; }
  .steps li { padding: .12rem .2rem; border-radius: 3px; }
  .steps li:hover, .steps li.active { background: #e3f2fd; }
  .pipes { display: block; margin-left: -.9rem; font-size: .72rem; }
  .link { background: none; border: none; padding: 0; color: var(--accent); cursor: pointer; text-decoration: underline; font: inherit; }
  .way { font-size: .8rem; max-width: 100%; margin-left: .3rem; }
  .chip { font-size: .72rem; background: #eceff1; border: 1px solid var(--line); border-radius: 999px; padding: 0 .4rem; margin: 0 .2rem; }
</style>
