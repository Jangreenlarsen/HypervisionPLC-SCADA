<script lang="ts">
  // Symbol-guiden (symbolstandarden, fase 6): 6 trin til én konfiguration pr. symbol.
  // Valideringen er serverens (POST …/preview, kaldt løbende) — guiden viser fejl pr. trin og skriveplanen.
  // Reference for opførsel: docs/prototyper/symbolguide.html · teknik: docs/SYMBOLSTANDARD_IMPLEMENTERING.md afsnit 8.
  import { onDestroy, onMount } from 'svelte';
  import { ask as askUser } from './ask';
  import { api, get, post, put, type LiveValue, type TagMeta } from './api';
  import { textFor } from './animate';
  import { expressionError } from './expression';
  import { pasteReport, type CopyResponse } from './symbolCopy';
  import { LiveClient } from './live';
  import SymbolCopy from './SymbolCopy.svelte';
  import TagAlarm from './TagAlarm.svelte';
  import TagSelect from './TagSelect.svelte';
  import AnimParams from './AnimParams.svelte';
  import OwnerAnims from './OwnerAnims.svelte';
  import { mergePalette, paramColors, svgColors } from './usedColors';
  import { KIND_TXT, groupAnimsOn, groupColor, groupsOf, listGroups, type OwnerBlock, type SymbolGroup } from './symbolGroups';
  import { CHART_RANGES, FONT_SCALES, LEGEND_PLACES, MAX_CHART_TAGS, defaultChart, legendOf } from './chartGraphic';
  import { SELECTOR_TYPES, selectorMismatch } from './selectorRedraw';
  import { DIR_TXT, applyLever, leverDirs, leverInSync, type LeverDir } from './toggleSwitch';
  import type { TagAlarm as TagAlarmRow } from './tagAlarm';
  import {
    ALARM_TXT, ANIM_TXT, ON, VAL_TYPES, WHEN_TYPES, parseValRef, valRef, alarmRef, parseAlarmRef, BLINK_TXT, CMP_TXT, MAX_ANIMS, MAX_LOGIC, MAX_LOGIC_INPUTS, MAX_PLANES, MAX_POSITIONS, OP_TXT, POS, STEPS,
    activeAt, animDefaults, keepSuggestion, GLIDE_SPEEDS, glideSeconds, cycleCell, describeBlock, emptyConfig, evalLogic, foundPosition, isLogicRef, newBlock, newSignal, partLabel,
    ALL_OPS, BY_VALUE_TYPES, allowedOps, opChoices, flickerPalette, offersSelectorExample, isValveType, libraryDefault, preset, removeBlock, resize, setOp, tagKind, template, typesFor, valveFromTag,
    type Anim, type AnimType, type LogicBlock, type Op, type PoolBlock, type Signal, type SrcKind, type SymbolConfig, type SymbolInfo,
  } from './symbolConfig';

  interface TagRow { name: string; source: string; unit: string; writable: boolean; plc: string }
  interface Write { tag: string; value: unknown; kind?: string; [k: string]: unknown }
  interface Preview {
    steps: Record<string, string[]>; warnings: string[]; errors: number;
    plans: { position: number; label: string; writes: Write[] }[];
  }

  let { drawingId, element, name, tags, group = [], onclose, onsaved, onremoved }: {
    drawingId: string; element: string; name: string; tags: TagRow[];
    /** "Opsæt de valgte samlet": de ANDRE valgte symboler — de får opsætningen, når der gemmes. */
    group?: { id: string; name: string }[];
    onclose: () => void; onsaved: () => void;
    /** Opsætningen er fjernet fra alle de valgte ("Opsæt de valgte samlet"); antal fjernede */
    onremoved?: (removed: number, skipped: number) => void;
  } = $props();

  const enc = encodeURIComponent;
  const base = $derived(`/api/drawings/${enc(drawingId)}/symbols/${enc(element)}`);

  let cfg = $state<SymbolConfig>(emptyConfig());
  let symbol = $state<SymbolInfo | null>(null);
  let exists = $state(false);
  let hasPin = $state(false);
  let pin = $state('');
  let notes = $state<string[]>([]);
  let pool = $state<PoolBlock[]>([]);   // logikblokke i andre symboler på tegningen
  let step = $state(0);
  let loading = $state(true);
  let error = $state('');       // fejl fra gem/fjern — vises, men stopper ikke guiden
  let loadError = $state('');   // symbolet kunne ikke hentes — guiden kan ikke bruges
  let saving = $state(false);
  let preview = $state<Preview | null>(null);
  let previewError = $state('');
  let checking = $state(false);   // en ændring venter på serverens kontrol
  let liveVals = $state<Record<string, LiveValue>>({});
  let copyOpen = $state(false);   // "Anvend på flere …"
  let savedHere = false;          // gemt undervejs (før kopiering) — luk guiden som efter et gem
  let groupProblems = $state<string[]>([]);   // det der ikke kunne overføres til de andre valgte
  let groupInfo = $state('');

  const tagByName = $derived(new Map(tags.map((t) => [t.name, t])));
  const sigKind = (id: string): 'bool' | 'num' | 'unknown' => {
    const s = cfg.signals.find((x) => x.id === id);
    return s ? tagKindOf(s.tag) : 'unknown';
  };
  function tagKindOf(tag: string): 'bool' | 'num' | 'unknown' {
    const k = tagKind(tagByName.get(tag)?.source);
    if (k !== 'unknown') return k;
    const v = liveVals[tag]?.value;   // ST-variabel: typen kendes fra live-værdien
    return typeof v === 'boolean' ? 'bool' : typeof v === 'number' ? 'num' : 'unknown';
  }
  const byValue = (a: Anim): boolean => !!a.by_value && isPos && !!a.src && !a.src.startsWith('@') && BY_VALUE_TYPES.includes(a.type);
  const srcKind = (a: Anim): SrcKind => (a.src === POS || byValue(a) ? 'pos' : a.src === ON || parseAlarmRef(a.src) || isLogicRef(a.src) || tagKindOf(a.src) === 'bool' ? 'bool' : 'num');
  const n = $derived(cfg.positions.length);
  const isPos = $derived(cfg.op === 'positions');
  const partIds = $derived(['all', ...Object.keys(symbol?.parts ?? {})]);
  const partInfo = (id: string) => (id === 'all' ? symbol ?? undefined : symbol?.parts[id]);
  const locks = $derived(isPos && cfg.lock.positions.some(Boolean));
  const pinOk = $derived(pin === '' || /^\d{4}$/.test(pin));
  const needPin = $derived(locks && !hasPin && !pin);
  const pinMissing = $derived(exists ? 'Symbolet har ingen kode (fx efter gendannelse af en backup) — sæt en ny kode.' : 'Låste positioner kræver en kode.');
  const stepErrors = (k: number): string[] => [...(preview?.steps[String(k + 1)] ?? []), ...(k === 4 && needPin ? [pinMissing] : [])];
  const canSave = $derived(!!preview && !checking && preview.errors === 0 && !needPin && pinOk && !saving && !previewError);

  // ---------------------------------------------------------------- indlæsning
  // Animationer som grupper har lagt på symbolet (v0.131.0): vises skrivebeskyttet under symbolets egne
  let groupOwners = $state<OwnerBlock[]>([]);
  // Hurtigvalg af brugte farver ved farvefelterne: animationernes egne, så symbolets tegnede, så tegningens øvrige
  let drawnOwn = $state<string[]>([]), drawnAll = $state<string[]>([]);
  const palette = $derived(mergePalette([paramColors(cfg.anims), drawnOwn, drawnAll]));
  let memberOf = $state<SymbolGroup[] | null>(null);   // grupperne symbolet er medlem af (null = ikke hentet endnu)
  onMount(() => {
    fetch(`/api/drawings/${encodeURIComponent(drawingId)}/svg`, { credentials: 'same-origin' })
      .then((r) => (r.ok ? r.text() : ''))
      .then((svg) => { drawnOwn = svgColors(svg, element); drawnAll = svgColors(svg); })
      .catch((e) => console.error('Tegningens farver kunne ikke hentes:', e));
    listGroups(drawingId)
      .then((all) => (memberOf = groupsOf(all, element)))
      .catch((e) => { memberOf = []; console.error('Grupperne kunne ikke hentes:', e); });
    groupAnimsOn(drawingId, element)
      .then((o) => (groupOwners = o.map((g) => ({ key: `g${g.group_id}`, label: `Gruppen ${g.group_name}`, color: groupColor(g.group_id), anims: g.anims }))))
      .catch((e) => console.error('Gruppernes animationer kunne ikke hentes:', e));
  });
  onMount(async () => {
    try {
      const r = await get<{ config: SymbolConfig | null; has_pin: boolean; symbol: SymbolInfo | null; orphaned: boolean; warnings: string[]; logic_pool?: PoolBlock[] }>(`${base}/config`);
      if (r.orphaned || !r.symbol) throw new Error(`Elementet '${element}' findes ikke i den aktive version af tegningen`);
      symbol = r.symbol;
      pool = r.logic_pool ?? [];
      hasPin = r.has_pin;
      if (r.config) {
        cfg = normalize(r.config);
        exists = true;
      } else {
        await convert(false);
        const proposal = libraryDefault(symbol);
        if (proposal && !cfg.anims.length && !cfg.signals.length) {
          cfg = proposal.config;
          notes = [...notes, proposal.note];
        }
      }
    } catch (e) {
      loadError = (e as Error).message;
    } finally {
      loading = false;
    }
  });

  /** Udfyld felter serveren kan have udeladt, så formularen altid har dem. */
  function normalize(c: SymbolConfig): SymbolConfig {
    const d = emptyConfig(c.type);
    return {
      ...d, ...c, click: c.click === 'step' ? 'step' as const : 'dialog' as const, fault: c.fault ?? '', lock: { ...d.lock, ...(c.lock ?? {}) },
      signals: (c.signals ?? []).map((s: Partial<Signal> & { id: string }) => ({ ...{ tag: '', fb: '', write: 'set' as const, ms: 500, rest: null }, ...s })),
      anims: (c.anims ?? []).map((a) => {
        const params = a.params ?? {};
        // Blafrer gemt med v0.69.0 (én farve) eller uden palette: altid tre farver at vælge (v0.70.0)
        return { ...a, src: a.src ?? '', only: a.only ?? null, when: Boolean(a.when), by_value: Boolean(a.by_value), params: a.type === 'flicker' ? { ...params, palette: flickerPalette(params) } : params };
      }),
      logic: (c.logic ?? []).map((b) => ({
        id: b.id, name: b.name ?? '', op: b.op ?? 'and', invert: Boolean(b.invert),
        inputs: (b.inputs ?? []).map((i) => ({ src: i.src ?? '', neg: Boolean(i.neg), cmp: i.cmp ?? '', value: i.value ?? null })),
      })),
    };
  }

  /** Forslag ud fra symbolets bindinger i dag (Konvertér). */
  async function convert(ask: boolean): Promise<void> {
    if (ask && !await askUser('Erstat guidens indhold med et forslag ud fra symbolets bindinger i dag?')) return;
    try {
      const s = await get<{ config: SymbolConfig; notes: string[]; convertible: boolean }>(`${base}/suggest`);
      notes = s.notes ?? [];
      if (s.convertible) cfg = normalize(s.config);
      else if (!ask) cfg = emptyConfig(symbol?.type ?? 'custom');
    } catch (e) {
      notes = [`Forslaget kunne ikke hentes: ${(e as Error).message}`];
      if (!ask) cfg = emptyConfig(symbol?.type ?? 'custom');
    }
  }

  // ---------------------------------------------------------------- serverens validering (løbende)
  let timer: ReturnType<typeof setTimeout> | null = null;
  let seq = 0;
  let recheck = $state(0);   // tæller op, når noget UDEN for opsætningen ændres (fx en tag-alarm rettet i trin 6)
  $effect(() => {
    const body = JSON.stringify(cfg);
    void recheck;
    if (loading || loadError) return;
    if (timer) clearTimeout(timer);
    const mine = ++seq;   // hver ændring gør ældre svar forældede — også dem der allerede er undervejs
    checking = true;
    timer = setTimeout(async () => {
      try {
        const r = await post<Preview>(`${base}/preview`, { config: JSON.parse(body) });
        if (mine !== seq) return;
        preview = r;
        previewError = '';
        checking = false;
      } catch (e) {
        if (mine !== seq) return;
        previewError = (e as Error).message;
        checking = false;
      }
    }, 300);
  });

  // ---------------------------------------------------------------- live-værdier (trin 6)
  const live = new LiveClient((changes) => { liveVals = { ...liveVals, ...changes }; });
  const usedTags = $derived([...new Set([
    ...cfg.signals.flatMap((s) => [s.tag, s.fb]), cfg.fault, ...cfg.anims.map((a) => a.src), ...cfg.anims.map((a) => a.params.dir_tag ?? ''),
    ...cfg.logic.flatMap((b) => b.inputs.map((i) => i.src)), ...(cfg.chart?.tags ?? []),
  ].filter((t) => t && t !== POS && !isLogicRef(t) && tagByName.has(t)))].sort());
  /** Graf (v0.91.0): sæt tag nr. i; tomt fjerner det (de øvrige rykker op). */
  function setChartTag(i: number, v: string): void {
    if (!cfg.chart) return;
    const list = [...cfg.chart.tags];
    if (v) list[i] = v; else list.splice(i, 1);
    cfg.chart.tags = [...new Set(list.filter(Boolean))].slice(0, MAX_CHART_TAGS);
  }
  /** Y-aksens grænse: tomt = automatisk (null); komma eller punktum. */
  const yLimit = (v: string): number | null => { const n = Number(v.trim().replace(',', '.')); return v.trim() && Number.isFinite(n) ? n : null; };
  /** Pseudo-tags for blokke i andre symboler som denne konfiguration bruger (til live-værdierne i trin 6). */
  const foreignTags = $derived([...new Set([
    ...cfg.logic.flatMap((b) => b.inputs.map((i) => i.src)), ...cfg.anims.map((a) => a.src), ...cfg.anims.map((a) => a.params.dir_tag ?? ''),
  ].filter((s) => isLogicRef(s) && s.includes(':')).map(pseudoOf))]);
  function pseudoOf(ref: string): string {
    const k = ref.lastIndexOf(':');
    return `sym:${drawingId}:${ref.slice(1, k)}:logic:${ref.slice(k + 1)}`;
  }
  /** Symbolets tags (også dem bag en alarmkilde) — til alarmafsnittet i trin 6 (v0.74.0). */
  const symbolTags = $derived([...new Set([...usedTags, ...cfg.anims.map((a) => parseAlarmRef(a.src)?.tag ?? '')].filter((t) => t && tagByName.has(t)))].sort());
  const alarmNames = $derived(symbolTags.flatMap((t) => [`alarm:${t}:active`, `alarm:${t}:unack`]));
  $effect(() => { live.subscribe([...usedTags, ...foreignTags, ...alarmNames]); });
  // Tagenes alarmopsætning hentes, når trin 6 åbnes (og opdateres, når en alarm rettes her)
  let alarmRows = $state<Record<string, TagAlarmRow & { unit?: string; source?: string; description?: string; trend?: boolean; trend_interval_s?: number }>>({});
  let alarmLoadError = $state('');
  $effect(() => {
    if (step !== 5) return;
    get<(TagAlarmRow & { name: string; unit?: string; source?: string; description?: string; trend?: boolean; trend_interval_s?: number })[]>('/api/tags')
      .then((list) => { alarmRows = Object.fromEntries(list.map((t) => [t.name, t])); alarmLoadError = ''; })
      .catch((e) => { alarmLoadError = (e as Error).message; });
  });
  // Historik (Trends) for symbolets tags (v0.80.0) — tagets "trend" (gælder tagget overalt, som under Tags)
  let trendBusy = $state('');
  let trendError = $state('');
  const noTrend = $derived(symbolTags.filter((t) => alarmRows[t] && !alarmRows[t].trend));
  async function setTrend(names: string[], on: boolean): Promise<void> {
    trendError = '';
    for (const t of names) {
      trendBusy = t;
      try {
        const row = await api<typeof alarmRows[string]>('PATCH', `/api/tags/${encodeURIComponent(t)}`, { trend: on });
        alarmRows = { ...alarmRows, [t]: { ...alarmRows[t], ...row } };
      } catch (e) {
        trendError = `${t}: ${(e as Error).message}`;
        break;   // samme fejl rammer typisk de næste — stop
      }
    }
    trendBusy = '';
  }
  onDestroy(() => {
    live.close();
    if (timer) clearTimeout(timer);
  });
  const valueOf = (t: string) => liveVals[t]?.value;
  /** Tagets enhed til forhåndsvisningen af en Værdi-animation. */
  const metaOf = (t: string): TagMeta | undefined => { const row = tagByName.get(t); return row ? ({ unit: row.unit } as TagMeta) : undefined; };
  const found = $derived(isPos ? foundPosition(cfg, valueOf) : null);
  const logicNow = $derived(evalLogic(cfg.logic, valueOf, (ref) => { const v = valueOf(pseudoOf(ref)); return typeof v === 'boolean' ? v : null; }));
  const triText = (v: boolean | null | undefined) => (v === true ? 'Til' : v === false ? 'Fra' : 'ukendt');
  const fmt = (v: unknown) => (v === undefined || v === null ? '—' : typeof v === 'boolean' ? (v ? 'Til' : 'Fra') : String(v));

  // ---------------------------------------------------------------- redigering
  let showAllOps = $state(false);
  // Former symbolet har haft, mens guiden er åben — de bliver stående i listen, så man altid kan vælge tilbage
  let visitedOps = $state<Op[]>([]);
  $effect(() => { const op = cfg.op; if (!visitedOps.includes(op)) visitedOps = [...visitedOps, op]; });
  const opList = $derived(showAllOps ? ALL_OPS : opChoices(symbol?.type ?? 'custom', cfg.op, visitedOps));
  const opsRestricted = $derived(opList.length < ALL_OPS.length);
  function changeOp(op: Op): void {
    setOp(cfg, op);
  }
  function addPosition(): void {
    if (n >= MAX_POSITIONS) return;
    cfg.positions.push({ label: String(n + 1) });
    resize(cfg, sigKind);
  }
  function removePosition(j: number): void {
    if (n <= 2) return;
    cfg.positions.splice(j, 1);
    for (const p of cfg.planes) p.values.splice(j, 1);
    cfg.lock.positions.splice(j, 1);
    for (const a of cfg.anims) {
      a.only?.splice(j, 1);
      for (const k of ['colors', 'set', 'angles', 'dxs', 'dys', 'dirs']) if (Array.isArray(a.params[k])) a.params[k].splice(j, 1);
    }
  }
  function addSignal(): void {
    if (cfg.signals.length >= 8) return;
    cfg.signals.push(newSignal(cfg));
  }
  async function removeSignal(i: number): Promise<void> {
    const id = cfg.signals[i].id;
    const plane = cfg.planes.find((p) => p.signal === id);
    // Signalets kontaktplan (trin 3) fjernes med — spørg, hvis den allerede har indhold
    if (plane?.values.some((v) => v !== null && v !== undefined) &&
        !(await askUser(`${id} bruges af en kontaktplan (trin 3). Fjern signalet og dets plan?`, { ok: 'Fjern', danger: true }))) return;
    cfg.signals.splice(i, 1);
    cfg.planes = cfg.planes.filter((p) => p.signal !== id);
  }
  function addPlane(): void {
    if (cfg.planes.length >= MAX_PLANES) return;
    const free = cfg.signals.find((s) => !cfg.planes.some((p) => p.signal === s.id)) ?? newSignal(cfg);
    if (!cfg.signals.includes(free)) cfg.signals.push(free);
    cfg.planes.push({ signal: free.id, values: cfg.positions.map(() => (sigKind(free.id) === 'num' ? null : 0)) });
  }
  function setCell(p: { values: (number | null)[] }, j: number, raw: string): void {
    const t = raw.trim().replace(',', '.');
    p.values[j] = t === '' ? null : Number.isFinite(Number(t)) ? Number(t) : p.values[j];
  }
  async function applyTemplate(t: 'A' | 'B' | 'C' | 'D'): Promise<void> {
    if (cfg.planes.length && !await askUser('Erstat kontaktplanerne med skabelonen?')) return;
    template(cfg, t);
  }
  async function applyPreset(): Promise<void> {
    if (!await askUser('Indsæt eksemplet "7-trins vælger" (erstatter positioner, signaler og kontaktplaner)?')) return;
    preset(cfg);
    step = 1;
  }

  // ---- logikblokke
  const blockLabel = (b: LogicBlock) => `${b.id}${b.name ? ` – ${b.name}` : ''}`;
  const poolLabel = (p: PoolBlock) => `${p.symbol} · ${p.id}${p.name ? ` – ${p.name}` : ''}`;
  const poolRef = (p: PoolBlock) => `@${p.element}:${p.id}`;
  const firstBlockRef = (local: LogicBlock[]) => (local[0] ? `@${local[0].id}` : pool[0] ? poolRef(pool[0]) : '');
  const srcMode = (a: Anim): string => (a.src === POS ? POS : a.src === ON ? ON : parseValRef(a.src) !== null ? 'val' : parseAlarmRef(a.src) ? 'alarm' : isLogicRef(a.src) ? 'logic' : 'tag');
  function setSrcMode(a: Anim, mode: string): void {
    a.src = mode === POS ? POS : mode === ON ? ON : mode === 'val' ? valRef(50) : mode === 'alarm' ? alarmRef('active', '') : mode === 'logic' ? firstBlockRef(cfg.logic) : '';
    resetParams(a);
  }
  // ---- 3-vejs ventil styret af ét til/fra-tag
  // Vippekontakten (v0.98.0): grebets stilling pr. position — Op / Midt (kun knoppen) / Ned
  const leverPart = (pid: string) => (symbol ? Object.entries(symbol.parts).find(([, p]) => p.pid === pid)?.[0] ?? null : null);
  const greb = $derived(symbol?.type?.startsWith('vippe_') ? leverPart('greb') : null);
  const knop = $derived(greb ? leverPart('knop') : null);
  const dirs = $derived(greb ? leverDirs(cfg.anims, greb, knop, cfg.positions.length) : []);
  const leverSync = $derived(greb ? leverInSync(cfg.anims, greb, knop, cfg.positions.length) : true);
  function setDir(i: number, d: LeverDir): void {
    if (!greb) return;
    const next = [...dirs]; next[i] = d;
    cfg.anims = applyLever(cfg.anims, greb, knop, next);
  }

  let valveTag = $state('');
  let valveMsg = $state('');
  async function applyValve(): Promise<void> {
    valveMsg = '';
    if (!symbol || !valveTag) return;
    if (tagKindOf(valveTag) === 'num') {
      valveMsg = `${valveTag} er et tal-tag — vælg et til/fra-tag.`;
      return;
    }
    // Intet at skrive til endnu (forslaget "Positioner" uden tag): hurtig opsætning er til visning, så skift til "Kun visning"
    const toView = cfg.op === 'positions' && !cfg.signals.some((s) => s.tag);
    const used = cfg.anims.filter((a) => ['port_a', 'port_b', 'port_ab'].includes(symbol!.parts[a.part]?.pid ?? '')).length;
    if (used && !toView && !await askUser(`Erstat de ${used} eksisterende animationer på portene A, B og AB?`)) return;
    if (toView) setOp(cfg, 'view');   // fjerner også forslagets positions-animationer
    const k = valveFromTag(cfg, symbol, valveTag);
    valveMsg = k > 0 ? `${k} animationer oprettet: Til = AB → A, Fra = AB → B.${toView ? ' Symbolet er sat til "Kun visning".' : ''}`
      : k === 0 ? 'Symbolet har ikke portene A, B og AB.' : 'Der er ikke plads til tre flere animationer (højst 12).';
  }

  function addBlock(): void {
    if (cfg.logic.length >= MAX_LOGIC) return;
    cfg.logic.push(newBlock(cfg));
  }
  function addInput(b: LogicBlock): void {
    if (b.inputs.length >= MAX_LOGIC_INPUTS) return;
    b.inputs.push({ src: '', neg: false, cmp: '', value: null });
  }
  /** Tagget er valgt: et tal-tag får en sammenligning (≥), et til/fra-tag ingen. */
  function inputTagChanged(i: LogicBlock['inputs'][number]): void {
    const k = tagKindOf(i.src);
    if (k === 'num') {
      if (!i.cmp) i.cmp = 'ge';
    } else if (k === 'bool') {
      i.cmp = '';
      i.value = null;
    }
  }
  /** Blokke en indgang må bruge: kun dem over blokken (serveren afviser løkker). */
  const earlier = (b: LogicBlock) => cfg.logic.slice(0, cfg.logic.indexOf(b));
  function setInputMode(b: LogicBlock, i: LogicBlock['inputs'][number], mode: string): void {
    i.src = mode === 'block' ? firstBlockRef(earlier(b)) : '';
    i.cmp = '';
    i.value = null;
  }
  const num2 = (v: string): number | null => (v.trim() !== '' && Number.isFinite(Number(v.replace(',', '.'))) ? Number(v.replace(',', '.')) : null);

  function addAnim(): void {
    if (cfg.anims.length >= MAX_ANIMS) return;
    const part = partIds.find((p) => p !== 'all') ?? 'all';
    const src = isPos ? POS : cfg.signals[0]?.tag ?? '';
    const a: Anim = { part, type: 'fill', src, params: {}, only: null };
    a.params = animDefaults('fill', srcKind(a), n);
    cfg.anims.push(a);
  }
  /** "+ Standard" (v0.72.0): en animation med "altid til" nederst — gælder, når ingen af de aktiv/passive over den er aktive. */
  function addDefault(): void {
    if (cfg.anims.length >= MAX_ANIMS) return;
    const last = cfg.anims[cfg.anims.length - 1];
    const type: AnimType = last && WHEN_TYPES.includes(last.type) ? last.type : 'fill';
    const a: Anim = { part: last?.part ?? 'all', type, src: ON, params: {}, only: null, when: false };
    a.params = animDefaults(type, 'bool', n);
    cfg.anims.push(a);
  }
  /** Nye standardindstillinger efter skift af del/type/kilde. `wasSrc`: kilden før skiftet — vælges det første tag til et
   *  forslag fra biblioteket (fx kontaktens knive: 32°), beholdes forslagets indstillinger, når de passer (v0.94.0). */
  function resetParams(a: Anim, wasSrc?: string): void {
    if (!typesFor(partInfo(a.part)).includes(a.type)) a.type = 'fill';
    if (a.by_value && (!isPos || a.src.startsWith('@') || !BY_VALUE_TYPES.includes(a.type))) a.by_value = false;
    if (parseValRef(a.src) !== null && !VAL_TYPES.includes(a.type)) a.src = '';   // en fast værdi passer kun til tal-animationer
    const fresh = animDefaults(a.type, srcKind(a), n);
    const before = wasSrc === undefined ? undefined : animDefaults(a.type, srcKind({ ...a, src: wasSrc }), n);
    if (!keepSuggestion(wasSrc, a.params, fresh, before)) a.params = fresh;
    if (a.src !== POS) a.only = isPos ? a.only : null;
  }
  function moveAnim(i: number, d: -1 | 1): void {
    const j = i + d;
    if (j < 0 || j >= cfg.anims.length) return;
    [cfg.anims[i], cfg.anims[j]] = [cfg.anims[j], cfg.anims[i]];
  }
  function toggleOnly(a: Anim, j: number): void {
    const only = a.only ?? cfg.positions.map(() => true);
    only[j] = !only[j];
    a.only = only.every(Boolean) ? null : only;
  }
  const num = (v: string, fallback: number) => (Number.isFinite(Number(v.replace(',', '.'))) && v.trim() !== '' ? Number(v.replace(',', '.')) : fallback);

  // ---------------------------------------------------------------- gem / fjern
  /** Gem opsætningen. → true hvis det lykkedes (fejlen vises i guiden). */
  async function persist(): Promise<boolean> {
    saving = true;
    error = '';
    try {
      const body: Record<string, unknown> = { config: $state.snapshot(cfg) };
      if (pin) body.pin = pin;   // skriv-kun: koden sendes kun når den sættes, og vises aldrig igen
      const r = await put<{ has_pin: boolean }>(`${base}/config`, body);
      hasPin = r.has_pin;
      pin = '';
      exists = true;
      return true;
    } catch (e) {
      error = (e as Error).message;
      return false;
    } finally {
      saving = false;
    }
  }
  async function save(): Promise<void> {
    if (!(await persist())) return;
    if (group.length && !(await applyGroup())) return;
    onsaved();
  }
  /** Gruppetilstand: kopiér den netop gemte opsætning til de andre valgte (overskriver — det er hele formålet). → alt gik glat? */
  async function applyGroup(): Promise<boolean> {
    saving = true;
    groupProblems = [];
    groupInfo = '';
    savedHere = true;
    try {
      const res = await post<CopyResponse>(`${base}/copy`, { targets: group.map((g) => g.id), overwrite: true });
      const names = new Map(group.map((g) => [g.id, g.name]));
      const rep = pasteReport(res, name, (id) => names.get(id) ?? id);
      groupInfo = `Gemt i ${name}${res.ok ? ` og ${res.ok} ${res.ok === 1 ? 'andet symbol' : 'andre symboler'}` : ''}.`;
      groupProblems = rep.problems;
      return rep.problems.length === 0;
    } catch (e) {
      error = `Gemt i ${name}, men kunne ikke overføres til de andre: ${(e as Error).message}`;
      return false;
    } finally {
      saving = false;
    }
  }
  /** "Anvend på flere …": serveren kopierer den GEMTE opsætning, så gem først (samme kontrol som Gem). */
  async function openCopy(): Promise<void> {
    if (!(await persist())) return;
    savedHere = true;
    copyOpen = true;
  }
  const close = () => (savedHere ? onsaved() : onclose());
  async function remove(): Promise<void> {
    if (!await askUser(`Fjern symbol-konfigurationen for ${name}? Symbolets gamle bindinger gælder så igen.`)) return;
    saving = true;
    error = '';
    try {
      await api('DELETE', `${base}/config`);
      onsaved();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      saving = false;
    }
  }
  /** "Opsæt de valgte samlet": fjern opsætningen på ALLE de valgte på én gang (alt eller intet). */
  async function removeAll(): Promise<void> {
    const ids = [element, ...group.map((g) => g.id)];
    if (!await askUser(`Fjern symbol-konfigurationen for alle ${ids.length} valgte symboler (${name} m.fl.)? Symbolernes gamle bindinger gælder så igen. Symboler uden opsætning røres ikke.`,
      { ok: 'Fjern fra alle', danger: true })) return;
    saving = true;
    error = '';
    try {
      const r = await post<{ removed: string[]; skipped: string[] }>(`/api/drawings/${encodeURIComponent(drawingId)}/symbols/delete-configs`, { elements: ids });
      if (onremoved) onremoved(r.removed.length, r.skipped.length);
      else onsaved();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      saving = false;
    }
  }
  /** Fjern koden straks (skriv-kun; serveren svarer kun has_pin). */
  async function clearPin(): Promise<void> {
    const msg = locks ? 'Fjern koden? De låste positioner kan så ikke vælges, før en ny kode er sat.' : 'Fjern koden?';
    if (!await askUser(msg)) return;
    error = '';
    try {
      const r = await api<{ has_pin: boolean }>('DELETE', `${base}/pin`);
      hasPin = r.has_pin;
      pin = '';
    } catch (e) {
      error = (e as Error).message;
    }
  }
  const writeText = (w: Write) => `${w.tag} := ${fmt(w.value)}${w.kind === 'pulse' ? ' (puls)' : ''}`;

  // Dialogen kan flyttes rundt ved at trække i overskriften (fx for at se tegningen bagved)
  let dx = $state(0), dy = $state(0);
  let drag: { x: number; y: number; dx: number; dy: number } | null = null;
  function dragStart(e: PointerEvent): void {
    if ((e.target as HTMLElement).closest('button')) return;
    drag = { x: e.clientX, y: e.clientY, dx, dy };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }
  function dragMove(e: PointerEvent): void {
    if (!drag) return;
    // Overskriften holdes inden for skærmen, så dialogen aldrig kan tabes helt
    dx = Math.max(-innerWidth + 80, Math.min(innerWidth - 80, drag.dx + e.clientX - drag.x));
    dy = Math.max(-40, Math.min(innerHeight - 60, drag.dy + e.clientY - drag.y));
  }
  const dragEnd = () => { drag = null; };
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={() => !saving && !copyOpen && close()}>
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="panel guide" role="dialog" aria-modal="true" aria-label="Opsæt symbol {name}" tabindex="-1" onclick={(e) => e.stopPropagation()}
    style="transform: translate({dx}px, {dy}px)">
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <header class="row head" title="Træk i overskriften for at flytte dialogen" onpointerdown={dragStart} onpointermove={dragMove} onpointerup={dragEnd} onpointercancel={dragEnd}>
      {#if group.length}
        <h2>Opsæt {group.length + 1} symboler samlet</h2>
        <span class="muted small">redigerer {name}{exists ? ' (konfigureret)' : ''}</span>
      {:else}
        <h2>Opsæt symbol: {name}</h2>
        <span class="muted small">{element}{symbol?.type ? ` · ${symbol.type}` : ''}{exists ? ' · konfigureret' : ''}</span>
      {/if}
      <button class="close" onclick={close} disabled={saving} aria-label="Luk">✕</button>
    </header>
    {#if memberOf}
      <p class="small members-note">
        {#if memberOf.length}
          Medlem af {memberOf.length === 1 ? 'gruppen' : 'grupperne'}:
          {#each memberOf as g (g.id)}<span class="gchip" style:--c={groupColor(g.id)} title={KIND_TXT[g.kind]}>{g.name}</span>{/each}
          <span class="muted">— deres animationer vises under Visning (trin 4)</span>
        {:else}<span class="muted">Ikke medlem af nogen gruppe.</span>{/if}
      </p>
    {/if}

    {#if group.length}
      <p class="small group-note">Du redigerer <strong>{name}</strong>. Når du gemmer, får også {group.length <= 4 ? group.map((g) => g.name).join(', ') : `${group.slice(0, 3).map((g) => g.name).join(', ')} og ${group.length - 3} andre`} opsætningen (dele oversættes efter navn; nøglelåsen kopieres ikke).</p>
    {/if}
    {#if groupInfo || groupProblems.length}
      <div class="small group-res">
        {#if groupInfo}<p>{groupInfo}</p>{/if}
        {#if groupProblems.length}<div class="error"><strong>Ikke alt kunne overføres</strong> — de øvrige har fået opsætningen:<ul>{#each groupProblems as m}<li>{m}</li>{/each}</ul></div>{/if}
      </div>
    {/if}
    {#if loading}
      <p class="muted">Henter…</p>
    {:else if !symbol}
      <p class="error">{loadError}</p>
    {:else}
      <nav class="steps" aria-label="Trin">
        {#each STEPS as s, k}
          {@const disabled = !isPos && k === 2}
          <button class:active={step === k} {disabled} onclick={() => (step = k)}>
            {k + 1}. {s}{#if stepErrors(k).length}<span class="dot" title="{stepErrors(k).length} fejl"></span>{/if}
          </button>
        {/each}
      </nav>

      <div class="body">
        {#if step === 0}
          <p class="muted small">Vælg hvordan symbolet betjenes. Alt andet i guiden følger af dette valg.</p>
          <div class="ops">
            {#each opList as op}
              <label class="opt"><input type="radio" name="op" checked={cfg.op === op} onchange={() => changeOp(op)} /> {OP_TXT[op]}</label>
            {/each}
          </div>
          {#if opsRestricted || showAllOps}
            <label class="opt small muted"><input type="checkbox" bind:checked={showAllOps} /> Vis alle betjeningsformer (kun de der giver mening for dette symbol vises som standard)</label>
          {/if}
          <div class="row">
            <button onclick={() => convert(true)}>Foreslå ud fra symbolet</button>
            {#if offersSelectorExample(symbol.type)}<button onclick={applyPreset}>Eksempel: 7-trins vælger</button>{/if}
          </div>
          {#if notes.length}
            <div class="notice small"><strong>Forslag fra de gamle bindinger:</strong><ul>{#each notes as m}<li>{m}</li>{/each}</ul></div>
          {/if}
        {:else if step === 1}
          {#if cfg.op === 'view'}
            <p class="muted small">Kun visning: symbolet skriver intet. Animationerne vælger deres tags under trin 4.</p>
          {:else if cfg.op === 'pulse' || cfg.op === 'entry'}
            <label class="field-row">{cfg.op === 'pulse' ? 'Signal der pulses' : 'Register der skrives'}
              <TagSelect bind:value={cfg.signals[0].tag} {tags} writableOnly />
            </label>
          {:else}
            <p class="muted small">Signalerne symbolet skriver. Tilbagemelding (valgfri) bruges til at finde PLC'ens position; ellers bruges kommandoen.</p>
            <table class="grid sig">
              <colgroup><col style="width: 3.2em" /><col style="width: 30%" /><col style="width: 30%" /><col /><col style="width: 2.6em" /></colgroup>
              <thead><tr><th>Id</th><th>Kommando</th><th>Tilbagemelding</th><th>Skrives som</th><th></th></tr></thead>
              <tbody>
                {#each cfg.signals as s, i (s.id)}
                  <tr>
                    <td><strong>{s.id}</strong></td>
                    <td><TagSelect bind:value={s.tag} {tags} writableOnly /></td>
                    <td><TagSelect bind:value={s.fb} {tags} placeholder="— ingen —" /></td>
                    <td class="skriv">
                      <select bind:value={s.write}><option value="set">Sæt</option><option value="pulse">Puls</option></select>
                      {#if s.write === 'pulse'}
                        <input class="n" type="number" min="100" max="10000" step="100" bind:value={s.ms} title="Pulslængde (ms)" /> ms
                        hvile <input class="n" value={s.rest ?? ''} placeholder="0" title="Værdi efter pulsen (tom = 0/Fra)"
                          onchange={(e) => { const t = e.currentTarget.value.trim(); s.rest = t === '' ? null : num(t, 0); }} />
                      {/if}
                    </td>
                    <td><button class="small" onclick={() => removeSignal(i)} aria-label="Fjern {s.id}" title="Fjern signalet {s.id} (og dets kontaktplan)">✕</button></td>
                  </tr>
                {/each}
              </tbody>
            </table>
            {#if !cfg.signals.length}
              <p class="small notice">Ingen signaler. Et symbol med positioner skal have mindst ét — tilføj et med <strong>+ Signal</strong>, eller vælg <em>Kun visning</em> i trin 1, hvis symbolet ikke skal betjenes.</p>
            {/if}
            <button class="small" onclick={addSignal} disabled={cfg.signals.length >= 8}>+ Signal</button>
          {/if}
          {#if cfg.op !== 'view'}
            <label class="field-row">Fejlsignal (valgfrit — betjening spærres når det er sat)
              <TagSelect bind:value={cfg.fault} {tags} placeholder="— intet —" />
            </label>
          {/if}
        {:else if step === 2 && isPos}
          <div class="row wrap">
            <span class="small muted">Positioner:</span>
            {#each cfg.positions as p, j}
              <span class="pos"><input class="lbl" maxlength="20" bind:value={p.label} aria-label="Position {j + 1}" />
                <button class="small" onclick={() => removePosition(j)} disabled={n <= 2} aria-label="Fjern position {j + 1}">✕</button></span>
            {/each}
            <button class="small" onclick={addPosition} disabled={n >= MAX_POSITIONS}>+ Position</button>
          </div>
          {#if symbol && SELECTOR_TYPES.has(symbol.type)}
            {@const drawn = Object.values(symbol.parts).filter((p) => p.tag === 'text' && !p.pid).map((p) => p.text ?? '')}
            {#if selectorMismatch(drawn, cfg.positions.map((p) => p.label))}
              <p class="small notice">Omskifterens tegning viser {drawn.length} positioner ({drawn.join(', ')}). Efter Gem: vælg omskifteren i <strong>Tegn</strong> og tryk <strong>Tegn omskifteren med {n} positioner</strong>, så tegningen og grebets vinkler følger med.</p>
            {/if}
          {/if}
          <div class="row wrap">
            <span class="small muted">Skabelon:</span>
            <button class="small" onclick={() => applyTemplate('A')} title="Ét register med positionens nummer">A · ét register</button>
            <button class="small" onclick={() => applyTemplate('B')} title="Ét til/fra-signal pr. position">B · ét signal pr. position</button>
            <button class="small" onclick={() => applyTemplate('C')} title="Ét register med en bit pr. position">C · bitmaske</button>
            <button class="small" onclick={() => applyTemplate('D')} title="Positionens nummer binært på flere signaler">D · dec → bin</button>
          </div>
          <table class="grid planes">
            <thead><tr><th>Signal</th>{#each cfg.positions as p}<th>{p.label}</th>{/each}<th></th></tr></thead>
            <tbody>
              {#each cfg.planes as p, i}
                {@const k = sigKind(p.signal)}
                <tr>
                  <td><select bind:value={p.signal}>{#each cfg.signals as s}<option value={s.id}>{s.id}{s.tag ? ` · ${s.tag}` : ''}</option>{/each}</select></td>
                  {#each p.values as v, j}
                    <td>
                      {#if k === 'bool'}
                        <button class="cell" class:on={v === 1} class:off={v === 0} onclick={() => (p.values[j] = cycleCell(v))}>{v === 1 ? 'Til' : v === 0 ? 'Fra' : '–'}</button>
                      {:else}
                        <input class="n" value={v ?? ''} placeholder="–" onchange={(e) => setCell(p, j, e.currentTarget.value)} aria-label="{p.signal} i {cfg.positions[j].label}" />
                      {/if}
                    </td>
                  {/each}
                  <td><button class="small" onclick={() => cfg.planes.splice(i, 1)} aria-label="Fjern plan">✕</button></td>
                </tr>
              {/each}
              <tr class="active-row">
                <td class="small muted">Aktive signaler</td>
                {#each cfg.positions as _, j}<td class="small">{activeAt(cfg, j, sigKind).join(' ') || '—'}</td>{/each}<td></td>
              </tr>
            </tbody>
          </table>
          <button class="small" onclick={addPlane} disabled={cfg.planes.length >= MAX_PLANES}>+ Kontaktplan</button>
          <p class="small muted">Til/fra-signaler: klik i cellen (Til → Fra → røres ikke). Registre: skriv værdien, tom = røres ikke.</p>
        {:else if step === 3}
          <div class="row wrap">
            {#if isPos}
              <label class="field-row">Vis
                <select bind:value={cfg.display}><option value="remote">PLC'ens position</option><option value="local">Valgt position</option></select>
              </label>
              <label class="field-row">Tid til at bekræfte (s)
                <input class="n" type="number" min="0.5" max="120" step="0.5" bind:value={cfg.validate_s} />
              </label>
            {/if}
            {#if cfg.op !== 'view'}
              <label class="field-row">Alarm ved afvigelse/fejl
                <select bind:value={cfg.alarm}>{#each Object.entries(ALARM_TXT) as [v, t]}<option value={v}>{t}</option>{/each}</select>
              </label>
            {/if}
          </div>
          {#if isValveType(symbol.type)}
            <div class="notice small">
              <strong>Hurtig opsætning:</strong> styres ventilen af ét til/fra-tag? Til = AB → A, Fra = AB → B (AB er altid åben).
              <div class="row wrap"><TagSelect bind:value={valveTag} {tags} placeholder="— vælg til/fra-tag —" />
                <button class="small" onclick={applyValve} disabled={!valveTag}>Opret animationer</button></div>
              {#if valveMsg}<span class="small">{valveMsg}</span>{/if}
            </div>
          {/if}
          {#if greb && isPos}
            <h4>Grebets stilling pr. position</h4>
            <p class="small muted">Hvordan står vippekontaktens greb i hver position? <em>Midt</em> = grebet peger lige ud mod dig, så kun knoppen ses. Guiden laver selv animationerne på grebet og knoppen.</p>
            <table class="lever">
              <tbody>
                {#each cfg.positions as pos, i (i)}
                  <tr><td>{pos.label || `Position ${i + 1}`}</td>
                    <td><select aria-label="Grebet i {pos.label || `position ${i + 1}`}" value={dirs[i]} onchange={(e) => setDir(i, e.currentTarget.value as LeverDir)}>
                      {#each Object.entries(DIR_TXT) as [d, t] (d)}{#if d !== 'mid' || knop}<option value={d}>{t}</option>{/if}{/each}
                    </select></td></tr>
                {/each}
              </tbody>
            </table>
            {#if !leverSync}<p class="small notice">Grebets animationer nedenfor er sat op på en anden måde. Vælg en stilling ovenfor for at erstatte dem med Op / Midt / Ned.</p>{/if}
          {/if}
          {#if cfg.chart}
            {@const ch = cfg.chart}
            <h4>Graf</h4>
            <p class="small muted">Historikken for 1–{MAX_CHART_TAGS} tags vises i symbolets ramme på Overview — som kurve eller søjler — og opdateres løbende. Tagsene skal gemme historik (slå det til i trin 6).</p>
            <div class="row wrap">
              {#each Array.from({ length: Math.min(MAX_CHART_TAGS, ch.tags.length + 1) }, (_, k) => k) as i (i)}
                <span class="opt small"><label class="opt small">Tag {i + 1} <TagSelect value={ch.tags[i] ?? ''} {tags} placeholder={i === 0 ? '— vælg tag —' : '— ingen —'} onchange={(v) => setChartTag(i, v)} /></label>
                  {#if ch.tags[i]}<button class="small" onclick={() => setChartTag(i, '')} aria-label="Fjern {ch.tags[i]} fra grafen" title="Fjern tagget fra grafen">✕</button>{/if}</span>
              {/each}
            </div>
            <div class="row wrap">
              <label class="opt small">Periode <select bind:value={ch.range_s}>{#each CHART_RANGES as r (r.s)}<option value={r.s}>{r.label}</option>{/each}</select></label>
              <label class="opt small"><input type="radio" bind:group={ch.style} value="line" /> Kurve</label>
              <label class="opt small"><input type="radio" bind:group={ch.style} value="bar" /> Søjler</label>
              {#if ch.style === 'bar'}{@render numInput(ch, 'bars', 'Antal søjler (4–60)')}{/if}
              <label class="opt small">Y-akse fra <input class="n" value={ch.y_min ?? ''} placeholder="auto" onchange={(e) => (ch.y_min = yLimit(e.currentTarget.value))} /></label>
              <label class="opt small">til <input class="n" value={ch.y_max ?? ''} placeholder="auto" onchange={(e) => (ch.y_max = yLimit(e.currentTarget.value))} /></label>
              <label class="opt small">Titel <input class="lbl" bind:value={ch.title} maxlength="60" placeholder="tagenes navne" /></label>
            </div>
            {@const lg = legendOf(ch)}
            <div class="row wrap">
              <span class="small muted">Tekst med tagene:</span>
              <label class="opt small">Placering <select value={lg.place} onchange={(e) => (ch.legend = e.currentTarget.value as 'top' | 'bottom' | 'none')}>{#each LEGEND_PLACES as pl (pl.id)}<option value={pl.id}>{pl.label}</option>{/each}</select></label>
              {#if lg.place !== 'none'}
                <label class="opt small">Størrelse <select value={String(lg.scale)} onchange={(e) => (ch.font_scale = Number(e.currentTarget.value))}>{#each FONT_SCALES as f (f.v)}<option value={String(f.v)}>{f.label}</option>{/each}</select></label>
                <label class="opt small"><input type="checkbox" checked={lg.bold} onchange={(e) => (ch.bold = e.currentTarget.checked)} /> Fed</label>
                <label class="opt small"><input type="checkbox" checked={lg.values} onchange={(e) => (ch.values = e.currentTarget.checked)} /> Vis seneste værdi</label>
              {/if}
            </div>
          {:else if symbol?.type === 'trendgraf'}
            <p class="small"><button class="small" onclick={() => (cfg.chart = defaultChart())}>+ Graf</button> <span class="muted">Symbolet kan vise en graf over tagenes historik.</span></p>
          {/if}
          <h4>Logik ({cfg.logic.length}/{MAX_LOGIC})</h4>
          <p class="small muted">Saml flere tags i én betingelse (fx pumpe kører OG ventil åben), og brug den som kilde til en animation. En blok kan også bruge blokkene over sig og blokke i andre symboler på tegningen (og omvendt — dine blokke kan bruges dér).</p>
          {#each cfg.logic as b (b.id)}
            <div class="anim logic">
              <div class="row wrap">
                <strong>{b.id}</strong>
                <input class="name" bind:value={b.name} maxlength="40" placeholder="Navn (fx Pumpe kører og ventil åben)" aria-label="Blokkens navn" />
                <select bind:value={b.op} aria-label="Regel"><option value="and">AND — alle skal være Til</option><option value="or">OR — mindst én Til</option></select>
                <label class="opt small"><input type="checkbox" bind:checked={b.invert} /> NOT på resultatet</label>
                <span class="spacer"></span>
                <button class="small" onclick={() => removeBlock(cfg, b.id)} aria-label="Fjern blok">✕</button>
              </div>
              {#each b.inputs as inp, k}
                {@const refs = earlier(b)}
                {@const isBlock = isLogicRef(inp.src)}
                <div class="row wrap small input">
                  <label class="opt"><input type="checkbox" bind:checked={inp.neg} /> NOT</label>
                  {#if refs.length || pool.length}
                    <select value={isBlock ? 'block' : 'tag'} onchange={(e) => setInputMode(b, inp, e.currentTarget.value)} aria-label="Indgangstype">
                      <option value="tag">tag</option><option value="block">blok</option>
                    </select>
                  {/if}
                  {#if isBlock}
                    <select bind:value={inp.src} aria-label="Blok">
                      {#if refs.length}<optgroup label="Dette symbol">{#each refs as r}<option value={'@' + r.id}>{blockLabel(r)}</option>{/each}</optgroup>{/if}
                      {#if pool.length}<optgroup label="Andre symboler">{#each pool as p}<option value={poolRef(p)}>{poolLabel(p)}</option>{/each}</optgroup>{/if}
                    </select>
                  {:else}
                    <TagSelect bind:value={inp.src} {tags} onchange={() => inputTagChanged(inp)} />
                    {#if inp.src && tagKindOf(inp.src) !== 'bool'}
                      <select bind:value={inp.cmp} aria-label="Sammenligning">
                        {#if tagKindOf(inp.src) === 'unknown'}<option value="">er Til</option>{/if}
                        {#each Object.entries(CMP_TXT) as [v, t]}<option value={v}>{t}</option>{/each}
                      </select>
                      {#if inp.cmp}<input class="n" value={inp.value ?? ''} onchange={(e) => (inp.value = num2(e.currentTarget.value))} aria-label="Grænseværdi" />{/if}
                    {/if}
                  {/if}
                  <button class="small" onclick={() => b.inputs.splice(k, 1)} disabled={b.inputs.length <= 1} aria-label="Fjern indgang">✕</button>
                </div>
              {/each}
              <div class="row small"><button class="small" onclick={() => addInput(b)} disabled={b.inputs.length >= MAX_LOGIC_INPUTS}>+ Indgang ({b.inputs.length}/{MAX_LOGIC_INPUTS})</button>
                <span class="muted">{describeBlock(b)}</span></div>
            </div>
          {/each}
          <button class="small" onclick={addBlock} disabled={cfg.logic.length >= MAX_LOGIC}>+ Logikblok</button>
          <h4>Animationer ({cfg.anims.length}/{MAX_ANIMS})</h4>
          {#each cfg.anims as a, i}
            {@const kind = srcKind(a)}
            <div class="anim">
              <div class="row wrap">
                <select bind:value={a.part} onchange={() => resetParams(a)} aria-label="Del">
                  {#each partIds as p}<option value={p}>{partLabel(p, symbol)}</option>{/each}
                </select>
                <select bind:value={a.type} onchange={() => resetParams(a)} aria-label="Animation">
                  {#each typesFor(partInfo(a.part)) as t}<option value={t}>{ANIM_TXT[t]}</option>{/each}
                </select>
                <span class="small muted">styres af</span>
                <select value={srcMode(a)} onchange={(e) => setSrcMode(a, e.currentTarget.value)} aria-label="Kilde">
                  {#if isPos}<option value={POS}>symbolets position</option>{/if}<option value="tag">et tag</option>
                  {#if VAL_TYPES.includes(a.type)}<option value="val">en fast værdi</option>{/if}
                  {#if cfg.logic.length || pool.length}<option value="logic">en logikblok</option>{/if}
                  {#if !['level', 'opacity', 'scale', 'text'].includes(a.type)}<option value="alarm">en alarm</option><option value={ON}>altid til</option>{/if}
                </select>
                {#if srcMode(a) === 'tag'}<TagSelect value={a.src} {tags} onchange={(v) => { const was = a.src; a.src = v; resetParams(a, was); }} />{/if}
                {#if srcMode(a) === 'tag' && isPos && BY_VALUE_TYPES.includes(a.type)}
                  <label class="opt small" title={`Tagets værdi er positionens nummer: ${cfg.positions.map((p, j) => `${j} = ${p.label}`).join(', ')}`}>
                    <input type="checkbox" checked={!!a.by_value} onchange={(e) => { a.by_value = e.currentTarget.checked; resetParams(a); }} />
                    Pr. værdi (0 = {cfg.positions[0]?.label ?? '1. position'}, 1 = {cfg.positions[1]?.label ?? '2. position'} …)</label>
                {/if}
                {#if srcMode(a) === 'val'}
                  <input class="n" value={parseValRef(a.src) ?? ''} aria-label="Fast værdi" title="Værdien bruges som om et tag havde den (område: Min–Max nedenfor)"
                    onchange={(e) => (a.src = valRef(num(e.currentTarget.value, parseValRef(a.src) ?? 0)))} />
                {/if}
                {#if srcMode(a) === 'alarm'}
                  {@const al = parseAlarmRef(a.src)!}
                  <select value={al.kind} onchange={(e) => (a.src = alarmRef(e.currentTarget.value as 'active' | 'unack', al.tag))} aria-label="Alarmtilstand">
                    <option value="active">er aktiv</option><option value="unack">er ukvitteret</option>
                  </select>
                  <span class="small muted">på</span>
                  <TagSelect value={al.tag} {tags} onchange={(v) => { a.src = alarmRef(al.kind, v); resetParams(a); }} />
                {/if}
                {#if srcMode(a) === 'logic'}
                  <select bind:value={a.src} onchange={() => resetParams(a)} aria-label="Logikblok">
                    {#if cfg.logic.length}<optgroup label="Dette symbol">{#each cfg.logic as b}<option value={'@' + b.id}>{blockLabel(b)}</option>{/each}</optgroup>{/if}
                    {#if pool.length}<optgroup label="Andre symboler">{#each pool as p}<option value={poolRef(p)}>{poolLabel(p)}</option>{/each}</optgroup>{/if}
                  </select>
                {/if}
                <span class="spacer"></span>
                <button class="small" onclick={() => moveAnim(i, -1)} disabled={i === 0} aria-label="Op">▲</button>
                <button class="small" onclick={() => moveAnim(i, 1)} disabled={i === cfg.anims.length - 1} aria-label="Ned">▼</button>
                <button class="small" onclick={() => cfg.anims.splice(i, 1)} aria-label="Fjern animation">✕</button>
              </div>
              <AnimParams {a} {kind} positions={cfg.positions} logic={cfg.logic} {pool} {tags} {valueOf} {metaOf} {palette} />
              {#if WHEN_TYPES.includes(a.type)}
                <label class="opt small">Når den ikke er aktiv:
                  <select value={a.when ? 'when' : 'toggle'} onchange={(e) => (a.when = e.currentTarget.value === 'when')} aria-label="Når den ikke er aktiv">
                    <option value="toggle">vis fra-tilstand</option>
                    <option value="when">gør ingenting (passiv)</option>
                  </select>
                </label>
              {/if}
              {#if isPos && a.src !== POS}
                <div class="row wrap small"><span class="muted">Gælder i:</span>
                  {#each cfg.positions as p, j}<label class="opt"><input type="checkbox" checked={a.only?.[j] ?? true} onchange={() => toggleOnly(a, j)} /> {p.label}</label>{/each}
                </div>
              {/if}
            </div>
          {/each}
          <div class="row wrap">
            <button class="small" onclick={addAnim} disabled={cfg.anims.length >= MAX_ANIMS}>+ Animation</button>
            <button class="small" onclick={addDefault} disabled={cfg.anims.length >= MAX_ANIMS}
              title="Tilføj en animation med 'altid til' nederst — den gælder, når ingen af de aktiv/passive over den er aktive">+ Standard</button>
          </div>
          <OwnerAnims owners={groupOwners} {symbol} title="Animationer fra grupper (ændres under Grupper — gælder ud over symbolets egne)" />
          {#if cfg.anims.some((x) => x.when)}
            <p class="small muted">Flere animationer af samme slags på samme del: den <strong>øverste aktive</strong> vinder (en med "vis fra-tilstand" tæller altid som aktiv). Er ingen aktive, vises delen som tegnet. Brug ▲▼ til at ordne dem.</p>
          {/if}
        {:else if step === 4}
          {#if cfg.op === 'view'}
            <p class="muted small">Kun visning — intet at betjene.</p>
          {:else}
            <label class="opt"><input type="checkbox" bind:checked={cfg.confirm} /> Operatøren skal bekræfte før der skrives</label>
            {#if isPos}
              <h4>Betjening på tegningen</h4>
              <label class="opt"><input type="radio" name="clickmode" value="dialog" bind:group={cfg.click} /> <strong>Dialog</strong> — et tryk åbner en boks, hvor operatøren vælger position</label>
              <label class="opt"><input type="radio" name="clickmode" value="step" bind:group={cfg.click} /> <strong>Interaktiv</strong> — tryk på <em>venstre</em> side for forrige og <em>højre</em> side for næste position (fx en omskifter med flere positioner)</label>
              {#if cfg.click === 'step'}
                <p class="small muted">Bekræftelse og nøglelås gælder som ellers: kræver positionen bekræftelse eller kode, åbnes boksen med den valgte position. Kendes den viste position ikke endnu, åbnes dialogen.</p>
              {/if}
            {/if}
            {#if cfg.op === 'pulse'}
              <label class="field-row">Pulslængde (ms) <input class="n" type="number" min="100" max="10000" step="100" bind:value={cfg.pulse_ms} /></label>
            {/if}
            {#if isPos}
              <h4>Nøglelås</h4>
              <div class="row wrap small"><span class="muted">Låste positioner:</span>
                {#each cfg.positions as p, j}<label class="opt"><input type="checkbox" bind:checked={cfg.lock.positions[j]} /> {p.label}</label>{/each}
              </div>
              <label class="opt small"><input type="checkbox" bind:checked={cfg.lock.leave} disabled={!locks} /> Koden kræves også for at forlade en låst position</label>
              {#if locks}
                <label class="field-row">Kode (4 cifre){hasPin ? ' — en kode er sat; udfyld kun for at skifte den' : ''}
                  <input class="n pin" type="password" inputmode="numeric" autocomplete="new-password" maxlength="4" bind:value={pin} placeholder={hasPin ? '••••' : ''} />
                </label>
                {#if !pinOk}<p class="small error">Koden skal være præcis 4 cifre.</p>{/if}
                {#if exists && hasPin}<div class="row"><button class="small danger" onclick={clearPin}>Fjern kode</button></div>{/if}
                <p class="small muted">Koden gemmes kun som hash og kommer ikke med i backup — efter en gendannelse skal den sættes igen.</p>
              {:else if exists && hasPin}
                <p class="small muted">Der er en kode, men ingen låste positioner. <button class="small danger" onclick={clearPin}>Fjern kode</button></p>
              {/if}
            {/if}
          {/if}
        {:else if step === 5}
          {#if cfg.signals.some((s) => s.tag)}
            <h4>Live</h4>
            <table class="grid">
              <thead><tr><th>Signal</th><th>Kommando</th><th>Tilbagemelding</th></tr></thead>
              <tbody>
                {#each cfg.signals.filter((s) => s.tag) as s}
                  <tr><td>{s.id}</td><td>{s.tag}: <strong>{fmt(valueOf(s.tag))}</strong></td><td>{s.fb ? `${s.fb}: ` : '—'}{#if s.fb}<strong>{fmt(valueOf(s.fb))}</strong>{/if}</td></tr>
                {/each}
              </tbody>
            </table>
            {#if isPos}<p class="small">PLC'ens position lige nu: <strong>{found !== null ? cfg.positions[found].label : 'ingen entydig position'}</strong></p>{/if}
          {/if}
          {#if cfg.logic.length}
            <h4>Logik (live)</h4>
            <table class="grid">
              <tbody>
                {#each cfg.logic as b}<tr><td><strong>{b.id}</strong> {b.name}</td><td class="small">{describeBlock(b)}</td><td><strong>{triText(logicNow[b.id])}</strong></td></tr>{/each}
              </tbody>
            </table>
          {/if}
          {#if symbolTags.length}
            <h4>Alarmer på symbolets tags</h4>
            {#if alarmLoadError}<p class="small error">Kunne ikke hente tagenes alarmer: {alarmLoadError}</p>{/if}
            <table class="grid">
              <thead><tr><th>Tag</th><th>Alarm</th><th>Lige nu</th><th></th></tr></thead>
              <tbody>
                {#each symbolTags.filter((t) => alarmRows[t]) as t (t)}
                  <TagAlarm name={t} row={alarmRows[t]} kind={tagKindOf(t) === 'bool' ? 'bool' : 'num'}
                    active={liveVals[`alarm:${t}:active`]?.value} unack={liveVals[`alarm:${t}:unack`]?.value}
                    onsaved={(r) => { alarmRows = { ...alarmRows, [t]: r }; recheck++; }} />
                {/each}
              </tbody>
            </table>
          {/if}
          {#if symbolTags.length}
            <h4>Historik (Trends)</h4>
            <table class="grid">
              <thead><tr><th>Tag</th><th>Gem historik</th></tr></thead>
              <tbody>
                {#each symbolTags.filter((t) => alarmRows[t]) as t (t)}
                  <tr>
                    <td><strong>{t}</strong>{#if alarmRows[t].description}<span class="small muted desc">{alarmRows[t].description}</span>{/if}</td>
                    <td><label class="small"><input type="checkbox" checked={!!alarmRows[t].trend} disabled={!!trendBusy}
                      onchange={(e) => setTrend([t], e.currentTarget.checked)} />
                      {alarmRows[t].trend ? `ja — højst hvert ${alarmRows[t].trend_interval_s ?? 10}. sekund` : 'nej'}</label></td>
                  </tr>
                {/each}
              </tbody>
            </table>
            <div class="row">
              {#if noTrend.length}<button class="small" onclick={() => setTrend(noTrend, true)} disabled={!!trendBusy}>{trendBusy ? 'Slår til …' : 'Gem historik for alle'}</button>{/if}
              <a class="small" href={`#trends/${drawingId}/${element}`} target="_blank" rel="noopener">Vis symbolet i Trends ↗</a>
            </div>
            {#if trendError}<p class="small error">{trendError}</p>{/if}
            <p class="small muted">Gælder tagget overalt (samme som under <strong>Tags</strong>). Kurverne fyldes op fra nu af; i <strong>Trends</strong> vælger du symbolet, så vises alle dets kurver. Intervallet ændres under Tags.</p>
          {/if}
          {#if preview?.plans.length}
            <h4>Skriveplan pr. position (fra den aktuelle tilstand)</h4>
            <table class="grid">
              <tbody>
                {#each preview.plans as pl}<tr><td><strong>{pl.label}</strong></td><td class="small">{pl.writes.map(writeText).join(' → ') || 'intet at skrive'}</td></tr>{/each}
              </tbody>
            </table>
          {/if}
        {/if}

        {#if stepErrors(step).length}
          <ul class="errors small">{#each stepErrors(step) as m}<li>{m}</li>{/each}</ul>
        {/if}
        {#if step === 5}
          {#each [1, 2, 3, 4] as k}
            {#if stepErrors(k).length}<p class="small error">Trin {k + 1} ({STEPS[k]}): {stepErrors(k).join(' ')}</p>{/if}
          {/each}
          {#if preview?.warnings.length}<ul class="warnings small">{#each preview.warnings as w}<li>{w}</li>{/each}</ul>{/if}
        {/if}
        {#if previewError}<p class="small error">Kontrol fejlede: {previewError}</p>{/if}
        {#if error}<p class="error">{error}</p>{/if}
      </div>

      <footer class="row">
        {#if group.length}
          <button class="danger" onclick={removeAll} disabled={saving}
            title="Fjern opsætningen fra alle de valgte symboler på én gang">Fjern konfiguration fra alle ({group.length + 1})</button>
        {/if}
        {#if !group.length}
          {#if exists}<button class="danger" onclick={remove} disabled={saving}>Fjern konfiguration</button>{/if}
          <button onclick={openCopy} disabled={!canSave}
            title={canSave ? 'Gem opsætningen og kopiér den til andre symboler på tegningen' : 'Ret fejlene først — opsætningen gemmes, før den kopieres'}>Gem og anvend på flere …</button>
        {/if}
        <span class="spacer"></span>
        <span class="small muted">{checking ? 'Kontrollerer…' : preview ? (preview.errors || needPin ? `${preview.errors + (needPin ? 1 : 0)} fejl` : 'Ingen fejl') : 'Kontrollerer…'}</span>
        <button onclick={() => (step = Math.max(0, step - 1 - (!isPos && step === 3 ? 1 : 0)))} disabled={step === 0}>Tilbage</button>
        {#if step < 5}
          <button onclick={() => (step = Math.min(5, step + 1 + (!isPos && step === 1 ? 1 : 0)))}>Næste</button>
        {/if}
        <!-- Gem på alle trin (v0.69.0): serveren kontrollerer løbende, så der kan gemmes, så snart der ikke er fejl -->
        <button class="primary" onclick={save} disabled={!canSave}
          title={canSave ? '' : 'Ret fejlene først (se trinene markeret med rødt)'}>{saving ? 'Gemmer…' : group.length ? `Gem i alle ${group.length + 1}` : 'Gem'}</button>
      </footer>
    {/if}
  </div>
</div>

{#if copyOpen}
  <SymbolCopy {drawingId} {element} {name} type={symbol?.type ?? ''} onclose={() => (copyOpen = false)} />
{/if}

{#snippet colorInput(obj: Record<string, any>, key: string | number, label: string)}
  <label class="opt small"><input type="color" bind:value={obj[key]} /> {label}</label>
{/snippet}

{#snippet numInput(obj: Record<string, any>, key: string | number, label: string)}
  <label class="opt small">{label} <input class="n" value={obj[key] ?? ''} onchange={(e) => (obj[key] = num(e.currentTarget.value, obj[key] ?? 0))} /></label>
{/snippet}
<style>
  table.lever { width: auto; margin-bottom: 6px; }
  table.lever td { padding: 3px 14px 3px 0; }
  .members-note { margin: .2rem 0 .4rem; }
  .gchip { display: inline-block; margin: 0 .25rem; padding: 0 .5rem; border: 1px solid var(--c); border-left-width: 5px; border-radius: var(--radius); background: color-mix(in srgb, var(--c) 10%, transparent); }
  .group-note { margin: .2rem 0 .4rem; padding: .35rem .6rem; background: var(--panel-2); border: 1px solid var(--line); border-radius: var(--radius); }
  .group-res { margin: 0 0 .4rem; }
  .group-res ul { margin: .2rem 0 0; padding-left: 1.2rem; }
  .backdrop { position: fixed; inset: 0; background: rgba(0, 0, 0, .35); display: flex; align-items: flex-start; justify-content: center; padding: 4vh 16px 0; z-index: 20; }
  .guide { width: 100%; max-width: 780px; max-height: 92vh; display: flex; flex-direction: column; box-shadow: 0 8px 30px rgba(0, 0, 0, .25); }
  .head { align-items: baseline; gap: .6rem; cursor: move; touch-action: none; user-select: none; }
  .head h2 { margin: 0; font-size: 1.15rem; }
  .close { margin-left: auto; }
  .steps { display: flex; flex-wrap: wrap; gap: .25rem; margin: .6rem 0; border-bottom: 1px solid var(--line); padding-bottom: .4rem; }
  .steps button { position: relative; }
  .steps button.active { background: var(--accent); color: #fff; border-color: var(--accent); }
  .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--alarm); margin-left: .35rem; vertical-align: middle; }
  .body { overflow: auto; flex: 1; min-height: 240px; min-width: 0; padding-right: .3rem; }
  .body h4 { margin: .8rem 0 .3rem; }
  footer { gap: .5rem; align-items: center; border-top: 1px solid var(--line); padding-top: .5rem; margin-top: .5rem; }
  .spacer { flex: 1; }
  .ops { display: flex; flex-wrap: wrap; gap: .4rem 1.2rem; margin: .4rem 0 .8rem; }
  .opt { display: inline-flex; align-items: center; gap: .3rem; }
  .wrap { flex-wrap: wrap; gap: .35rem .6rem; align-items: center; }
  .grid { border-collapse: collapse; margin: .3rem 0; }
  .grid th, .grid td { border: 1px solid var(--line); padding: .2rem .35rem; text-align: left; }
  /* En tag-dropdown er ellers lige så bred som sin længste valgmulighed ("navn · kilde (type) [enhed]") og presser nabokolonnerne */
  .grid :global(select), .anim :global(select) { width: auto; max-width: 24em; }   /* :global — TagSelect er en underkomponent */
  .grid td.skriv { min-width: 13em; }
  /* Signal-tabellen i trin 2 skal passe i den smalle guide uden vandret rulning: faste kolonner, tag-valget fylder sin kolonne */
  .grid.sig { width: 100%; table-layout: fixed; }
  .grid.sig td { overflow-wrap: anywhere; }
  .grid.sig td :global(select) { width: 100%; max-width: 100%; min-width: 0; }
  .grid.sig td.skriv { min-width: 0; }
  .grid.sig td.skriv :global(select) { width: auto; }
  .planes td, .planes th { text-align: center; }
  .n { width: 5.5em; }
  .desc { margin-left: .4rem; }
  .lbl { width: 7em; }
  .pin { letter-spacing: .3em; }
  .pos { display: inline-flex; gap: .15rem; }
  .cell { min-width: 3.2em; }
  .cell.on { background: #c8e6c9; border-color: var(--ok); }
  .cell.off { background: #eeeeee; }
  .active-row td { background: var(--panel-2); }
  .name { min-width: 14em; }
  .logic .input { margin: .15rem 0 .15rem 1rem; }
  .anim { border: 1px solid var(--line); border-radius: var(--radius); padding: .4rem; margin: .35rem 0; background: var(--panel-2); }
  .errors { color: var(--alarm); margin: .5rem 0; }
  .warnings { color: var(--warn); }
  .notice { background: #fff8e1; border: 1px solid #ffe082; padding: .4rem .6rem; border-radius: var(--radius); }
  .notice ul { margin: .2rem 0 0 1rem; padding: 0; }
  .danger { color: var(--alarm); }
  .error { color: var(--alarm); }
  .field-row { display: flex; flex-direction: column; gap: .2rem; margin: .3rem 0; }
</style>
