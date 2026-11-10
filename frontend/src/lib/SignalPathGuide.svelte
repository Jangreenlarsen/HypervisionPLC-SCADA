<script lang="ts">
  // Signalveje i Tegn (v4.2.0; v4.13.0: grene, ventilvalg, ind/ud fra symbolerne og en interaktiv editor — PLAN.md › Signalveje 2).
  // Arbejdsgang: 1) vælg start og slutpunkter (klik i tegningen), 2) vejen beregnes med det samme og vises i tegningen — skift en
  // 3-vejsventils vej, og vejen beregnes forfra — og låses med "Brug denne vej", 3) svar på hvornår der går flow, 4) navn og udseende.
  // Grafen og vejen beregnes her ud fra tegningen (signalPath.ts); backend validerer og gemmer opsætningerne samlet.
  import { onDestroy, untrack } from 'svelte';
  import { del, get, post, put } from './api';
  import { ask as askUser } from './ask';
  import { postStream } from './assist';
  import SpConditions, { type AiState, type QAnswer } from './SpConditions.svelte';
  import SpLook from './SpLook.svelte';
  import SpSaved from './SpSaved.svelte';
  import SpStart, { type PickMode } from './SpStart.svelte';
  import {
    MAX_ENDS, QUESTION, TOL, answerFrom, conditionsFrom, describeNet, endpoints, findPaths, findViaPath, graphKey, passable, pickNext,
    questionsOf, suggestAnswer,
    type Answer, type Condition, type Graph, type Net, type NetRow, type Pt, type Question, type Step, type TagInfo,
  } from './signalPath';
  import { mergeDefs, parseWay, wayKey, wayLabel, waysOf, type FlowDefs } from './symbolFlow';
  import {
    GROUPS, GROUP_LABEL, TYPE_LABEL, WAYS_PART, WHOLE, animsFor, anyChosen, defaultLook, groupOf, restoreLook, type Look, type LookGroup,
  } from './pathLook';

  interface Saved {
    id: number; name: string; start: string; end: string; ends: string[]; ui: { forced?: Record<string, Record<string, string>>; picks?: number[] };
    elements: { element: string; flows: { part: string; reverse: boolean }[]; branches?: number[] }[];
    conditions: (Condition & { branches?: number[] })[]; style: { light: string; speed: number; dash: number }; missing: string[]; updated_by: string;
  }
  interface ElInfo {
    element: string; name?: string; type?: string; configured?: boolean; tags?: TagInfo[]; missing?: boolean;
    parts?: { id: string; pid: string; line: boolean; text: string }[];
  }

  let { drawingId, ready, rev = 0, selected, graph, highlight, select, ensureSaved, onchanged, oneditchange }: {
    drawingId: string;
    ready: boolean;
    rev?: number;           // tælles op, hver gang tegningen ændres (flyt, ret, fortryd): vejen regnes så forfra
    selected: string[];
    graph: () => Graph | null;
    highlight: (lines: { pts: Pt[]; color: string; flow: number }[], boxes: { id: string; color: string }[], focus?: string[]) => void;
    select?: (ids: string[]) => void;
    ensureSaved: () => Promise<boolean>;
    onchanged?: (text: string) => void;
    /** guiden er åben for en vej (ny eller Ret) — Tegn lægger den så i et vindue over tegningen (v5.2.0) */
    oneditchange?: (editing: boolean) => void;
  } = $props();

  const COLORS = ['#ff8f00', '#1e88e5', '#43a047', '#8e24aa'];       // en farve pr. gren i tegningen
  const SHARED = '#6d4c41';                                           // stykker, flere grene går igennem
  const branchColor = (b: number) => COLORS[b % COLORS.length];

  let paths = $state<Saved[]>([]);
  let error = $state('');
  let busy = $state(false);
  let editing = $state<{ id: number | null } | null>(null);
  $effect(() => { const on = editing !== null; untrack(() => oneditchange?.(on)); });
  let name = $state('');
  let start = $state('');
  let endIds = $state<string[]>([]);
  let light = $state('#8fc8ea');
  let speed = $state(40);
  let look = $state<Look>(defaultLook());     // hvilke animationer vejen lægger på hvilke slags elementer (v4.14.0)
  // Klik i tegningen (v4.15.0): "gå via"-punkter pr. gren (rør og symboler, vejen skal igennem), og hvilken gren et klik gælder
  let via = $state<Record<number, string[]>>({});
  let viaMissing = $state<Record<number, string[]>>({});
  let flips = $state<Record<number, boolean>>({});     // gren → brugeren har vendt flowets retning (v4.16.0)
  let activeBranch = $state(0);
  let clicking = $state(true);                  // et klik på et rør/symbol i tegningen ændrer vejen (så længe trin 2 er åbent)
  let clickNote = $state('');
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
  let ai = $state<AiState>({ text: '', thinking: false, start: 0, secs: 0, note: '', set: new Set<string>(), unfilled: [] });
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
  const missingEnds = $derived(endIds.map((e, b) => ({ e, b })).filter(({ b }) => !cands[b]?.length));
  const complete = $derived(!!net && endIds.length > 0 && !missingEnds.length);
  /** Elementer, AI-forslag kan udfylde: kun dem med ét spørgsmål (en flervejs-ventil har ét pr. vej). */
  /** Hvilke slags elementer der er på vejen (og hvor mange af hver), til udseende-trinnet. */
  const present = $derived(new Map<LookGroup, number>(GROUPS.map((g) => [g, (net?.rows ?? []).filter((r) => groupOf(r.role) === g).length] as [LookGroup, number]).filter(([, n]) => n > 0)));
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
    const viaBoxes = Object.values(via).flat().map((id) => ({ id, color: '#6a1b9a' }));      // via-punkter: lilla
    if (!net) {
      highlight([], [...[start, ...endIds].filter(Boolean).map((id, i) => ({ id, color: i ? branchColor(i - 1) : '#455a64' })), ...viaBoxes],
        focusId ? [focusId] : []);
      return;
    }
    for (const r of net.rows) {
      const n = byId.get(r.id);
      const color = r.branches.length > 1 ? SHARED : branchColor(r.branches[0] ?? 0);
      const parts = r.flows.map((f) => ({ f, l: n?.lines.find((l) => l.part === f.part) })).filter((x) => x.l !== undefined);
      if (parts.length) for (const { f, l } of parts) lines.push({ pts: l!.pts ?? [l!.a, l!.b], color, flow: f.reverse ? -1 : 1 });
      else boxes.push({ id: r.id, color });
    }
    highlight(lines, [...boxes, ...viaBoxes], focusId ? [focusId] : []);
  }
  $effect(() => { void focusId; void net; void via; untrack(show); });

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
    // via-punkter, der ikke længere findes i tegningen, fjernes (meldes)
    const here = new Set(g.nodes.map((n) => n.id));
    const gone = Object.values(via).flat().filter((id) => !here.has(id));
    if (gone.length) {
      via = Object.fromEntries(Object.entries(via).map(([k, v]) => [k, v.filter((id) => here.has(id))]));
      clickNote = `${gone.map(label).join(', ')} findes ikke længere i tegningen og er fjernet fra vejen.`;
    }
    const missed: Record<number, string[]> = {};
    cands = endIds.map((e, b) => {
      if (!e || e === start) return [];
      const opts = { defs, forced: forced[b] ?? {} };
      if (via[b]?.length) {
        const r = findViaPath(g!, start, e, via[b], TOL, opts);
        missed[b] = r.missing;
        if (r.path) return [r.path];
      }
      return findPaths(g!, start, e, 3, TOL, opts);
    });
    viaMissing = missed;
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
    net = chosen.some((p) => p.length) ? describeNet(g, chosen, defs, endIds.map((_, b) => !!flips[b])) : null;
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
  let picking = $state<PickMode>(null);
  let pickNote = $state('');
  let pickBase = '';
  function startPick(what: PickMode): void {
    error = '';
    picking = what;
    select?.([]);        // markeringen fjernes, så et klik på netop det symbol, der var valgt, også tæller som et valg
    pickBase = '';
    if (what === 'start') {
      start = '';
      endIds = [];
      forced = {};
      via = {};
      flips = {};
      recompute();
      pickNote = 'Klik på startsymbolet i tegningen …';
    } else if (what === 'via') pickNote = 'Klik på et rør eller symbol, vejen skal gå igennem …';
    else pickNote = what === 'add' ? 'Klik på det nye slutpunkt i tegningen …' : 'Klik på slutsymbolet i tegningen …';
  }
  function stopPick(): void {
    picking = null;
    pickNote = '';
  }
  $effect(() => {
    const sel = selected;
    const key = sel.join(',');
    untrack(() => {
      if (!sel.length) {
        pickBase = '';
        return;
      }
      if (key === pickBase) return;
      pickBase = key;
      if (picking === null) {      // ikke i gang med at vælge (OBS: 0 = det første slutpunkt er i gang): et klik på et element på vejen vælger dets række
        if (clicking && !locked && sel.length === 1 && clickElement(sel[0])) return;
        const hit = sel.length === 1 ? net?.rows.find((r) => r.id === sel[0]) : undefined;
        if (hit) {
          activeRow = hit.id;
          document.getElementById(`sp-row-${hit.id}`)?.scrollIntoView?.({ block: 'nearest' });
        }
        return;
      }
      if (picking === 'via') {
        const n = sel.length === 1 ? byId.get(sel[0]) : undefined;
        const why = viaProblem(n);
        if (why) pickNote = why;
        else {
          addVia(n!.id);
          stopPick();
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
      via = {};
      flips = {};
      recompute();
    });
  });

  // ---------------------------------------------------------------- gå via og klik i tegningen (v4.15.0)
  /** Hvorfor et element ikke kan bruges som via-punkt (tekst), eller null. */
  function viaProblem(n: Graph['nodes'][number] | undefined): string | null {
    if (!n) return 'Klik på et rør eller symbol i tegningen';
    if (n.id === start || endIds.includes(n.id)) return `${label(n.id)} er allerede start eller slutpunkt`;
    if (!passable(n)) return 'Det valgte er en tekst eller en visning — klik på et rør eller et anlægssymbol';
    if (hasWays(n.type)) return `${label(n.id)} har flere veje — klik på den på vejen for at skifte vej`;
    return null;
  }
  const allVia = $derived(Object.entries(via).flatMap(([b, ids]) => ids.map((id) => ({ b: Number(b), id }))));

  function addVia(id: string, b = activeBranch < endIds.length ? activeBranch : 0): void {
    via = { ...via, [b]: [...(via[b] ?? []), id].filter((x, i, a) => a.indexOf(x) === i) };
    recompute();
    if (viaMissing[b]?.includes(id)) {
      clickNote = `${label(id)} kan ikke bruges: der er ingen vej gennem det uden at vende om (en blindgyde?).`;
      via = { ...via, [b]: via[b].filter((x) => x !== id) };
      recompute();
    } else clickNote = `${label(id)} er tilføjet: vejen går nu igennem det. Klik på det igen for at fjerne det.`;
  }
  /** Et via-punkt valgt i rullemenuen. */
  function viaFromList(id: string): void {
    const why = viaProblem(byId.get(id));
    if (why) error = why;
    else {
      error = '';
      addVia(id);
    }
  }
  /** Brug det, der er valgt i tegningen, som via-punkt. */
  function viaFromSelection(): void {
    const id = selected.find((x) => byId.has(x));
    const why = viaProblem(id ? byId.get(id) : undefined);
    if (why || !id) error = why ?? 'Vælg et rør eller symbol i tegningen først';
    else {
      error = '';
      addVia(id);
    }
  }
  function removeVia(id: string): void {
    via = Object.fromEntries(Object.entries(via).map(([k, v]) => [k, v.filter((x) => x !== id)]));
    recompute();
    clickNote = `${label(id)} er fjernet fra vejen.`;
  }

  /** Et klik på et rør eller symbol i tegningen, mens trin 2 er åbent: skift en flervejs-ventils vej, tilføj/fjern et via-punkt. */
  function clickElement(id: string): boolean {
    const n = byId.get(id);
    if (!n || id === start || endIds.includes(id) || !endIds.length) return false;
    const done = (note: string): true => {
      clickNote = note;
      select?.([]);          // markeringen fjernes, så det samme element kan klikkes igen
      pickBase = '';
      return true;
    };
    const on = net?.rows.find((r) => r.id === id);
    // en 3-vejsventil på vejen — eller en, hvis valgte vej midlertidigt har ødelagt vejen: skift mellem automatisk og symbolets veje
    const forcedIn = Number(Object.keys(forced).find((k) => forced[Number(k)]?.[id] !== undefined));
    if (hasWays(n.type) && (on || !Number.isNaN(forcedIn))) {
      const b = on ? (on.branches.includes(activeBranch) ? activeBranch : on.branches[0]) : forcedIn;
      const options = ['', ...waysOf(defs[n.type]).map(wayKey)];
      const next = options[(options.indexOf(forced[b]?.[id] ?? '') + 1) % options.length];
      setWay(b, id, next);
      const used = rowOfNet(id)?.uses.find((u) => u.branch === b)?.way;
      return done(`${label(id)}: ${next ? wayLabel(parseWay(next)!) : `automatisk${used ? ` (${wayLabel(parseWay(used)!)})` : ''}`}${endIds.length > 1 ? ` — gren ${b + 1}` : ''}`);
    }
    const mine = Object.entries(via).find(([, ids]) => ids.includes(id));
    if (mine) {
      removeVia(id);
      return done(`${label(id)} er fjernet fra vejen.`);
    }
    if (on) return false;             // et almindeligt element på vejen: vælg dets række som før
    const why = viaProblem(n);
    if (why) return done(why);
    addVia(id);
    return done(clickNote);
  }
  /** Vend flowets retning på en gren (hvis symbolerne ikke giver den rigtige, eller ingen giver en). */
  function flipBranch(b: number): void {
    flips = { ...flips, [b]: !flips[b] };
    refresh();
  }
  const rowOfNet = (id: string) => net?.rows.find((r) => r.id === id);

  function setEnd(i: number, id: string): void {
    endIds = id ? endIds.map((e, k) => (k === i ? id : e)) : endIds.filter((_, k) => k !== i);
    forced = {};
    via = {};
    flips = {};
    recompute();
  }
  function removeEnd(i: number): void {
    endIds = endIds.filter((_, k) => k !== i);
    forced = {};
    via = {};
    flips = {};
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
    via = {};
    flips = {};
    recompute();
  }
  function setStart(id: string): void {
    start = id;
    forced = {};
    via = {};
    flips = {};
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
    look = restoreLook((p?.ui as { look?: unknown } | undefined)?.look);
    start = p?.start ?? '';
    endIds = p ? (p.ends?.length ? p.ends : [p.end]) : [];
    forced = Object.fromEntries(Object.entries(p?.ui?.forced ?? {}).map(([k, v]) => [Number(k), v]));
    via = Object.fromEntries(Object.entries((p?.ui as { via?: Record<string, string[]> } | undefined)?.via ?? {}).map(([k, v]) => [Number(k), v]));
    flips = Object.fromEntries(Object.entries((p?.ui as { flips?: Record<string, boolean> } | undefined)?.flips ?? {}).map(([k, v]) => [Number(k), !!v]));
    viaMissing = {};
    activeBranch = 0;
    clicking = true;
    clickNote = '';
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

  async function save(): Promise<void> {
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
    if (!anyChosen(look, new Set(present.keys()))) {
      error = 'Vælg mindst én animation under Udseende';
      return;
    }
    const body = {
      name: name.trim(), start, end: endIds[0], ends: endIds.slice(1), conditions,
      elements: net.rows.map((r) => {
        const x = animsFor(r, look, defs, info.get(r.id)?.parts ?? []);
        return { element: r.id, flows: x.flows, anims: x.anims, branches: r.branches };
      }),
      style: { light, speed, dash: 12 }, ui: { forced, picks, look, via, flips },
    };
    busy = true;
    try {
      const id = editing?.id;
      if (id) await put(`${base}/${id}`, body);
      else await post(base, body);
      const n = body.elements.filter((e) => e.flows.length || e.anims.length).length;
      onchanged?.(`Signalvejen "${body.name}" er gemt — ${n} dele har fået animationer.`);
      editing = null;
      highlight([], []);
      await load();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  async function remove(p: Saved): Promise<void> {
    if (!(await askUser(`Slet signalvejen "${p.name}"? Dens løbelys og animationer forsvinder; symbolernes egen opsætning røres ikke.`,
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
  const rowOf = (id: string) => net?.rows.find((r) => r.id === id);
</script>

{#if error}<p class="error small">{error}</p>{/if}

{#if !editing}
  <p class="small muted">En signalvej sætter løbelys på alle rør mellem symboler på én gang — styret af ventiler og pumper undervejs. Vejen kan dele sig i flere grene.</p>
  <div class="row"><button class="primary" onclick={() => begin(null)} disabled={!ready || busy}>Ny signalvej …</button></div>
  <SpSaved {paths} {ready} {busy} onedit={(p) => begin(p as Saved)} onremove={(p) => remove(p as Saved)} />
{:else}
  <div class="step">
    <h4>1. Start og slutpunkter</h4>
    <SpStart {choices} {start} {endIds} {picking} {pickNote} {busy} {branchColor} {label}
      via={allVia.map((v) => ({ ...v, missing: !!viaMissing[v.b]?.includes(v.id) }))}
      viaChoices={choices.filter((c) => c.id !== start && !endIds.includes(c.id) && !hasWays(byId.get(c.id)?.type ?? ''))}
      onpick={startPick} onstoppick={stopPick} onstart={setStart} onend={setEnd} onremoveend={removeEnd} onaddend={addEnd}
      onviapick={viaFromList} onviaselected={viaFromSelection} onremovevia={removeVia} onswap={swap} {fromSelection} />
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
      {#if !locked && start && endIds.length}
        {#if clicking}
          <p class="clickbar small" role="status">Klik på <strong>rør og symboler i tegningen</strong> for at ændre vejen: klik på et rør for at gå via det (klik igen fjerner det), og klik på en <strong>3-vejsventil</strong> for at skifte vej.
            <button class="small" onclick={() => (clicking = false)}>Færdig (Esc)</button></p>
        {:else}<div class="row"><button class="small" onclick={() => (clicking = true)}>Ret vejen i tegningen</button></div>{/if}
        {#if clickNote}<p class="small ok" role="status">{clickNote}</p>{/if}
      {/if}
      {#each endIds as e, b (b)}
        {#if cands[b]?.length}
          <div class="branch" class:activeb={endIds.length > 1 && activeBranch === b} style="border-left-color:{branchColor(b)}">
            {#if endIds.length > 1}<div class="small"><button class="link" onclick={() => (activeBranch = b)} title="Klik i tegningen gælder denne gren"><strong>Gren {b + 1}</strong></button> → {label(e)}{#if activeBranch === b && clicking && !locked} <span class="chip">klik gælder her</span>{/if}</div>{/if}
            {#if net?.manual[b]}<div class="small ok">⇄ Du har vendt flowets retning.</div>
            {:else if net?.flipped[b]}<div class="small ok">↻ Vejen er vendt, så flowet følger {net.by[b].join(', ')} (ind → ud).</div>
            {:else if net?.by[b]?.length}<div class="small ok">Flowet følger {net.by[b].join(', ')} (ind → ud).</div>{/if}
            {#if !locked}<div class="row"><button class="small" onclick={() => flipBranch(b)} title="Vend flowets retning på {endIds.length > 1 ? `gren ${b + 1}` : 'vejen'} (pilene i tegningen vender)">⇄ Vend flowet</button></div>{/if}
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
        {#if !locked}<div class="row"><button class="primary" onclick={() => (locked = true)}>Brug denne vej →</button></div>{/if}
      {/if}
    </div>
  {/if}

  {#if complete && locked}
    <div class="step">
      <h4>3. Hvornår går der flow?</h4>
      <SpConditions bind:answers bind:ai bind:focusId {questions} {askedOnce} rows={net?.rows ?? []} tagsOf={(id) => info.get(id)?.tags ?? []} {allTags}
        branchCount={endIds.length} {branchColor} {busy} onsuggest={suggest} onstop={() => thinkCtl?.abort()} />
    </div>

    <div class="step">
      <h4>4. Udseende — hvilke animationer?</h4>
      <SpLook bind:look bind:light bind:speed {present} rows={net?.rows ?? []} parts={(id) => info.get(id)?.parts ?? []} />
    </div>

    <div class="step">
      <h4>5. Navn og gem</h4>
      <label class="field">Navn <input bind:value={name} maxlength="60" placeholder="fx Kedel → radiatorer" /></label>
      <div class="row">
        <button class="primary" onclick={() => save()} disabled={busy || !name.trim()}>Gem signalvej</button>
        <button onclick={cancel} disabled={busy}>Annullér</button>
      </div>
    </div>
  {:else}
    <div class="row"><button onclick={cancel}>Annullér</button></div>
  {/if}
{/if}

<svelte:window onkeydown={(e) => { if (e.key === 'Escape') { if (picking !== null) stopPick(); else if (clicking && editing) clicking = false; } }} />

<style>
  .step { border-top: 1px solid var(--line); padding: .4rem 0; }
  .step h4 { margin: .1rem 0 .35rem; font-size: .9rem; display: flex; align-items: center; gap: .5rem; }
  .field { display: flex; flex-direction: column; gap: .15rem; font-size: .85rem; margin-bottom: .35rem; }
  .opt { display: flex; gap: .35rem; align-items: flex-start; font-size: .85rem; margin: .2rem 0; }
  .warn { color: var(--warn); }
  .ok { color: #2e7d32; }
  .dot { display: inline-block; width: .7rem; height: .7rem; border-radius: 50%; margin-right: .3rem; vertical-align: middle; }
  .branch { border-left: 4px solid var(--line); padding: .15rem 0 .15rem .5rem; margin: .35rem 0; }
  .steps { margin: .25rem 0; padding-left: 1.1rem; font-size: .85rem; }
  .steps li { padding: .12rem .2rem; border-radius: 3px; }
  .steps li:hover, .steps li.active { background: #e3f2fd; }
  .pipes { display: block; margin-left: -.9rem; font-size: .72rem; }
  .link { background: none; border: none; padding: 0; color: var(--accent); cursor: pointer; text-decoration: underline; font: inherit; }
  .way { font-size: .8rem; max-width: 100%; margin-left: .3rem; }
  .clickbar { background: #f3e5f5; border: 1px solid #6a1b9a; border-radius: var(--radius); padding: .3rem .45rem; margin: .3rem 0; }
  .activeb { background: #fafafa; }
  .chip { font-size: .72rem; background: #eceff1; border: 1px solid var(--line); border-radius: 999px; padding: 0 .4rem; margin: 0 .2rem; }
</style>
