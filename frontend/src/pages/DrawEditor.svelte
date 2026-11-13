<script lang="ts">
  import { onDestroy, onMount, untrack } from 'svelte';
  import { ask as askUser, askText } from '../lib/ask';
  import { suggestName } from '../lib/draw/naming';
  import { del, get, patch, post, put } from '../lib/api';
  import { SELECTOR_TYPES, selectorMismatch, withSelectorAngles } from '../lib/selectorRedraw';
  import { parseSize, presetFor, SIZE_PRESETS, sizeText } from '../lib/drawingSize';
  import { toolHint } from '../lib/toolHints';
  import { knownFavorites, moveFavorite, toggleFavorite } from '../lib/palette';
  import { availableHeight, onLayoutChange } from '../lib/canvas';
  import { deleteDrawingFlow } from '../lib/drawingDelete';
  import GroupBasis from '../lib/GroupBasis.svelte';
  import DrawCanvas from '../lib/draw/DrawCanvas.svelte';
  import Menu from '../lib/draw/Menu.svelte';
  import Inspector, { type InspectApi } from '../lib/draw/Inspector.svelte';
  import ObjectTree, { type TreeApi } from '../lib/draw/ObjectTree.svelte';
  import PanelSection from '../lib/draw/PanelSection.svelte';
  import { loadPanels, savePanels, togglePanel, togglePin } from '../lib/draw/panels';
  import { symbolsHref } from '../lib/symbolRoute';
  // @ts-expect-error — ren JS uden typer
  import { symbolType } from '../../svgedit-host/symbolPorts.js';
  import SymbolGuide from '../lib/SymbolGuide.svelte';
  import { connectionCheck, pairsToBind, planFixes, unboundPairs, type FixMove, type Graph } from '../lib/signalPath';
  import SymbolGroups from '../lib/SymbolGroups.svelte';
  import SymbolTree from '../lib/SymbolTree.svelte';
  import FloatWin from '../lib/FloatWin.svelte';
  import ConnGroups from '../lib/ConnGroups.svelte';
  import FlowLive from '../lib/FlowLive.svelte';
  import GroupAnims from '../lib/GroupAnims.svelte';
  import type { SymbolGroup } from '../lib/symbolGroups';
  import SymbolReplace, { type ReplaceOptions } from '../lib/SymbolReplace.svelte';
  import SymbolExport from '../lib/SymbolExport.svelte';
  import LibraryImport from '../lib/LibraryImport.svelte';
  import { sections as libSections, symbolsIn as libSymbolsIn } from '../lib/library';
  import { defs, library, loadLibrary } from '../lib/libraryStore.svelte';
  import { configGroups, pasteReport, pasteTargets, type ConfigClip, type ConfigGroup, type CopyResponse, type Member, type SymbolRow } from '../lib/symbolCopy';
  import type { SymbolConfig, SymbolInfo } from '../lib/symbolConfig';
  import type { SelectionInfo } from '../lib/symbolSuggest';
  import { FITTING_LEGS, PIPE_IDS, previewViewBox, SYMBOLS, selectorSymbol, withName, type SymbolDef } from '../lib/symbols';
  import { MAX_DIGITS, MIN_DIGITS, segDisplaySvg } from '../lib/segDisplay';
  import { setLeaveGuard } from '../lib/leaveGuard';

  let { route = 'draw' }: { route?: string } = $props();

  interface Version { version: number; comment: string; created_at: number }
  interface Detail { id: string; name: string; active_version: number; versions: Version[] }
  interface Report { removed_elements: Record<string, number>; removed_attributes: Record<string, number>; element_count: number; orphaned_bindings?: string[]; orphaned_symbols?: string[] }
  interface Sel { id: string; tag: string; name?: string; desc?: string; children?: number; type?: string; onePath?: boolean }
  interface ScadaApi {
    ready: Promise<void>;
    load(svg: string): boolean;
    newDrawing(w: number, h: number): void;
    getSvg(): string;
    onSelection(fn: (sel: Sel[]) => void): void;
    onChange(fn: () => void): void;
    setSelectedId(id: string): string;
    selectByIds(ids: string[]): number;
    connectionGraph(): Graph;
    setSelectedText(attr: 'data-hv-name' | 'data-hv-desc', value: string): string;
    uniqueName(base: string): string;
    insertSymbol(fragment: string, baseId: string, at?: { x: number; y: number } | null): string;
    insertGraphic(fragment: string, name?: string, at?: { x: number; y: number } | null, maxFrac?: number, nth?: number): string;
    docPointAt(clientX: number, clientY: number): { x: number; y: number };
    fixConnections(moves: { id: string; from: [number, number]; to: [number, number]; toId: string }[]): { fixed: number; details: { id: string; to: string; gap: number }[]; skipped: number };
    exemptSymbols(ids: string[], on: boolean): number;
    unnamedSymbolCount(): number;
    nameUnnamedSymbols(labels: Record<string, string>): number;
    bindLinks(pairs: { id: string; key: string; to: string; toKey: string }[]): { links: number; elements: number };
    unlink(id: string, key: string): number;
    markConnections(items: { id: string; exempt: boolean; status: string; drift: [number, number][]; driftKeys: string[]; open: [number, number][]; openKeys: string[]; ignored: [number, number][]; ignoredKeys: string[] }[]): void;
    toggleUnused(id: string, key: string): boolean;
    setNameLabels(opts: { symbols: boolean; pipes: boolean }): void;
    setFlowOverlay(data: Record<string, unknown> | null): void;
    setGuides(opts: { grid: boolean; snapGrid: boolean; snapObjects: boolean; keepRatio: boolean; step: number; showGuides: boolean; snapGuides: boolean; snapPipes: boolean }): void;
    getGuides(): { every: number; v: number[]; h: number[]; active: { axis: 'v' | 'h'; at: number } | null };
    setGuideEvery(n: number): void;
    addGuide(axis: 'v' | 'h'): void;
    describeSelection(): SelectionInfo | null;
    replaceSelected(fragment: string, baseId: string, opts: { name?: string; namePrefix?: string; keepId?: boolean; stretch?: boolean; useText?: boolean; similar?: false | 'same' | 'any'; protectIds?: string[]; apexNative?: number; axisNative?: number; mirror?: boolean }):
      { ok?: boolean; replaced?: number; skipped?: number; ids?: string[]; error?: string };
    ungroupSelected(): string;
    selectionColors(): { color: string; uses: number }[];
    recolorSelection(from: string, to: string): number;
    nameElements(ids: string[], base: string): Record<string, string>;
    setReservedIds(ids: string[]): void;
    duplicateNames(): { name: string; count: number }[];
    onMode(fn: (mode: string) => void): void;
    getSize(): { w: number; h: number };
    setSize(w: number, h: number, fit?: boolean, margin?: number): { w?: number; h?: number; error?: string };
    selectorLabels(id: string): string[];
    partIdByPid(id: string, pid: string): string | null;
    fixDuplicateNames(): { id: string; from: string; to: string }[];
    setLibraryPorts(map: Record<string, number[][]>): void;
    setTeeSymbol(def: { fragment: string; label: string } | null): void;
    splitFitting(id: string, legs: string): { ok?: boolean; removed?: string[]; parts?: string[]; error?: string };
    elementBox(id: string): { x: number; y: number; w: number; h: number } | null;
    elementMarkup(id: string): string;
  }

  let drawings = $state<{ id: string; name: string }[]>([]);
  let current = $state<Detail | null>(null); // null = ny, ikke gemt tegning
  let loadedVersion = $state<number | null>(null);
  let newName = $state('');
  let comment = $state('');
  let selection = $state<Sel[]>([]);
  let colors = $state<{ color: string; uses: number }[]>([]);   // farverne i markeringen (panelet Farver)
  let idInput = $state('');
  let nameInput = $state('');
  let dirty = $state(false);
  let busy = $state(false);
  let error = $state('');
  let info = $state('');
  let report = $state<Report | null>(null);
  let ready = $state(false);
  // Tegnehjælp: gitter, fang til gitter/objekter. Huskes pr. browser (ikke pr. tegning).
  const GUIDE_STEPS = [5, 10, 20, 25, 50];
  function loadGuides(): { grid: boolean; snapGrid: boolean; snapObjects: boolean; keepRatio: boolean; step: number; showGuides: boolean; snapGuides: boolean; snapPipes: boolean } {
    const fallback = { grid: false, snapGrid: false, snapObjects: false, keepRatio: false, step: 10, showGuides: true, snapGuides: true, snapPipes: true };
    try {
      const raw = JSON.parse(localStorage.getItem('draw.guides') ?? '{}');
      return { grid: !!raw.grid, snapGrid: !!raw.snapGrid, snapObjects: !!raw.snapObjects, keepRatio: !!raw.keepRatio, step: GUIDE_STEPS.includes(Number(raw.step)) ? Number(raw.step) : 10,
               showGuides: raw.showGuides !== false, snapGuides: raw.snapGuides !== false, snapPipes: raw.snapPipes !== false };
    } catch {
      return fallback; // ingen eller ødelagt localStorage: standardværdier
    }
  }
  let guides = $state(loadGuides());
  $effect(() => {
    const g = $state.snapshot(guides);
    if (ready && ed) ed.setGuides(g);
    try {
      localStorage.setItem('draw.guides', JSON.stringify(g));
    } catch {
      // localStorage kan være blokeret (privat vindue): hjælpen virker stadig, den huskes bare ikke
    }
  });
  // Vis navne (v4.17.0): symboler og forbindelser som mærkater oven på tegningen. Kun visning i Tegn; huskes pr. browser.
  function loadNames(): { symbols: boolean; pipes: boolean } {
    try {
      const raw = JSON.parse(localStorage.getItem('draw.names') ?? '{}');
      return { symbols: !!raw.symbols, pipes: !!raw.pipes };
    } catch {
      return { symbols: false, pipes: false };
    }
  }
  let showNames = $state(loadNames());
  $effect(() => {
    const n = $state.snapshot(showNames);
    void inspectRev;       // tegningen er ændret (flyt, omdøb …): mærkaterne tegnes forfra
    if (ready && ed) ed.setNameLabels({ symbols: n.symbols, pipes: n.pipes });
    try {
      localStorage.setItem('draw.names', JSON.stringify(n));
    } catch {
      // localStorage kan være blokeret: valget virker, det huskes bare ikke
    }
  });
  // Tjek forbindelser (v4.18.0): markér, hvad der hænger fast i resten af tegningen (grønt) og hvad der har åbne ender (rødt). Kun visning.
  let checkConn = $state(false);
  let connSummary = $state<{ open: number; isolated: number; drift: number; unbound: number; bound: boolean; names: string[] } | null>(null);
  let connMoves = $state<FixMove[]>([]);
  let connExempt = $state<Set<string>>(new Set());       // symboler, der er udeladt fra tjekket (data-hv-unused="*")
  const selIds = $derived(selection.map((x) => x.id).filter(Boolean));
  const selAllExempt = $derived(selIds.length > 0 && selIds.every((id) => connExempt.has(id)));
  function exemptSelected(): void {
    if (!ed || !selIds.length) return;
    const n = ed.exemptSymbols(selIds, !selAllExempt);
    info = n ? `${n} symbol${n === 1 ? '' : 'er'} ${selAllExempt ? 'tages med i' : 'udeladt fra'} tjekket af forbindelser. Det gemmes med tegningen (Gem kladde / Gem og udgiv).` : '';
  }       // rettelserne, det seneste tjek foreslår (til *Ret forbindelser*)
  const FIX_GAP = 25;      // en fri rør-ende højst så langt fra et punkt/en anden ende regnes for "tydeligvis skal sidde sammen"
  function fixConnectionsNow(): void {
    if (!ed) return;
    const r = ed.fixConnections(connMoves);
    info = r.fixed
      ? `${r.fixed} forbindelse${r.fixed === 1 ? '' : 'r'} rettet (fortryd med Ctrl+Z).${r.skipped ? ` ${r.skipped} åbne ender er for langt fra noget til at blive rettet automatisk.` : ''}`
      : `Ingen forbindelser at rette automatisk — de åbne ender ligger mere end ${FIX_GAP} enheder fra noget, de kan sættes fast i.`;
    // en bundet tegning holdes bundet: de ender, der nu sidder sammen, gemmes også (eget fortryd-trin)
    const g = r.fixed ? ed.connectionGraph() : null;
    if (g?.nodes.some((n) => n.links?.length)) ed.bindLinks(pairsToBind(g));
    inspectRev++;
  }
  /** Bind forbindelser (v5.3.0): gem det, der hænger sammen nu, som tegningens forbindelser. */
  function bindNow(): void {
    const g = ed?.connectionGraph();
    if (!ed || !g) return;
    const r = ed.bindLinks(pairsToBind(g));
    info = r.links
      ? `${r.links} forbindelse${r.links === 1 ? '' : 'r'} er gemt i tegningen (${r.elements} elementer). De gælder for tjekket; gem tegningen for at beholde dem. Ctrl+Z fortryder.`
      : (r.elements ? 'Forbindelser til slettede elementer er ryddet op.' : 'Alle forbindelser er allerede gemt.');
    inspectRev++;
  }
  /** Er elementet bundet til tegningens forbindelser (v6.3.0, påmindelsen i guiden)? null = kan ikke ses. */
  function isLinked(id: string): boolean | null {
    const g = ed?.connectionGraph();
    return g ? !!g.nodes.find((n) => n.id === id)?.links?.length : null;
  }
  // Påmindelse ved Gem (v6.3.0, Jan: "en påmindelse"): ubundne forbindelser på en tegning med en pumpe eller gemte forbindelser
  let bindReminder = $state(0);
  function checkBindReminder(): void {
    const g = ed?.connectionGraph();
    if (!g) return;
    const n = unboundPairs(g).length;
    const relevant = g.nodes.some((x) => x.type === 'pumpe' || (x.links ?? []).length > 0);
    bindReminder = n && relevant ? n : 0;
    if (bindReminder) msgOpen = true;
  }
  /** Antal gemte forbindelser (hver tælles én gang, selv om den står på begge elementer). */
  const countLinks = (g: Graph) => Math.round(g.nodes.reduce((n, x) => n + (x.links ?? []).filter((l) => l.i >= 0).length, 0) / 2);
  let connTimer: ReturnType<typeof setTimeout> | undefined;
  $effect(() => {
    const on = checkConn;
    void inspectRev;       // tegningen er ændret (flyt, forbind, slet …): tjekket køres forfra efter et kort øjeblik
    clearTimeout(connTimer);
    if (!ready || !ed) return;
    if (!on) {
      ed.markConnections([]);
      connSummary = null;
      return;
    }
    connTimer = setTimeout(() => {
      const g = ed?.connectionGraph();
      if (!g || !checkConn) return;
      const items = connectionCheck(g);
      ed?.markConnections(items.map((i) => ({ id: i.id, exempt: i.exempt, status: i.status, open: i.open, openKeys: i.openKeys, ignored: i.ignored,
        ignoredKeys: i.ignoredKeys, drift: i.drift, driftKeys: i.driftKeys })));
      connMoves = planFixes(g, items, FIX_GAP);
      connExempt = new Set(items.filter((i) => i.exempt).map((i) => i.id));
      const bad = items.filter((i) => i.status !== 'ok');
      connSummary = { open: bad.filter((i) => i.status === 'open').length, isolated: bad.filter((i) => i.status === 'isolated').length,
        drift: items.filter((i) => i.drift.length).length, unbound: unboundPairs(g).length,
        bound: g.nodes.some((n) => (n.links ?? []).length > 0), names: bad.slice(0, 30).map((i) => i.name || i.id) };
    }, 300);
  });
  onDestroy(() => clearTimeout(connTimer));
  let flowOpen = $state(false);                                    // Flow-vinduet over tegningen (v6.1.0): forbindelsesgrupper
  let guideFor = $state<{ id: string; name: string } | null>(null); // symbol-guiden (6 trin) er åben
  let treeRev = $state(0);                                         // symbol-oversigten henter forfra (v5.5.0)
  let unnamed = $state(0);                                          // symboler uden navn i tegningen (v5.9.0)
  $effect(() => { void inspectRev; unnamed = ready && ed ? ed.unnamedSymbolCount() : 0; });
  function nameThem(): void {
    const labels: Record<string, string> = {};
    for (const s of defs()) labels[s.id] = s.label;
    const n = ed?.nameUnnamedSymbols(labels) ?? 0;
    info = n ? `${n} symbol${n === 1 ? '' : 'er'} har fået et unikt navn. Gem tegningen for at beholde navnene (Ctrl+Z fortryder).` : 'Alle symboler har et navn.';
    inspectRev++;
  }
  let treeGroup = $state<SymbolGroup | null>(null);                // gruppens animationer åbnet fra oversigten
  let tags = $state<{ name: string; source: string; unit: string; writable: boolean; plc: string }[]>([]);
  let ed: ScadaApi | null = null;
  let canvasRef = $state<{ perform(name: string): void } | null>(null);
  let zoomLevel = $state(1);

  // Tegne-editoren (v3.0.0): SVG-Edits tegnemotor (@svgedit/svgcanvas) direkte i siden med vores egen brugerflade
  // (lib/draw/*). Al Tegn-logik ligger i svgedit-host/scada-core.js.
  let editorHeight = $state(600);
  const SYMBOL_DRAG = 'application/x-hv-symbol';   // træk-og-slip fra symbolpaletten
  let inspectRev = $state(0);
  // Højre panel: foldbare sektioner — åbnes én, foldes de ikke-fastgjorte sammen (v3.5.0)
  let panels = $state(loadPanels());
  let objCount = $state(0);
  let guideEvery = $state(0);   // tegningens faste inddeling (læses fra tegningen)
  $effect(() => savePanels($state.snapshot(panels)));
  // antal elementer i tegningen (tallet ved Objekter — også når sektionen er foldet sammen)
  $effect(() => {
    void inspectRev;
    const list = ready && ed ? (ed as unknown as TreeApi).objectList() : [];
    objCount = list.reduce((n, l) => n + l.items.length, 0);
    guideEvery = ready && ed ? ed.getGuides().every : 0;
  });
  const sec = (id: string) => ({
    open: panels.open.includes(id),
    pinned: panels.pinned.includes(id),
    ontoggle: (x: string) => (panels = togglePanel(panels, x)),
    onpin: (x: string) => (panels = togglePin(panels, x)),
  });   // panelet Egenskaber læser markeringen igen, når tallet skifter

  // Listen over tegninger skal være hentet, før #draw/<tegning> kan åbnes (den nye editor er klar før listen)
  let drawingsLoaded: () => void = () => {};
  const drawingsReady = new Promise<void>((r) => (drawingsLoaded = r));

  async function attach(api: ScadaApi): Promise<void> {
    ed = api;
    await ed.ready;
    ed.onSelection((sel) => {
      selection = sel;
      colors = sel.length && ed ? ed.selectionColors() : [];
      idInput = sel.length === 1 ? sel[0].id : '';
      nameInput = sel.length === 1 ? sel[0].name ?? '' : '';
      void checkSelector();
      inspectRev++;
    });
    ed.onMode((m) => (mode = m));   // hjælpelinjen under tegneområdet (v0.92.0)
    // dublet-navne følges løbende (fx tilbage efter Ctrl+Z på "Giv dem unikke navne")
    ed.onChange(() => { dirty = true; dupNames = ed!.duplicateNames(); readSize(); inspectRev++; });
    ready = true;
    // Rør koblet på et rør får bibliotekets T-stykke (tre ben, hvert med eget løbelys i guiden)
    const tee = SYMBOLS.find((x) => x.id === 't_stykke');
    ed.setTeeSymbol(tee ? { fragment: tee.svg, label: tee.label } : null);
    // Symbol-editorens rettede tilslutningspunkter bygges ind i symboler, der indsættes herfra
    try {
      ed.setLibraryPorts(await get<Record<string, number[][]>>('/api/symbol-ports'));
    } catch (e) {
      info = `Symbolernes rettede tilslutningspunkter kunne ikke hentes (${(e as Error).message}) — nye symboler får de automatiske.`;
    }
    await drawingsReady;
    const [, fromRoute, wantSelector] = route.split('/');
    if (fromRoute && drawings.some((d) => d.id === fromRoute)) {
      await open(fromRoute);
      if (wantSelector?.startsWith('sym:')) startSymbolEdit(decodeURIComponent(wantSelector.slice(4)));   // fra Symboler › Bibliotek
      else if (wantSelector) await guarded('Tegn omskifteren', () => redrawFromRoute(wantSelector));   // fra Bindinger: #draw/<tegning>/<omskifter>
    } else startNew(true);
  }

  // ---- Redigér et biblioteks-symbols grafik (v4.7.1): arbejdstegning fra Symboler › Bibliotek
  let symbolEdit = $state<{ type: string; label: string; own: boolean } | null>(null);
  function startSymbolEdit(type: string): void {
    const d = defs().find((x) => x.id === type);
    if (!ed || !d) { info = `Symbolet '${type}' findes ikke i biblioteket.`; return; }
    const own = library.own.some((s) => s.type === type);
    symbolEdit = { type, label: d.label, own };
    const items = (ed as unknown as TreeApi).objectList().flatMap((l) => l.items);
    if (!items.length) {   // en ny arbejdstegning: læg symbolet ind og vælg det
      const id = ed.insertSymbol(withName(d.svg, d.label), d.id);
      if (id) ed.selectByIds([id]);
      dirty = true;
    }
  }
  async function saveSymbolEdit(): Promise<void> {
    if (selection.length !== 1) {
      error = 'Vælg det samlede symbol (gruppér delene med Ctrl+G, hvis du har opløst det), og tryk igen.';
      return;
    }
    await openExport();
  }
  async function afterSymbolSaved(msg: string): Promise<void> {
    exportFor = null;
    info = msg;
    const id = current?.id;
    if (!id) return;
    if (await askUser(`${msg}\n\nSlet arbejdstegningen "${current?.name}" og gå tilbage til biblioteket?`, { ok: 'Slet og gå tilbage' })) {
      try {
        await del(`/api/drawings/${encodeURIComponent(id)}`);
        dirty = false;
        symbolEdit = null;
        location.hash = '#symbols';
      } catch (e) {
        error = (e as Error).message;
      }
    }
  }

  /** Åbnet fra Bindinger med "Gem og tegn omskifteren om": vælg omskifteren og tegn den om med opsætningens positioner (v2.11.0). */
  async function redrawFromRoute(id: string): Promise<void> {
    if (!ed || !ed.selectByIds([id])) { info = `Omskifteren '${id}' findes ikke i den aktive version af tegningen.`; return; }
    for (let i = 0; i < 40 && selection[0]?.id !== id; i++) await new Promise((r) => setTimeout(r, 100));
    await checkSelector();
    if (selectorFix) await redrawSelector(true);
    else info = 'Omskifterens tegning passer allerede med opsætningens positioner.';
  }

  // Omskifter (v0.91.1): tegningens positioner skal følge opsætningens — ellers tilbyd at tegne den igen
  let selectorFix = $state<{ id: string; drawn: string[]; labels: string[] } | null>(null);
  async function checkSelector(): Promise<void> {
    const sel = selection.length === 1 ? selection[0] : null;
    if (!ed || !current || !sel || !SELECTOR_TYPES.has(sel.type ?? '')) { selectorFix = null; return; }
    try {
      const r = await get<{ config: SymbolConfig | null }>(`/api/drawings/${encodeURIComponent(current.id)}/symbols/${encodeURIComponent(sel.id)}/config`);
      if (selection[0]?.id !== sel.id) return;   // et andet element er valgt imens
      const labels = r.config?.op === 'positions' ? r.config.positions.map((p) => p.label) : [];
      const drawn = ed.selectorLabels(sel.id);
      selectorFix = selectorMismatch(drawn, labels) ? { id: sel.id, drawn, labels } : null;
    } catch {
      selectorFix = null;   // ingen opsætning (fx et ikke-udgivet symbol) — intet at sammenligne med
    }
  }
  // auto = true efter guidens Gem: tegningen var udgivet før guiden åbnede, så den gemmes uden at spørge (v2.4.0)
  async function redrawSelector(auto = false): Promise<void> {
    const fix = selectorFix, sel = selection[0];
    if (!ed || !fix || !sel || sel.id !== fix.id || !current) return;
    error = '';
    const oldGreb = ed.partIdByPid(fix.id, 'greb');
    const res = ed.replaceSelected(withName(selectorSymbol(fix.labels), sel.name || 'Omskifter'), sel.type || 'omskifter',
      { name: sel.name || undefined, keepId: true, stretch: false, useText: false, similar: false, protectIds: [] });
    if (res.error) { error = res.error; return; }
    dirty = true;
    const grebId = ed.partIdByPid(fix.id, 'greb');
    if (!(await ensurePublished('omskifterens nye tegning kan bruges', auto))) {
      info = 'Omskifteren er tegnet med de nye positioner. Gem og udgiv tegningen, og tryk så knappen igen for at rette grebets vinkler.';
      return;
    }
    const base = `/api/drawings/${encodeURIComponent(current.id)}/symbols/${encodeURIComponent(fix.id)}/config`;
    try {
      const r = await get<{ config: SymbolConfig }>(base);
      await put(base, { config: withSelectorAngles(r.config, grebId, oldGreb) });
      info = `Omskifteren viser nu ${fix.labels.length} positioner (${fix.labels.join(', ')}), og grebet peger på dem.`;
    } catch (e) {
      error = `Tegningen er gemt, men grebets vinkler kunne ikke rettes: ${(e as Error).message} — ret dem i guiden (trin 4, Drej).`;
    }
    selectorFix = null;
  }

  // Det valgte værktøj → hjælpelinjen (v0.92.0)
  let mode = $state('select');
  const hint = $derived(toolHint(mode));

  // Tegningens størrelse (v0.92.0)
  let size = $state({ w: 1200, h: 700 });
  let sizeOpen = $state(false);
  let sizeForm = $state({ w: '', h: '', margin: '20' });
  let sizeError = $state('');
  const readSize = () => { if (ed) size = ed.getSize(); };
  function openSize(): void {
    readSize();
    sizeForm = { w: String(size.w), h: String(size.h), margin: sizeForm.margin };
    sizeError = '';
    sizeOpen = !sizeOpen;
  }
  function applySize(fit: boolean): void {
    if (!ed) return;
    sizeError = '';
    let w = 0, h = 0;
    if (!fit) {
      const r = parseSize(sizeForm.w, sizeForm.h);
      if ('error' in r) { sizeError = r.error; return; }
      ({ w, h } = r);
    }
    const margin = Math.max(0, Math.min(500, Math.round(Number(sizeForm.margin.replace(',', '.')) || 0)));
    const res = ed.setSize(w, h, fit, margin);
    if (res.error) { sizeError = res.error; return; }
    readSize();
    sizeForm = { ...sizeForm, w: String(size.w), h: String(size.h) };
    dirty = true;
    info = `Tegningen er nu ${sizeText(size.w, size.h)}${fit ? ` (tilpasset indholdet med ${margin} i margen)` : ''}. Ctrl+Z fortryder; tryk Gem kladde eller Gem og udgiv for at gemme.`;
  }

  // Symboler med samme navn (v0.89.0) — fx gamle kopier fra før v0.63.1; navnene skal være unikke
  let dupNames = $state<{ name: string; count: number }[]>([]);
  async function fixDuplicates(): Promise<void> {
    if (!ed) return;
    await guarded('Giv unikke navne', async () => {
      const done = ed!.fixDuplicateNames();
      dupNames = ed!.duplicateNames();
      info = `${done.length} symbol${done.length === 1 ? '' : 'er'} fik nyt navn: ${done.map((d) => `"${d.from}" → "${d.to}"`).join(', ')}. ` +
        'Tryk Gem kladde eller Gem og udgiv for at gemme (Ctrl+Z fortryder).';
    });
  }

  /** Til symbol-editoren (med "Tilbage til tegningen"); ugemte ændringer går tabt — spørg først. */
  async function gotoSymbols(type: string | null): Promise<void> {
    if (dirty && !(await askUser('Tegningen har ændringer, der ikke er gemt — de går tabt, hvis du skifter til Symboler. Gem først med "Gem kladde", eller fortsæt og kassér dem.', { ok: 'Kassér og fortsæt', danger: true }))) return;
    dirty = false;
    location.hash = symbolsHref(current?.id ?? null, type);
  }

  async function confirmDiscard(): Promise<boolean> {
    return !dirty || await askUser('Der er ændringer der ikke er gemt. Kassér dem?');
  }

  async function startNew(force = false): Promise<void> {
    if (!ed || (!force && !(await confirmDiscard()))) return;
    ed.newDrawing(1200, 700);
    ed.setReservedIds([]);
    dupNames = [];
    size = { w: 1200, h: 700 };
    current = null;
    loadedVersion = null;
    newName = '';
    dirty = false;
    report = null;
    info = '';
    history.replaceState(null, '', '#draw');
  }

  async function open(id: string, version?: number): Promise<void> {
    if (!ed || !(await confirmDiscard())) return;
    error = info = '';
    report = null;
    try {
      const detail = await get<Detail>(`/api/drawings/${encodeURIComponent(id)}`);
      const v = version ?? detail.active_version;
      const resp = await fetch(`/api/drawings/${encodeURIComponent(id)}/svg?version=${v}`);
      if (!resp.ok) throw new Error(`Kunne ikke hente SVG (HTTP ${resp.status})`);
      const text = await resp.text();
      // De reserverede id'er skal kendes FØR indlæsningen: SVG-Edit giver elementer uden id (fx dele af 3-vejs ventilen)
      // et svg_N-id, når tegningen indlæses — ellers kan de få et id med en gammel opsætning (BUGS.md v0.83.1)
      await refreshReservedIds(id);
      if (!ed.load(text)) throw new Error('SVG-Edit kunne ikke læse tegningen');
      current = detail;
      loadedVersion = v;
      dirty = false;
      dupNames = ed.duplicateNames();
      readSize();
      history.replaceState(null, '', `#draw/${id}`);
    } catch (e) {
      error = (e as Error).message;
    }
  }

  /**
   * Opsæt det valgte symbol med guiden (6 trin). Guiden arbejder på tegningens AKTIVE version, så tegningen
   * gemmes og udgives først, hvis den er ny eller har ændringer.
   */
  async function openGuide(): Promise<void> {
    const sel = selection.length === 1 ? selection[0] : null;
    if (!ed || !sel?.name) return;
    error = '';
    if (!(await ensurePublished('symbolet kan opsættes'))) return;
    try {
      if (!tags.length) tags = await get('/api/tags');
    } catch (e) {
      error = (e as Error).message;
      return;
    }
    guideFor = { id: sel.id, name: sel.name };
  }

  /**
   * Opsæt et element UDEN navn (v3.36.0): spørg efter et navn (forslag "Rør 1", "Linje 2" …), sæt det, og åbn guiden.
   * Før stod kun en tekst om at give elementet et navn — let at overse, især for rør.
   */
  async function nameAndGuide(): Promise<void> {
    const sel = selection.length === 1 ? selection[0] : null;
    if (!ed || !sel || sel.name) return;
    const items = (ed as unknown as TreeApi).objectList().flatMap((l) => l.items);
    const me = items.find((it) => it.id === sel.id);
    const label = sel.type ? SYMBOLS.find((x) => symbolType(x.id) === sel.type)?.label : undefined;
    const name = await askText('Elementet skal have et navn for at kunne sættes op som symbol (vises fx i alarmer og i Bindinger).', {
      value: suggestName({ tag: sel.tag, pipe: me?.pipe, label }, items.map((it) => it.name).filter(Boolean)),
      ok: 'Videre til guiden',
    });
    if (!name) return;
    const err = ed.setSelectedText('data-hv-name', name);
    if (err) {
      error = err;
      return;
    }
    nameInput = name;
    dirty = true;
    selection = selection.map((x) => (x.id === sel.id ? { ...x, name } : x));
    await openGuide();
  }

  /**
   * Id'er med opsætning eller binding på tegningen (også forsvundne) må ikke gives til nye elementer — ellers "vågner" en
   * gammel opsætning op på dem (BUGS.md v0.68.0). Hentes når tegningen åbnes, og når opsætninger ændres.
   */
  async function refreshReservedIds(drawingId = current?.id): Promise<void> {
    if (!ed || !drawingId) return;
    try {
      ed.setReservedIds(await get<string[]>(`/api/drawings/${encodeURIComponent(drawingId)}/used-ids`));
    } catch (e) {
      // uden listen kan et id blive genbrugt — sig det, men lad tegningen kunne bruges
      ed.setReservedIds([]);   // ikke den forrige tegnings liste
      error = `Kunne ikke hente tegningens brugte id'er (nye elementer kan arve en gammel opsætning): ${(e as Error).message}`;
    }
  }

  /** Symbolopsætninger hører til tegningens AKTIVE version: gem og udgiv først, hvis tegningen er ny, ændret eller en kladde. → klar? */
  async function ensurePublished(why: string, asked = false): Promise<boolean> {
    if (current !== null && !dirty && loadedVersion === current.active_version) return true;
    if (!current && !newName.trim()) {
      error = `Giv tegningen et navn (øverst) — den skal gemmes, før ${why}`;
      return false;
    }
    if (!asked && !await askUser(`Tegningen gemmes og udgives først, så ${why}. Fortsæt?`)) return false;
    await save(true);
    return !error && !dirty && current !== null; // save() har vist en evt. fejl
  }

  // ---- Opsæt de valgte samlet (v0.63.0): guiden redigerer ét udgangspunkt, og Gem giver alle de valgte opsætningen
  let groupFor = $state<{ basis: { id: string; name: string }; others: { id: string; name: string }[] } | null>(null);
  let basisChoice = $state<{ groups: ConfigGroup[]; members: Member[]; unnamed: string[] } | null>(null);

  /** Kør en handling fra panelet, så en uventet fejl altid vises (ellers sker der bare ingenting — BUGS.md v0.63.1). */
  async function guarded(what: string, fn: () => Promise<void>): Promise<void> {
    try {
      await fn();
    } catch (e) {
      busy = false;
      // "x is not a function": tegneeditoren mangler en funktion — typisk en gammel kopi i browseren
      const old = e instanceof TypeError && /is not a function/.test(e.message) ? ' — tegneeditoren er sandsynligvis en ældre version; genindlæs siden med Ctrl+F5' : '';
      error = `${what} fejlede: ${(e as Error).message}${old}`;
      console.error(what, e);
    }
  }

  async function openGroupGuide(): Promise<void> {
    if (!ed || selection.length < 2) return;
    error = info = '';
    const withId = selection.filter((s) => !!s.id);
    const named = withId.filter((s) => !!s.name?.trim());
    const unnamed = withId.filter((s) => !s.name?.trim()).map((s) => s.id);
    if (!named.length) {
      error = 'Giv mindst ét af de valgte symboler et navn — det bliver udgangspunktet, og de andre navngives efter det.';
      return;
    }
    if (!(await ensurePublished('de valgte kan sættes op'))) return;
    busy = true;
    let members: Member[];
    try {
      if (!tags.length) tags = await get('/api/tags');
      const did = encodeURIComponent(current!.id);
      members = await Promise.all(named.map(async (s) => {
        const r = await get<{ config: SymbolConfig | null; symbol: SymbolInfo | null }>(`/api/drawings/${did}/symbols/${encodeURIComponent(s.id)}/config`);
        return { element: s.id, name: s.name!.trim(), config: r.config, symbol: r.symbol };
      }));
    } catch (e) {
      error = (e as Error).message;
      return;
    } finally {
      busy = false;
    }
    const gone = members.filter((m) => !m.symbol);
    if (gone.length) {
      error = `${gone.map((m) => m.name).join(', ')} findes ikke i den udgivne version af tegningen.`;
      return;
    }
    const groups = configGroups(members);
    if (groups.length > 1) {
      basisChoice = { groups, members, unnamed };   // brugeren vælger udgangspunktet i dialogen
      return;
    }
    await startGroup(groups[0]?.members[0] ?? members[0], members, unnamed);
  }

  async function startGroup(basis: Member, members: Member[], unnamed: string[]): Promise<void> {
    basisChoice = null;
    let extra: { id: string; name: string }[] = [];
    if (unnamed.length) {
      const who = unnamed.length === 1 ? 'Ét valgt element har' : `${unnamed.length} valgte elementer har`;
      if (!await askUser(`${who} intet navn. De får navnet "${basis.name}" med løbenummer (${basis.name}_1, ${basis.name}_2 … — numre der allerede er brugt, springes over), og tegningen gemmes og udgives med de nye navne. Fortsæt?`)) return;
      const named = ed?.nameElements(unnamed, basis.name) ?? {};
      extra = Object.entries(named).map(([id, name]) => ({ id, name }));
      if (!(await ensurePublished('de valgte kan sættes op', true))) return;
    }
    groupFor = {
      basis: { id: basis.element, name: basis.name },
      others: [...members.filter((m) => m.element !== basis.element).map((m) => ({ id: m.element, name: m.name })), ...extra],
    };
  }

  // ---- Kopiér/indsæt symbolopsætning (v0.60.0): selve opsætningen ligger på serveren; "udklipsholderen" husker kun kilden
  let clip = $state<ConfigClip | null>(null);
  async function copyConfig(): Promise<void> {
    const sel = selection.length === 1 ? selection[0] : null;
    if (!sel?.name) return;
    error = info = '';
    if (!current) {
      error = 'Tegningen er ikke gemt endnu — der er ingen opsætning at kopiere';
      return;
    }
    try {
      // opsætningen findes kun for symboler i den UDGIVNE version (et nyt, ikke-udgivet symbol har ingen)
      const r = await get<{ config: unknown | null; orphaned: boolean }>(`/api/drawings/${encodeURIComponent(current.id)}/symbols/${encodeURIComponent(sel.id)}/config`);
      if (r.orphaned) throw new Error(`"${sel.name}" findes ikke i den udgivne version af tegningen — gem og udgiv, og sæt det op først`);
      if (!r.config) throw new Error(`"${sel.name}" har ingen opsætning endnu — sæt det op med "Opsæt symbol (6 trin)" først`);
      clip = { drawingId: current.id, element: sel.id, name: sel.name };
      info = `Opsætningen fra "${sel.name}" er kopieret — vælg et eller flere andre symboler og tryk "Indsæt opsætning".`;
    } catch (e) {
      error = (e as Error).message;
    }
  }
  const clipHere = $derived(!!clip && !!current && clip.drawingId === current.id);
  async function pasteConfig(): Promise<void> {
    if (!clip || !clipHere) return;
    const src = clip;
    const { targets, unnamed, noId, self } = pasteTargets(selection, src);
    error = info = '';
    if (!targets.length && !unnamed.length) {
      error = self ? `Det er "${src.name}" selv — vælg et andet symbol.` : 'Vælg et eller flere elementer at indsætte opsætningen i.';
      return;
    }
    let named: Record<string, string> = {};
    if (unnamed.length) {
      // elementer uden navn bliver symboler med kildens navn + løbenummer ("<navn>_1", "_2" …); navnet er en tegningsændring
      const published = current !== null && !dirty && loadedVersion === current.active_version;
      if (!current && !newName.trim()) {
        error = 'Giv tegningen et navn (øverst) — den skal gemmes, før opsætningen kan indsættes';
        return;
      }
      const who = unnamed.length === 1 ? 'Ét valgt element har' : `${unnamed.length} valgte elementer har`;
      if (!await askUser(`${who} intet navn. De får navnet "${src.name}" med løbenummer (${src.name}_1, ${src.name}_2 … — numre der allerede er brugt, springes over) og derefter opsætningen.`
        + `${published ? ' Tegningen gemmes og udgives med de nye navne.' : ' Tegningen gemmes og udgives først (også dine andre ændringer).'} Fortsæt?`)) return;
      named = ed?.nameElements(unnamed, src.name) ?? {};
      targets.push(...Object.keys(named));
      if (!(await ensurePublished('opsætningen kan indsættes', true))) return;
    } else if (!(await ensurePublished('opsætningen kan indsættes'))) return;
    busy = true;
    try {
      const base = `/api/drawings/${encodeURIComponent(src.drawingId)}`;
      const rows = await get<SymbolRow[]>(`${base}/symbols`);
      const byId = new Map(rows.map((r) => [r.element, r]));
      const nameOf = (id: string) => byId.get(id)?.name || named[id] || selection.find((x) => x.id === id)?.name || id;
      const taken = targets.filter((t) => byId.get(t)?.configured);
      if (taken.length && !await askUser(`${taken.length === 1 ? `"${nameOf(taken[0])}" har` : `${taken.length} af de valgte har`} allerede en opsætning. Overskriv med opsætningen fra "${src.name}"?`)) return;
      const res = await post<CopyResponse>(`${base}/symbols/${encodeURIComponent(src.element)}/copy`, { targets, overwrite: taken.length > 0 });
      const rep = pasteReport(res, src.name, nameOf);
      await refreshReservedIds();
      const newNames = Object.values(named);
      info = rep.info
        + (newNames.length ? ` Nye navne: ${newNames.length <= 4 ? newNames.join(', ') : `${newNames[0]} … ${newNames[newNames.length - 1]}`}.` : '')
        + (noId ? ` ${noId} element${noId === 1 ? '' : 'er'} uden id er sprunget over.` : '');
      if (rep.problems.length) error = rep.problems.join(' · ');
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  // ---- Farver på de valgte symboler (v0.61.0): én farve skiftes i hele markeringen
  const MAX_COLORS = 12;
  function recolor(from: string, to: string): void {
    if (!ed || from === to) return;
    error = info = '';
    const n = ed.recolorSelection(from, to);
    if (!n) error = `Farven ${from} findes ikke længere i markeringen`;
  }

  // ---- Del et T-stykke/kryds (én sti, fra før v0.68.0) i rør, så hvert rør kan få sit eget løbelys
  async function splitFitting(): Promise<void> {
    const sel = selection.length === 1 ? selection[0] : null;
    const legs = sel?.type ? FITTING_LEGS[sel.type] : undefined;
    if (!ed || !sel || !legs) return;
    error = info = '';
    // en opsætning med animationer på den gamle sti mister dem (stien findes ikke mere) — sig det først
    let lost = 0;
    if (current && sel.name) {
      try {
        const r = await get<{ config: { anims?: { part: string }[] } | null }>(`/api/drawings/${encodeURIComponent(current.id)}/symbols/${encodeURIComponent(sel.id)}/config`);
        lost = (r.config?.anims ?? []).filter((a) => a.part !== 'all').length;
      } catch {
        // symbolet findes ikke i den udgivne version endnu (ingen opsætning at miste)
      }
    }
    const warn = lost ? `\n\n${lost} animation${lost === 1 ? '' : 'er'} på den gamle sti skal vælges igen på et af rørene i guiden (animationer på hele symbolet virker som før).` : '';
    if (!(await askUser(`Del "${sel.name || sel.id}" i ${sel.type === 'kryds' ? 'fire' : 'tre'} rør, så hvert rør kan få sit eget løbelys?${warn}`, { ok: 'Del i rør' }))) return;
    const r = ed.splitFitting(sel.id, legs);
    if (r.error) error = r.error;
    else info = `"${sel.name || sel.id}" er delt i ${r.parts?.length} rør. Gem tegningen, og sæt løbelys på hvert rør i guiden.`;
  }

  // ---- Erstat med symbol (tegnet del → bibliotekssymbol)
  let replaceInfo = $state<SelectionInfo | null>(null);

  // ---- Gem som symbol (v3.28.0): objektet/gruppen gemmes i biblioteket ud fra tegningens gemte version
  let importOpen = $state(false);   // Importér SVG-symboler (v3.31.0)
  let exportFor = $state<{ id: string; name: string; box: { x: number; y: number; w: number; h: number }; markup: string } | null>(null);
  async function openExport(): Promise<void> {
    const sel = selection.length === 1 ? selection[0] : null;
    if (!ed || !sel) return;
    error = '';
    if (!sel.id) {
      error = 'Elementet har intet id — giv det et id under Avanceret, eller gruppér det (Ctrl+G).';
      return;
    }
    const box = ed.elementBox(sel.id);
    if (!box || box.w <= 0 || box.h <= 0) {
      error = 'Objektet har ingen størrelse og kan ikke gemmes som symbol.';
      return;
    }
    if (!(await ensurePublished('objektet kan gemmes i biblioteket'))) return;
    exportFor = { id: sel.id, name: sel.name ?? '', box, markup: ed.elementMarkup(sel.id) };
  }
  let replaceLost = $state({ own: 0, similarBound: 0, similarBoundParts: 0 });
  let boundIds: string[] = [];        // elementer med bindinger i den gemte version — lignende dele med dem springes over

  async function openReplace(): Promise<void> {
    if (!ed) return;
    error = info = '';
    const d = ed.describeSelection();
    if (!d) {
      error = 'Vælg mindst ét element at erstatte';
      return;
    }
    // Bindinger på delens underelementer følger ikke med (kun på selve delen, hvis id'et beholdes)
    let lost = { own: 0, similarBound: 0, similarBoundParts: 0 };
    boundIds = [];
    if (current) {
      try {
        const view = await get<{ bindings: { element: string }[] }>(`/api/drawings/${encodeURIComponent(current.id)}/view`);
        const own = new Set(d.ids);
        const bound = new Set(view.bindings.map((b) => b.element));
        boundIds = [...bound];
        // selve delens id følger med (hvis id'et beholdes); alt andet — underelementer og tekster der fjernes — gør ikke
        lost = {
          own: view.bindings.filter((b) => own.has(b.element) && b.element !== d.id).length,
          similarBound: d.similarGroups.filter((ids) => ids.some((id) => bound.has(id))).length,
          // med "behold id" følger bindingen på selve delen med — kun dele med bundne underelementer/tekster springes over
          similarBoundParts: d.similarGroups.filter((ids) => ids.slice(1).some((id) => bound.has(id))).length,
        };
      } catch (e) {
        error = `Bindinger kunne ikke kontrolleres: ${(e as Error).message}`;
      }
    }
    replaceLost = lost;
    replaceInfo = d;
  }

  function doReplace(o: ReplaceOptions): void {
    if (!ed) return;
    const res = ed.replaceSelected(withName(o.symbol.svg, o.name || o.symbol.label), o.symbol.id,
      { name: o.name || o.symbol.label, namePrefix: o.symbol.label, keepId: o.keepId, stretch: o.stretch, useText: o.useText, similar: o.similar, protectIds: boundIds, apexNative: o.apexNative, axisNative: o.axisNative, mirror: o.mirror });
    replaceInfo = null;
    if (res.error) {
      error = res.error;
      return;
    }
    dirty = true;
    const skipped = res.skipped ? ` ${res.skipped} lignende del${res.skipped === 1 ? '' : 'e'} med bindinger blev sprunget over — erstat dem enkeltvis, hvis de også skal erstattes.` : '';
    info = `${res.replaced} del${res.replaced === 1 ? '' : 'e'} er erstattet med «${o.symbol.label}».${skipped} Ctrl+Z fortryder det i ét trin. Tryk Gem kladde, når du er tilfreds — Overview viser først ændringen, når du udgiver versionen.`;
  }

  function ungroup(): void {
    if (!ed) return;
    const err = ed.ungroupSelected();
    if (err) error = err;
    else {
      error = '';
      dirty = true;
      info = 'Gruppen er opløst — dens dele kan nu vælges enkeltvis.';
    }
  }

  /** Slet den åbne tegning (alle versioner og bindinger) — efter en bekræftelse der viser hvad det rammer. */
  async function removeCurrent(): Promise<void> {
    if (!current) return;
    error = info = '';
    const { id, name } = current;
    try {
      if (!(await deleteDrawingFlow(id))) return;
      drawings = await get<{ id: string; name: string }[]>('/api/drawings');
      startNew(true); // tegningen findes ikke mere — tilbage til en tom, ny tegning
      info = `Tegningen "${name}" er slettet.`;
    } catch (e) {
      error = (e as Error).message;
    }
  }

  async function save(publish: boolean): Promise<void> {
    if (!ed) return;
    error = info = '';
    report = null;
    busy = true;
    try {
      const svg = ed.getSvg();
      if (!current) {
        if (!newName.trim()) throw new Error('Giv tegningen et navn');
        const res = await post<{ drawing: Detail; report: Report }>('/api/drawings', { name: newName.trim(), svg, comment });
        current = res.drawing;
        loadedVersion = res.drawing.active_version;
        report = res.report;
        info = `Tegningen "${res.drawing.name}" er oprettet og udgivet som version 1.`;
        history.replaceState(null, '', `#draw/${res.drawing.id}`);
      } else {
        const res = await post<{ drawing: Detail; version: number; report: Report }>(
          `/api/drawings/${encodeURIComponent(current.id)}/versions`, { svg, comment, activate: publish });
        current = res.drawing;
        loadedVersion = res.version;
        report = res.report;
        info = publish ? `Version ${res.version} er gemt og udgivet — Overview viser den nu.`
          : `Version ${res.version} er gemt som kladde. Overview viser stadig version ${res.drawing.active_version}.`;
      }
      comment = '';
      dirty = false;
      checkBindReminder();
      drawings = await get<{ id: string; name: string }[]>('/api/drawings');
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  async function publishLoaded(): Promise<void> {
    if (!current || loadedVersion === null) return;
    try {
      current = await patch<Detail>(`/api/drawings/${encodeURIComponent(current.id)}`, { active_version: loadedVersion });
      info = `Version ${loadedVersion} er nu udgivet.`;
    } catch (e) {
      error = (e as Error).message;
    }
  }

  function applyId(id: string): void {
    if (!ed || !id) return;
    const err = ed.setSelectedId(id);
    if (err) error = err;
    else {
      error = '';
      dirty = true;
    }
  }

  /** Navn på det valgte element — gemmes i tegningen og er symbolets identitet under Bindinger (resten konfigureres dér). */
  function applyText(attr: 'data-hv-name' | 'data-hv-desc', value: string): void {
    if (!ed) return;
    const err = ed.setSelectedText(attr, value);
    if (err) error = err;
    else {
      error = '';
      dirty = true;
    }
  }

  let symbolFilter = $state('');
  // "Mine symboler" (v0.78.0): brugerens egen sektion øverst, gemt pr. bruger på serveren
  const known = (): Set<string> => new Set(defs().map((s) => s.id));
  let favorites = $state<string[]>([]);
  let favError = $state('');
  async function loadFavorites(): Promise<void> {
    try {
      favorites = knownFavorites((await get<{ symbols: string[] }>('/api/auth/me/palette')).symbols, known());
    } catch (e) {
      favError = `Mine symboler kunne ikke hentes: ${(e as Error).message}`;
    }
  }
  async function saveFavorites(next: string[]): Promise<void> {
    const before = favorites;
    favorites = next;   // vis ændringen med det samme; rul tilbage, hvis serveren afviser
    favError = '';
    try {
      favorites = knownFavorites((await put<{ symbols: string[] }>('/api/auth/me/palette', { symbols: next })).symbols, known());
    } catch (e) {
      favorites = before;
      favError = `Mine symboler kunne ikke gemmes: ${(e as Error).message}`;
    }
  }
  const mine = (): SymbolDef[] => {
    const q = symbolFilter.trim().toLowerCase();
    const all = defs();
    return favorites.map((id) => all.find((s) => s.id === id)).filter((s): s is SymbolDef => !!s && (!q || s.label.toLowerCase().includes(q) || s.hint.toLowerCase().includes(q)));
  };
  // Sektionerne og rækkefølgen kommer fra bibliotekets opdeling (Opsætning › Symboler); egne symboler er med (v3.28.0)
  const symbolsIn = (cat: string): SymbolDef[] => libSymbolsIn(defs(), library.layout, cat, symbolFilter);

  /** Forhåndsvisning: viewBox efter symbolets egen størrelse, så små og store symboler fylder knappen ens. */
  /** Rør og fittings vises i samme målestok, så rørtykkelsen ser ens ud på tværs af knapperne. */
  const fitPreview = (id: string) => (svg: SVGSVGElement): void => {
    try {
      const b = (svg.firstElementChild as SVGGraphicsElement).getBBox();
      svg.setAttribute('viewBox', previewViewBox(b, PIPE_IDS.has(id)));
    } catch {
      // getBBox kan fejle hvis knappen er skjult — standard-viewBox bruges så
    }
  };

  // Display med egne cifre (v2.9.0): 7- eller 11-segment, 1–16 cifre
  let displayKind = $state<'7' | '11'>('7');
  let displayDigits = $state(4);
  function insertDisplay(): void {
    if (!ed) return;
    const kind = displayKind === '11' ? 11 : 7;
    const n = Math.min(MAX_DIGITS, Math.max(MIN_DIGITS, Math.round(Number(displayDigits)) || MIN_DIGITS));
    displayDigits = n;
    ed.insertSymbol(withName(segDisplaySvg(kind, n), ed.uniqueName(`${kind}-segment display`)), `segdisplay${kind}`);
    dirty = true;
    info = `Displayet med ${n} ${n === 1 ? 'ciffer' : 'cifre'} er indsat — tryk "Opsæt symbol (6 trin)" i panelet til højre og vælg det tal-tag, det skal vise.`;
  }

  let selectorLabels = $state('Hånd, 0, Auto');
  let selectorError = $state('');

  /** Omskifter med de positioner brugeren har skrevet (2-8, adskilt med komma). */
  function insertSelector(): void {
    selectorError = '';
    try {
      const svg = selectorSymbol(selectorLabels.split(','));
      if (!ed) return;
      ed.insertSymbol(withName(svg, ed.uniqueName('Omskifter')), 'omskifter');
      dirty = true;
      info = 'Omskifteren er indsat — tryk "Opsæt symbol (6 trin)" i panelet til højre for at koble den til PLC\'en.';
    } catch (e) {
      selectorError = (e as Error).message;
    }
  }

  /** SVG-filer fra computeren ind i tegningen som grupper (v3.32.0). Serveren renser filen; tegningen renses igen ved gem. */
  async function insertSvgFiles(files: File[], at: { x: number; y: number } | null = null): Promise<void> {
    if (!ed) return;
    const svgs = files.filter((f) => /\.svg$/i.test(f.name) || f.type === 'image/svg+xml');
    if (!svgs.length) { error = 'Kun SVG-filer kan sættes ind (.svg)'; return; }
    error = info = '';
    const done: string[] = [];
    const warn: string[] = [];    // advarsler (filen er sat ind)
    const failed: string[] = [];  // filer der ikke kunne sættes ind
    for (const [i, f] of svgs.entries()) {
      if (f.size > 5 * 1024 * 1024) { failed.push(`${f.name}: filen er større end 5 MB`); continue; }
      try {
        const r = await post<{ svg: string; parts: string[]; warnings: string[] }>('/api/library/fragment', { svg: await f.text() });
        if (ed.insertGraphic(r.svg, f.name.replace(/\.svg$/i, ''), at, 0.6, i)) {
          done.push(f.name);
          dirty = true;
        }
        warn.push(...r.warnings.map((w) => `${f.name}: ${w}`));
      } catch (e) {
        failed.push(`${f.name}: ${(e as Error).message}`);
      }
    }
    if (done.length) info = `${done.join(', ')} er sat ind som ${done.length === 1 ? 'en gruppe' : 'grupper'}. Fortryd med Ctrl+Z.`
      + (warn.length ? ` ⚠ ${warn.join(' · ')}` : '');
    if (failed.length) error = failed.join(' · ');
  }
  let svgFileInput = $state<HTMLInputElement>();

  function insert(symbolId: string, at: { x: number; y: number } | null = null): void {
    const s = defs().find((x) => x.id === symbolId);
    if (!ed || !s) return;
    ed.insertSymbol(withName(s.svg, ed.uniqueName(s.label)), s.id, at);
    dirty = true;
    // ingen meddelelse: "Opsæt symbol" står allerede i panelet, og en meddelelse over tegnefladen ville skubbe den ned
  }

  const onBeforeUnload = (e: BeforeUnloadEvent) => {
    if (dirty) e.preventDefault();
  };

  // Tegne-editoren fylder højden ned til sidefoden (mindst 600 px — ellers scrolles siden)
  // Sidepanelet får samme højde som editoren, så symbolbiblioteket ruller for sig selv (v0.75.1); på smalle skærme
  // ligger panelet under tegningen og har sin naturlige højde.
  let aside: HTMLElement;
  let frameBox: HTMLElement;
  const fitFrame = () => {
    if (!frameBox) return;
    const h = Math.max(600, availableHeight(frameBox) - 2);
    editorHeight = h;
    if (aside) aside.style.height = window.matchMedia('(max-width: 900px)').matches ? '' : `${h}px`;
  };
  let stopLayout: (() => void) | null = null;

  onMount(async () => {
    window.addEventListener('beforeunload', onBeforeUnload);
    removeLeaveGuard = setLeaveGuard(async () => !dirty || await askUser('Tegningen har ændringer, der ikke er gemt — de går tabt, hvis du forlader siden. Gem først med "Gem kladde", eller fortsæt og kassér dem.', { ok: 'Kassér og forlad', danger: true }));
    void loadLibrary().then(loadFavorites);   // egne symboler skal kendes, før favoritterne filtreres
    fitFrame();
    stopLayout = onLayoutChange(fitFrame);
    try {
      drawings = await get<{ id: string; name: string }[]>('/api/drawings');
    } catch (e) {
      error = (e as Error).message;
    }
    drawingsLoaded();
  });
  let removeLeaveGuard: (() => void) | null = null;
  onDestroy(() => {
    window.removeEventListener('beforeunload', onBeforeUnload);
    removeLeaveGuard?.();
    stopLayout?.();
  });

  const single = $derived(selection.length === 1 ? selection[0] : null);
  const isActive = $derived(current !== null && loadedVersion === current.active_version);
  // Meddelelser (v4.20.1): systemets beskeder (før en gul bjælke over tegningen) samles her og vises i en boks, når man trykker på
  // *Meddelelser* i den øverste linje — som alarmklokken i topmenuen. Nye beskeder gør knappen orange; advarsler åbner boksen.
  interface Msg { id: number; at: number; text: string; extra: string[]; warn: boolean }
  let messages = $state<Msg[]>([]);
  let unread = $state(0);
  let msgOpen = $state(false);
  // Topmenuen (v6.2.0): menuerne Tegning, version, Forbindelser og kommentaren under Gem og udgiv ▾
  let drawMenu = $state(false), verMenu = $state(false), connMenu = $state(false), saveMenu = $state(false);
  const connErrors = $derived(checkConn && connSummary ? connSummary.open + connSummary.isolated + connSummary.drift : 0);
  const connBadge = $derived(!checkConn || !connSummary ? '' : connErrors ? connErrors : '✓');
  const menuDo = (f: () => unknown) => () => { drawMenu = verMenu = connMenu = false; f(); };
  let msgSeq = 0;
  $effect(() => {
    const text = info;
    if (!text) return;
    untrack(() => {
      const r = report;
      const extra: string[] = [];
      if (r && (Object.keys(r.removed_elements).length || Object.keys(r.removed_attributes).length)) extra.push(`Renset ved gem: ${entries(r.removed_elements)} ${entries(r.removed_attributes)}`);
      if (r?.orphaned_bindings?.length) extra.push(`Bindinger uden element nu: ${r.orphaned_bindings.join(', ')}`);
      const warn = !!r?.orphaned_symbols?.length;
      if (warn) extra.push(`Symboler sat op med guiden, som ikke længere findes: ${r!.orphaned_symbols!.join(', ')} — flyt eller fjern dem under Bindinger`);
      messages = [{ id: ++msgSeq, at: Date.now(), text, extra, warn }, ...messages].slice(0, 30);
      unread++;
      if (warn) msgOpen = true;
      info = '';
    });
  });
  // Opgraderingen v5.1.0 (den gamle symbolmodel fjernet): symboler, der skal sættes op i guiden, står øverst i Meddelelser
  interface MigrationReport { at: number; converted: { drawing: string; element: string; name: string | null }[];
    manual: { drawing: string; element: string; name: string | null; reasons: string[] }[]; removed_bindings: number }
  let migration = $state<MigrationReport | null>(null);
  onMount(async () => {
    try {
      migration = await get<MigrationReport | null>('/api/symbol-migration');
    } catch {
      migration = null;     // (kun teknikere; uden rapport vises intet)
    }
  });
  async function clearMigration(): Promise<void> {
    try {
      await del('/api/symbol-migration');
      migration = null;
    } catch (e) {
      error = (e as Error).message;
    }
  }
  const clock = (t: number) => new Date(t).toLocaleTimeString('da-DK', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const entries = (o: Record<string, number>) => Object.entries(o).map(([k, v]) => `${k} ×${v}`).join(', ');
</script>

<!-- Topmenuen (v6.2.0, PLAN.md): én linje i tre zoner — tegningen | værktøjer | zoom, meddelelser og gem -->
<div class="toolbar" role="toolbar" aria-label="Tegn">
  <div class="zone">
    <Menu label={current ? current.name : 'Ny tegning'} title="Skift tegning, ny tegning, størrelse, bindinger, slet" cls="dname" disabled={!ready} bind:open={drawMenu}>
      <span class="mhead">Tegninger</span>
      <div class="mlist">
        {#each drawings as d (d.id)}
          <button class="mitem" class:cur={d.id === current?.id} onclick={menuDo(() => d.id !== current?.id && open(d.id))}>{d.name}</button>
        {:else}<span class="small muted">Ingen tegninger endnu.</span>{/each}
      </div>
      <hr class="mrule" />
      <button class="mitem" onclick={menuDo(() => startNew())}>+ Ny tegning …</button>
      <button class="mitem" onclick={menuDo(openSize)} title="Tegningens bredde og højde">⤢ Størrelse … <span class="muted">({sizeText(size.w, size.h)})</span></button>
      {#if current}
        <a class="mitem" href={'#editor/' + current.id} onclick={() => (drawMenu = false)}>Bindinger →</a>
        <hr class="mrule" />
        <button class="mitem danger" onclick={menuDo(removeCurrent)} disabled={busy} title="Slet tegningen med alle versioner og bindinger">Slet tegning …</button>
      {/if}
    </Menu>
    {#if current}
      <Menu label={`v${loadedVersion ?? '?'} ${isActive ? 'udgivet' : 'kladde'}`} title="Tegningens versioner — åbn en anden, eller udgiv den åbne" cls={isActive ? 'ver' : 'ver draft'} bind:open={verMenu}>
        <span class="mhead">Versioner</span>
        <div class="mlist">
          {#each [...current.versions].reverse() as v (v.version)}
            <button class="mitem" class:cur={v.version === loadedVersion} onclick={menuDo(() => current && v.version !== loadedVersion && open(current.id, v.version))}>
              v{v.version} <span class="muted">{v.version === current.active_version ? '(udgivet)' : '(kladde)'}</span>{v.comment ? ` — ${v.comment}` : ''}</button>
          {/each}
        </div>
        {#if !isActive}<hr class="mrule" /><button class="primary" onclick={menuDo(publishLoaded)}>Udgiv v{loadedVersion}</button>{/if}
      </Menu>
    {:else}
      <input bind:value={newName} placeholder="Navn på ny tegning" maxlength="80" class="newname" aria-label="Navn på ny tegning" />
    {/if}
    {#if dirty}<span class="dirty" title="Der er ændringer, der ikke er gemt">● <span class="long">ikke gemt</span></span>{/if}
  </div>

  <div class="zone tools">
    <Menu label="Vis" title="Gitter, hjælpelinjer og navne">{@render viewMenu()}</Menu>
    <Menu label="Fang" title="Fang til gitter, objekter, rør og hjælpelinjer">{@render snapMenu()}</Menu>
    <Menu label="Forbindelser" short="Forb." title="Tjek forbindelser: åbne ender, ret, bind" badge={connBadge} good={connErrors === 0}
      hot={connErrors > 0} wide bind:open={connMenu}>{@render connMenuBody()}</Menu>
    <button class:on={flowOpen} onclick={() => (flowOpen = !flowOpen)} disabled={!current}
      title="Flow: hvordan rør og rørstykker viser det beregnede flow på Overview (forbindelsesgrupper)">Flow</button>
  </div>

  <div class="zone right">
    <span class="zoombar" role="group" aria-label="Zoom">
      <button onclick={() => canvasRef?.perform('zoomOut')} disabled={!ready} title="Zoom ud (Ctrl+−)" aria-label="Zoom ud">−</button>
      <span class="zoom">{Math.round(zoomLevel * 100)} %</span>
      <button onclick={() => canvasRef?.perform('zoomIn')} disabled={!ready} title="Zoom ind (Ctrl++)" aria-label="Zoom ind">+</button>
      <button onclick={() => canvasRef?.perform('zoomFit')} disabled={!ready} title="Tilpas til vinduet (Ctrl+0)" aria-label="Tilpas til vinduet">⤢</button>
    </span>
    <Menu label="Meddelelser" short="🔔" title="Systemets beskeder om tegningen (gem, rettelser, advarsler)" badge={unread + (dupNames.length ? 1 : 0) + (migration?.manual.length ? 1 : 0) + (bindReminder ? 1 : 0)} hot={unread > 0 || dupNames.length > 0 || !!migration?.manual.length || bindReminder > 0}
          wide align="right" bind:open={msgOpen} onopen={() => (unread = 0)}>{@render messagesMenu()}</Menu>
    {#if current}
      <button onclick={() => save(false)} disabled={busy || !ready} title="Gem som en ny kladde-version — Overview viser stadig den udgivne"><span class="long">Gem kladde</span><span class="short">Kladde</span></button>
    {/if}
    <span class="split">
      <button class="primary" onclick={() => save(true)} disabled={busy || !ready}>{#if current}<span class="long">Gem og udgiv</span><span class="short">Udgiv</span>{:else}Opret tegning{/if}</button>
      <Menu label="Kommentar til versionen" bare cls="primary caret" align="right" badge={comment.trim() ? '●' : ''} good
        title="Kommentar til versionen, der gemmes" bind:open={saveMenu}>
        <label class="field">Kommentar til versionen
          <input bind:value={comment} placeholder="fx Ny pumpe i kælderen" maxlength="200" onkeydown={(e) => { if (e.key === 'Enter') saveMenu = false; }} />
        </label>
        <span class="small muted">Gemmes med næste <em>Gem kladde</em> eller <em>Gem og udgiv</em>.</span>
      </Menu>
    </span>
  </div>
</div>
{#if symbolEdit}
  <div class="notice row sym-edit" role="status">
    <span>Du retter grafikken for <strong>{symbolEdit.label}</strong>{symbolEdit.own ? '' : ' (indbygget — gemmes som en kopi)'}.
      Ret stregerne og farverne (<em>Opløs</em> gruppen for at rette enkelte dele, <em>Gruppér</em> igen med Ctrl+G), vælg det samlede symbol, og gem.</span>
    <button class="primary" onclick={saveSymbolEdit} disabled={busy || !ready}>Gem i biblioteket{symbolEdit.own ? ' (ny version)' : ' som kopi'}</button>
    <a class="btn" href="#symbols">← Tilbage til biblioteket</a>
  </div>
{/if}
{#if sizeOpen}
  <div class="panel size-panel" role="group" aria-label="Tegningens størrelse">
    <div class="row"><strong>Tegningens størrelse</strong><button class="small close" onclick={() => (sizeOpen = false)} aria-label="Luk">✕</button></div>
    <div class="row wrap">
      <label class="opt">Fast valg
        <select value={presetFor(Number(sizeForm.w), Number(sizeForm.h))?.label ?? ''} onchange={(e) => { const p = SIZE_PRESETS.find((x) => x.label === e.currentTarget.value); if (p) sizeForm = { ...sizeForm, w: String(p.w), h: String(p.h) }; }}>
          <option value="">— egen størrelse —</option>
          {#each SIZE_PRESETS as p (p.label)}<option value={p.label}>{p.label}</option>{/each}
        </select>
      </label>
      <label class="opt">Bredde <input class="num" bind:value={sizeForm.w} inputmode="numeric" /></label>
      <label class="opt">Højde <input class="num" bind:value={sizeForm.h} inputmode="numeric" /></label>
      <button class="primary" onclick={() => applySize(false)}>Brug størrelsen</button>
    </div>
    <div class="row wrap">
      <button onclick={() => applySize(true)}>Tilpas til indholdet</button>
      <label class="opt small">med margen <input class="num" bind:value={sizeForm.margin} inputmode="numeric" /></label>
      <span class="small muted">Flytter tegningen op i hjørnet og gør den præcis stor nok. Overview skalerer altid tegningen til skærmen.</span>
    </div>
    {#if sizeError}<p class="small error">{sizeError}</p>{/if}
  </div>
{/if}

{#snippet viewMenu()}
  <span class="mhead">Gitter</span>
  <div class="mrow">
    <label class="opt"><input type="checkbox" bind:checked={guides.grid} /> Vis gitter</label>
    <label class="opt">afstand
      <select bind:value={guides.step} aria-label="Gitterafstand">{#each GUIDE_STEPS as s}<option value={s}>{s}</option>{/each}</select>
    </label>
  </div>
  <span class="mhead">Hjælpelinjer</span>
  <div class="mrow">
    <label class="opt" title="Hjælpelinjerne gemmes i tegningen, men vises kun her i Tegn — aldrig i Overview"><input type="checkbox" bind:checked={guides.showGuides} /> Vis hjælpelinjer</label>
  </div>
  {#if guides.showGuides}
    <div class="mrow">
      <label class="opt" title="Faste hjælpelinjer med denne afstand over hele tegningen (gemmes i tegningen)">Inddeling
        <select value={guideEvery} onchange={(e) => { ed?.setGuideEvery(Number(e.currentTarget.value)); guideEvery = ed?.getGuides().every ?? 0; }} disabled={!ready} aria-label="Fast inddeling">
          {#each [0, 50, 100, 200, 250] as n}<option value={n}>{n ? n : 'Fra'}</option>{/each}
        </select>
      </label>
      <button class="small" onclick={() => ed?.addGuide('v')} disabled={!ready} title="Ny lodret hjælpelinje midt i det, du ser — træk den på plads">+ Lodret</button>
      <button class="small" onclick={() => ed?.addGuide('h')} disabled={!ready} title="Ny vandret hjælpelinje midt i det, du ser — træk den på plads">+ Vandret</button>
    </div>
  {/if}
  <span class="mhead">Navne i tegningen</span>
  <div class="mrow" title="Viser navnene oven på tegningen (kun her i Tegn — aldrig i Overview, og de gemmes ikke i tegningen)">
    <label class="opt"><input type="checkbox" bind:checked={showNames.symbols} /> symboler</label>
    <label class="opt"><input type="checkbox" bind:checked={showNames.pipes} /> forbindelser</label>
  </div>
{/snippet}

{#snippet connMenuBody()}
  <label class="opt" title="Markerer, hvad der hænger fast i resten af tegningen: grønt = forbundet, rødt = åbne ender (røde prikker). Kun visning i Tegn">
    <input type="checkbox" bind:checked={checkConn} /> Tjek forbindelser</label>
  {#if !checkConn}
    <span class="small muted">Slå tjekket til for at se åbne ender, rette dem og binde forbindelserne (det kræver flowberegningen).</span>
  {:else if connSummary}
    <span class="mhead">Resultat</span>
    <div class="mrow">
      {#if connSummary.open || connSummary.isolated}
        <span class="small" style="color:var(--warn)" title={connSummary.names.join(', ')}>{connSummary.open} åbne, {connSummary.isolated} uden forbindelse</span>
      {:else}<span class="small" style="color:#2e7d32">✓ alt hænger sammen</span>{/if}
      {#if connSummary.drift}<span class="small" style="color:#ef6c00" title="Gemte forbindelser, hvor punkterne er gledet fra hinanden (orange). Ret flytter rør-enden tilbage; klik på den orange prik fjerner forbindelsen">{connSummary.drift} gledet</span>{/if}
      <span class="small muted">{connSummary.bound ? (connSummary.unbound ? `${connSummary.unbound} ikke bundet` : 'alle bundet') : 'ikke bundet endnu'}</span>
    </div>
    {#if connSummary.names.length}<div class="small muted mnames">{connSummary.names.join(', ')}</div>{/if}
    <div class="mrow">
      {#if connMoves.length}
        <button class="small" onclick={fixConnectionsNow} title="Flytter rør-ender, der ligger tæt på (højst {FIX_GAP} enheder) en anden ende eller et tilslutningspunkt, så de sidder sammen. Symboler flyttes aldrig. Kan fortrydes med Ctrl+Z">Ret {connMoves.length}</button>
      {/if}
      {#if connSummary.unbound > 0 || !connSummary.bound}
        <button class="small primary" onclick={bindNow} title="Gem det, der hænger sammen nu, som tegningens forbindelser — så gælder de for tjekket og flowberegningen, også hvis noget senere glider lidt">Bind forbindelser{connSummary.unbound > 0 ? ` (${connSummary.unbound})` : ''}</button>
      {/if}
      <button class="small" onclick={exemptSelected} disabled={!selIds.length} title="Udelad de valgte symboler fra tjekket, så de ikke giver fejl (fx et symbol, der bevidst ikke er tilsluttet). Gemmes med tegningen. Peg på en rød prik: klik = kun det punkt, Skift+klik = hele symbolet">{selAllExempt ? 'Tag valgte med i tjekket' : 'Udelad valgte fra tjekket'}</button>
    </div>
  {/if}
{/snippet}

{#snippet messagesMenu()}
  {#if bindReminder}
    <div class="msg warn">
      <strong>Husk at binde forbindelserne:</strong> {bindReminder} forbindelse{bindReminder === 1 ? '' : 'r'} i tegningen er ikke bundet. Flowberegningen
      (løbelys på Overview) bruger kun bundne forbindelser.
      <div class="mrow"><button class="small primary" onclick={() => { bindNow(); bindReminder = 0; }} disabled={!ready}>Bind nu</button>
        <button class="small" onclick={() => (bindReminder = 0)}>Ikke nu</button>
        <span class="small muted">Gem tegningen igen bagefter.</span></div>
    </div>
  {/if}
  {#if migration}
    <div class="msg" class:warn={migration.manual.length > 0}>
      <strong>Opgradering v5.1.0:</strong> den gamle symbolmodel er fjernet — {migration.converted.length} symbol{migration.converted.length === 1 ? '' : 'er'} er konverteret til guidens opsætning{migration.removed_bindings ? `, ${migration.removed_bindings} gamle bindinger er slettet` : ''}.
      {#if migration.manual.length}
        <div class="small">Disse skal sættes op i guiden (<em>Bindinger › Opsæt symbol</em>):</div>
        <ul class="small">{#each migration.manual as m (m.drawing + m.element)}<li><a href={'#editor/' + m.drawing}>{drawings.find((d) => d.id === m.drawing)?.name ?? m.drawing}</a>: {m.name || m.element}{m.reasons.length ? ` — ${m.reasons[0]}` : ''}</li>{/each}</ul>
      {/if}
      <div class="mrow"><button class="small" onclick={clearMigration}>Ryd rapporten</button></div>
    </div>
  {/if}
  {#if dupNames.length}
    <div class="msg warn">
      Flere symboler har samme navn: {dupNames.map((d) => `"${d.name}" (${d.count})`).join(', ')} — navnene skal være unikke (de bruges fx i
      Trends, ved kopiering af opsætning og i guiden). <button class="small" onclick={fixDuplicates} disabled={!ready}>Giv dem unikke navne</button>
    </div>
  {/if}
  {#each messages as m (m.id)}
    <div class="msg" class:warn={m.warn}>
      <span class="small muted">{clock(m.at)}</span> {m.text}
      {#each m.extra as x}<div class="small muted">{x}</div>{/each}
    </div>
  {:else}
    {#if !dupNames.length && !migration && !bindReminder}<span class="small muted">Ingen meddelelser endnu. Her kommer systemets beskeder, fx når tegningen er gemt eller en rettelse er udført.</span>{/if}
  {/each}
  {#if messages.length}<div class="mrow"><button class="small" onclick={() => (messages = [])}>Ryd meddelelser</button></div>{/if}
{/snippet}

{#snippet snapMenu()}
  <label class="opt"><input type="checkbox" bind:checked={guides.snapGrid} /> Fang til gitter</label>
  <label class="opt" title="Når du slipper et objekt, lægges det kant mod kant eller midte mod midte med nærmeste objekt, hvis det er tæt på"><input type="checkbox" bind:checked={guides.snapObjects} /> Fang til objekter</label>
  <label class="opt" title="Når du flytter et symbol med rør, fanges det, så røret står snorlige ud af det (blå stiplet linje under trækket)"><input type="checkbox" bind:checked={guides.snapPipes} /> Fang rør lige</label>
  <label class="opt" title="Symboler, rør og rør-stykker fanges til hjælpelinjerne"><input type="checkbox" bind:checked={guides.snapGuides} /> Fang til hjælpelinjer</label>
  <hr class="mrule" />
  <label class="opt" title="Træk i et hjørne: bredde og højde ændres i samme forhold. Hold Shift nede for at skalere frit"><input type="checkbox" bind:checked={guides.keepRatio} /> Skalér symmetrisk</label>
{/snippet}


{#if error}<div class="error">{error}</div>{/if}
<div class="layout">
  <div class="frame" bind:this={frameBox}>
    <DrawCanvas height={editorHeight} dropType={SYMBOL_DRAG} ondropsymbol={(id, x, y) => ed && insert(id, ed.docPointAt(x, y))} ondropfiles={(files, x, y) => ed && insertSvgFiles(files, ed.docPointAt(x, y))} onready={(api) => attach(api as ScadaApi)} onupdate={() => inspectRev++} onzoom={(z) => (zoomLevel = z)} bind:this={canvasRef} bar={false}
                hint="{hint.name}: {hint.how} · Drejning i 15°-trin, Shift = fri" />
  </div>

  <aside bind:this={aside}>
    {#snippet selBadge()}{selection.length > 1 ? `${selection.length} valgt` : single ? (single.name || `<${single.tag}>`) : ''}{/snippet}
    {#snippet objBadge()}{objCount}{/snippet}
    <PanelSection id="valgt" title="Valgt element" badge={selection.length ? selBadge : undefined} {...sec('valgt')}>
      {#if !single}
        <p class="muted small">{selection.length > 1 ? `${selection.length} elementer valgt` : 'Vælg et element i tegningen.'}</p>
        {#if selection.length > 1}
          <div class="row"><button class="primary" onclick={() => guarded('Opsæt de valgte samlet', openGroupGuide)} disabled={!ready || busy} title="Rediger tag og animationer for alle de valgte på én gang — guiden redigerer ét af dem, og Gem giver alle opsætningen">Opsæt de valgte samlet ({selection.length})</button></div>
          <div class="row"><button onclick={openReplace} disabled={!ready || busy} title="Erstat de valgte dele samlet med ét symbol — fx en ventil tegnet af flere løse figurer">Erstat markeringen med symbol …</button></div>
          <p class="small muted">Skal de gemmes som ét symbol i biblioteket? Gruppér dem først (Ctrl+G), og vælg gruppen.</p>
          {@render clipRow(false)}
          {@render colorRow()}
        {/if}
      {:else}
        <p class="small muted">&lt;{single.tag}&gt;</p>
        <label class="field">Navn
          <input bind:value={nameInput} maxlength="60" placeholder="fx Ventilator stue"
            onchange={() => applyText('data-hv-name', nameInput)} />
        </label>
        {#if single.name}
          <div class="row"><button class="primary" onclick={openGuide} disabled={busy || !ready}>Opsæt symbol (6 trin)</button></div>
          {#if selectorFix}
            <div class="notice small">
              Tegningen viser {selectorFix.drawn.length} positioner ({selectorFix.drawn.join(', ')}), men opsætningen har {selectorFix.labels.length} ({selectorFix.labels.join(', ')}).
              <button class="small" onclick={() => guarded('Tegn omskifteren', () => redrawSelector())} disabled={busy || !ready}>Tegn omskifteren med {selectorFix.labels.length} positioner</button>
            </div>
          {/if}
          {@render clipRow(true)}
          <p class="small muted">Tag, positioner, animationer og nøglelås sættes i guiden — samme guide findes under <strong>Bindinger</strong>.{!current || dirty ? ' Tegningen gemmes og udgives først.' : ''}</p>
        {:else}
          <div class="row"><button class="primary" onclick={nameAndGuide} disabled={busy || !ready} title="Elementet får et navn, og guiden åbnes">Opsæt symbol (6 trin) …</button></div>
          <p class="small muted">Uden <strong>navn</strong> er elementet kun tegning. Knappen giver det et navn og åbner guiden — eller skriv navnet i feltet ovenfor.</p>
          {#if clip}{@render clipRow(false)}{/if}
        {/if}
        {#if single.tag === 'g' && !single.name && (single.children ?? 0) > 20}
          <p class="small notice">Denne gruppe har {single.children} dele. Opløs den for at vælge delene enkeltvis, så de kan erstattes med symboler.</p>
          <div class="row"><button onclick={ungroup} disabled={!ready}>Opløs gruppen</button></div>
        {/if}
        {#if single.onePath && single.type && FITTING_LEGS[single.type]}
          <div class="row"><button onclick={() => guarded('Del i rør', splitFitting)} disabled={!ready || busy} title="Del T-stykket/krydset i selvstændige rør, så hvert rør kan få sit eget løbelys">Del i rør</button></div>
        {/if}
        <div class="row"><button onclick={openReplace} disabled={!ready || busy} title="Erstat den tegnede del med et symbol fra biblioteket (samme placering, størrelse og drejning)">Erstat med symbol …</button></div>
        <div class="row"><button onclick={() => guarded('Gem som symbol', openExport)} disabled={!ready || busy} title="Gem objektet/gruppen som et nyt symbol i biblioteket — med dele, gradienter og opsætningen fra guiden">Gem som symbol i biblioteket …</button></div>
        {#if single.type && SYMBOLS.some((x) => symbolType(x.id) === single.type)}
          <div class="row"><button onclick={() => gotoSymbols(single?.type ?? null)} title="Åbn symbol-editoren på dette symbol — ret tilslutningspunkterne for symboler, der indsættes fremover">Ret tilslutningspunkter …</button></div>
        {/if}
        {@render colorRow()}
        <details class="adv">
          <summary class="small">Avanceret</summary>
          <label class="field">Id (teknisk)
            <span class="row"><input bind:value={idInput} /><button onclick={() => applyId(idInput.trim())} disabled={!idInput.trim() || idInput === single.id}>Sæt</button></span>
          </label>
        </details>
      {/if}
    </PanelSection>
    <PanelSection id="egenskaber" title="Egenskaber" {...sec('egenskaber')}>
      <Inspector api={ready ? (ed as unknown as InspectApi) : null} rev={inspectRev} keepRatio={guides.keepRatio} />
    </PanelSection>
    <PanelSection id="objekter" title="Objekter" badge={objBadge} {...sec('objekter')}>
      <ObjectTree api={ready ? (ed as unknown as TreeApi) : null} rev={inspectRev} onchange={() => inspectRev++} />
    </PanelSection>
    <PanelSection id="oversigt" title="Symbol-oversigt" {...sec('oversigt')}>
      <SymbolTree drawingId={current?.id ?? null} rev={inspectRev + treeRev} {ready} select={(ids) => ed?.selectByIds(ids) ?? 0}
        onguide={(id, name) => (guideFor = { id, name })} ongroup={(g) => (treeGroup = g)} {unnamed} onname={nameThem} />
    </PanelSection>
    <PanelSection id="symboler" title="Symboler" grow {...sec('symboler')}>
      <div class="sym-head">
        <button class="linkish small" onclick={() => gotoSymbols(null)} title="Åbn symbol-editoren — ret symbolernes tilslutningspunkter">Ret tilslutningspunkter i symbol-editoren →</button>
        <input bind:value={symbolFilter} placeholder="Søg symbol (fx bøjning, kontaktor)" style="width:100%" />
      </div>
      {#if favError}<p class="small error">{favError}</p>{/if}
      <details open>
        <summary>Grupper</summary>
        <SymbolGroups drawingId={current?.id ?? null} {tags} selectedIds={selection.filter((x) => !!x.id).map((x) => x.id)}
          select={(ids) => ed?.selectByIds(ids) ?? 0} />
      </details>
      <details open>
        <summary>Mine symboler <span class="muted small">({favorites.length})</span></summary>
        {#if mine().length}
          <div class="symbols">
            {#each mine() as s (s.id)}{@render tile(s, true)}{/each}
          </div>
        {:else}
          <p class="small muted">{favorites.length ? `Ingen af dine symboler matcher "${symbolFilter}".` : 'Tryk ☆ på et symbol for at lægge det her. Ordn dem med ◀ ▶.'}</p>
        {/if}
      </details>
      {#if library.error}<p class="small error">{library.error}</p>{/if}
      <div class="row lib-import">
        <button class="small" onclick={() => (importOpen = true)} title="Hver SVG-fil bliver ét symbol i biblioteket">Importér SVG-symboler …</button>
        <button class="small" onclick={() => svgFileInput?.click()} disabled={!ready} title="Sæt en SVG-fil ind i tegningen som en gruppe — eller træk filen ind på tegnefladen">Indsæt SVG-fil …</button>
        <input type="file" accept=".svg,image/svg+xml" multiple hidden bind:this={svgFileInput}
               onchange={(e) => { const el = e.currentTarget as HTMLInputElement; void insertSvgFiles(Array.from(el.files ?? [])); el.value = ''; }} />
        <a class="small" href="#symbols">Organisér …</a>
      </div>
      {#each libSections(library.layout) as cat (cat.id)}
        {@const list = symbolsIn(cat.id)}
        {#if list.length}
          <details open>
            <summary>{cat.label} <span class="muted small">({list.length})</span></summary>
            <div class="symbols">
              {#each list as s (s.id)}{@render tile(s, false)}{/each}
            </div>
            {#if cat.id === 'proces'}
              <div class="selector-cfg">
                <label class="small">Display med egne cifre (1–16)
                  <span class="row">
                    <select bind:value={displayKind} aria-label="Type"><option value="7">7-segment</option><option value="11">11-segment</option></select>
                    <input type="number" min="1" max="16" bind:value={displayDigits} style="width:4.5rem" aria-label="Antal cifre" />
                    <button onclick={insertDisplay} disabled={!ready}>Indsæt</button></span>
                </label>
                <p class="small muted">7-segment viser tal; 11-segment også de fleste store bogstaver.</p>
              </div>
            {/if}
            {#if cat.id === 'betjening'}
              <div class="selector-cfg">
                <label class="small">Omskifter med egne positioner (2-8, komma imellem)
                  <span class="row"><input bind:value={selectorLabels} placeholder="fx 1, 2, 3, 4" />
                    <button onclick={insertSelector} disabled={!ready}>Indsæt</button></span>
                </label>
                {#if selectorError}<p class="small error">{selectorError}</p>{/if}
                <p class="small muted">Værdierne bliver 0, 1, 2 … i rækkefølge — kan rettes under Bindinger.</p>
              </div>
            {/if}
          </details>
        {/if}
      {/each}
      {#if libSections(library.layout).every((c) => !symbolsIn(c.id).length)}<p class="small muted">Ingen symboler matcher "{symbolFilter}".</p>{/if}
      <p class="small muted">Symbolerne er grå i normaltilstand (ISA-101). Farve og animation kommer fra bindingerne.</p>
    </PanelSection>
  </aside>
</div>

{#snippet colorRow()}
  {#if colors.length}
    <div class="colors" role="group" aria-label="Farver i markeringen">
      <span class="small"><strong>Farver</strong> <span class="muted">— vælg en ny for at skifte den i {selection.length > 1 ? `alle ${selection.length} valgte` : 'det valgte'}</span></span>
      <div class="swatches">
        {#each colors.slice(0, MAX_COLORS) as c (c.color)}
          <label class="swatch" title="{c.color} — bruges {c.uses} gang{c.uses === 1 ? '' : 'e'}">
            <input type="color" value={c.color} aria-label="Skift farven {c.color}" onchange={(e) => recolor(c.color, e.currentTarget.value)} />
            <span class="small muted">{c.uses}</span>
          </label>
        {/each}
      </div>
      {#if colors.length > MAX_COLORS}<p class="small muted">+ {colors.length - MAX_COLORS} farver mere — vælg færre elementer for at se dem.</p>{/if}
      <p class="small muted">Ctrl+Z fortryder. Animationer (fx farve eller løbelys) kan stadig farve symbolet på Overview.</p>
    </div>
  {/if}
{/snippet}

{#snippet tile(s: SymbolDef, inMine: boolean)}
  {@const fav = favorites.includes(s.id)}
  {@const pos = favorites.indexOf(s.id)}
  <div class="tile">
    <button class="ins" onclick={() => insert(s.id)} disabled={!ready} title="{s.hint} — klik for at indsætte, eller træk ind på tegningen"
            draggable={ready} ondragstart={(e) => { e.dataTransfer?.setData(SYMBOL_DRAG, s.id); if (e.dataTransfer) e.dataTransfer.effectAllowed = 'copy'; }}>
      <svg viewBox="-4 -4 168 152" aria-hidden="true" {@attach fitPreview(s.id)}>{@html s.svg}</svg>
      <span>{s.label}</span>
    </button>
    <button class="star" class:on={fav} onclick={() => saveFavorites(toggleFavorite(favorites, s.id))}
      aria-label={fav ? `Fjern ${s.label} fra Mine symboler` : `Læg ${s.label} i Mine symboler`} title={fav ? 'Fjern fra Mine symboler' : 'Læg i Mine symboler'}>{fav ? '★' : '☆'}</button>
    {#if inMine}
      <button class="mv left" onclick={() => saveFavorites(moveFavorite(favorites, s.id, -1))} disabled={pos <= 0} aria-label="Flyt {s.label} frem" title="Flyt frem">◀</button>
      <button class="mv right" onclick={() => saveFavorites(moveFavorite(favorites, s.id, 1))} disabled={pos === favorites.length - 1} aria-label="Flyt {s.label} tilbage" title="Flyt tilbage">▶</button>
    {/if}
  </div>
{/snippet}

{#snippet clipRow(canCopy: boolean)}
  <div class="row clip">
    {#if canCopy}<button onclick={() => guarded('Kopiér opsætning', copyConfig)} disabled={busy || !ready} title="Husk dette symbols opsætning (tag og animationer), så den kan indsættes i andre symboler">Kopiér opsætning</button>{/if}
    {#if clip}
      <button onclick={() => guarded('Indsæt opsætning', pasteConfig)} disabled={busy || !ready || !clipHere || (single?.id === clip.element)}
        title={!clipHere ? 'Opsætningen er kopieret fra en anden tegning' : `Indsæt opsætningen fra "${clip.name}" i de valgte symboler`}>Indsæt opsætning</button>
    {/if}
  </div>
  {#if clip}<p class="small muted">Kopieret: <strong>{clip.name}</strong>{clipHere ? '' : ' (fra en anden tegning — kan ikke indsættes her)'}</p>{/if}
{/snippet}

{#if replaceInfo}
  <SymbolReplace info={replaceInfo} lostBindings={replaceLost} onreplace={doReplace} onclose={() => (replaceInfo = null)} currentType={single?.type ?? ''} />
{/if}

{#if importOpen}<LibraryImport onclose={() => (importOpen = false)} />{/if}
{#if exportFor && current}
  <SymbolExport drawingId={current.id} version={loadedVersion} element={exportFor.id} box={exportFor.box} markup={exportFor.markup}
    suggested={symbolEdit ? (symbolEdit.own ? symbolEdit.label : `${symbolEdit.label} (egen)`) : exportFor.name}
    onclose={() => (exportFor = null)} ondone={(msg) => (symbolEdit ? afterSymbolSaved(msg) : (() => { exportFor = null; info = msg; })())} />
{/if}

{#if basisChoice}
  {@const bc = basisChoice}
  <GroupBasis groups={bc.groups} unconfigured={bc.members.filter((m) => !m.config)} unnamed={bc.unnamed.length}
    onpick={(m) => guarded('Opsæt de valgte samlet', () => startGroup(m, bc.members, bc.unnamed))} onclose={() => (basisChoice = null)} />
{/if}

{#if groupFor && current}
  {@const gf = groupFor}
  <SymbolGuide drawingId={current.id} element={gf.basis.id} name={gf.basis.name} {tags} group={gf.others}
    onclose={() => (groupFor = null)}
    onremoved={(n, skipped) => { info = `Opsætningen er fjernet fra ${n} symboler${skipped ? ` (${skipped} havde ingen)` : ''}.`; groupFor = null; refreshReservedIds(); }}
    onsaved={() => { info = `${gf.others.length + 1} symboler er opsat ud fra "${gf.basis.name}".`; groupFor = null; refreshReservedIds(); }} />
{/if}

{#if flowOpen && current}
  <FloatWin key="draw.flowwin" title="Flow" onclose={() => (flowOpen = false)}>
    <FlowLive drawingId={current.id} {ready} getSvg={() => (ed ? ed.getSvg() : null)} setOverlay={(d) => ed?.setFlowOverlay(d)} />
    <ConnGroups drawingId={current.id} {ready} selected={selection.map((x) => x.id)} select={(ids) => ed?.selectByIds(ids)}
      ensureSaved={() => ensurePublished('forbindelsesgrupperne gælder den udgivne tegning')} />
  </FloatWin>
{/if}
{#if treeGroup && current}
  <GroupAnims drawingId={current.id} group={treeGroup} {tags} onclose={() => { treeGroup = null; treeRev++; }} />
{/if}
{#if guideFor && current}
  <SymbolGuide drawingId={current.id} element={guideFor.id} name={guideFor.name} {tags} selectorRedraw="auto" linked={isLinked(guideFor.id)}
    onclose={() => { guideFor = null; treeRev++; }}
    onsaved={() => guarded('Opdatér symbolet', async () => {
      info = `Symbolet "${guideFor?.name ?? ''}" er opsat.`;
      guideFor = null;
      treeRev++;
      await refreshReservedIds();
      // omskifter: tegningen følger de nye positioner med det samme (ellers først ved et tryk på knappen)
      await checkSelector();
      if (selectorFix) await redrawSelector(true);
    })} />
{/if}

<style>
  /* Topmenuen (v6.2.0): én linje i tre zoner, der ikke ombrydes; værktøjszonen fylder midten */
  .toolbar { margin-bottom: .35rem; display: flex; align-items: center; gap: .35rem .75rem; flex-wrap: wrap; min-width: 0; }   /* én linje ned til ~1000 px; derunder hele zoner på næste linje */
  .zone { display: flex; align-items: center; gap: .35rem; flex-wrap: nowrap; flex: none; }
  .zone.tools { flex: 1 1 auto; padding-left: .75rem; border-left: 1px solid var(--line); }
  .zone.right { flex: none; padding-left: .75rem; border-left: 1px solid var(--line); }
  .toolbar :global(button.dname) { font-weight: 600; max-width: 16rem; overflow: hidden; text-overflow: ellipsis; }
  .toolbar :global(button.ver) { font-size: .8rem; padding: .2rem .45rem; }
  .toolbar :global(button.ver.draft) { background: #fff8e1; border-color: #e0b062; }
  .newname { width: 12rem; }
  .dirty { color: #ef6c00; font-size: .8rem; white-space: nowrap; }
  .split { display: inline-flex; flex: none; }
  .split > button { border-top-right-radius: 0; border-bottom-right-radius: 0; white-space: nowrap; }
  .split :global(button.caret) { border-top-left-radius: 0; border-bottom-left-radius: 0; border-left: 1px solid rgba(255, 255, 255, .5); padding-left: .35rem; padding-right: .35rem; }
  .short { display: none; }
  @media (max-width: 1250px) { .long { display: none; } .short { display: inline; } .zoombar .zoom { display: none; } }
  .toolbar :global(.mlist) { display: flex; flex-direction: column; max-height: 45vh; overflow: auto; }
  .toolbar :global(.mitem) { text-align: left; border: 0; background: none; padding: .3rem .4rem; border-radius: 4px; color: inherit; text-decoration: none; white-space: nowrap; }
  .toolbar :global(.mitem:hover:not(:disabled)) { background: var(--hover, #eef3f8); }
  .toolbar :global(.mitem.cur) { font-weight: 600; background: var(--hover, #eef3f8); }
  .toolbar :global(.mitem.danger) { color: var(--danger, #c62828); }
  .mnames { max-height: 5rem; overflow: auto; overflow-wrap: anywhere; }
  .size-panel .close { margin-left: auto; }
  .msg { padding: .35rem .5rem; background: #fff8e1; border: 1px solid #e0b062; border-radius: 6px; overflow-wrap: anywhere; }
  .msg.warn { background: #fdecea; border-color: #e57373; }
  .zoombar { display: inline-flex; align-items: center; gap: 4px; }
  .zoombar .zoom { min-width: 3.6em; text-align: center; font-variant-numeric: tabular-nums; }
  /* Værktøjslinjens menuer (Vis, Fang, Meddelelser) skal ligge over tegnefladens lag, men UNDER topmenuen (App.svelte: 40):
     tegnefladen får sin egen stablingskontekst (.layout z-index 0), så dens lag (53–56) ikke konkurrerer med menuerne. */
  .toolbar { position: relative; z-index: 30; }
  .layout {
    position: relative;
    z-index: 0;
    display: grid;
    grid-template-columns: minmax(0, 1fr) 280px;
    gap: 1rem;
    align-items: start;
  }
  @media (max-width: 900px) { .layout { grid-template-columns: minmax(0, 1fr); } }
  .frame { min-width: 0; }
  aside { min-width: 0; }
  /* Sidepanelet har editorens højde (fitFrame): foldbare sektioner; åbne sektioner deler højden og ruller hver for sig,
     symbolbiblioteket får resten (v3.5.0) */
  @media (min-width: 901px) {
    aside { display: flex; flex-direction: column; gap: .5rem; overflow: hidden; }
    aside > :global(.psec) { margin: 0; flex: 0 1 auto; }
    aside > :global(.psec.open) { max-height: 60%; }
    aside > :global(.psec.open.grow) { flex: 1 1 0; max-height: none; min-height: 8rem; }
    .sym-head { position: sticky; top: 0; z-index: 1; background: var(--panel); padding: .2rem 0 .4rem; }
  }
  .linkish { border: 0; background: none; padding: 0 0 .3rem; color: var(--accent); text-decoration: underline; cursor: pointer; }
  .field { display: flex; flex-direction: column; gap: .25rem; font-size: .85rem; color: var(--muted); margin-bottom: .5rem; }
  .field :global(select), .field input { width: 100%; }
  /* minmax(0, 1fr): lange navne må ikke gøre en kolonne bredere end panelet */
  .symbols { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .4rem; }
  .lib-import { gap: .4rem .6rem; align-items: center; flex-wrap: wrap; margin: .2rem 0 .4rem; }
  .symbols .tile { position: relative; min-width: 0; display: flex; }
  .symbols .ins { flex: 1; min-width: 0; display: flex; flex-direction: column; align-items: center; gap: .2rem; padding: .3rem; font-size: .72rem; line-height: 1.15; }
  .symbols span { max-width: 100%; overflow-wrap: anywhere; hyphens: auto; text-align: center; }
  /* ☆/★ i øverste højre hjørne; ◀ ▶ i de nederste hjørner (kun i Mine symboler) */
  .symbols .star, .symbols .mv { position: absolute; padding: 0 .25rem; min-width: 0; line-height: 1.2; font-size: .8rem; background: transparent; border: 0; color: var(--muted); }
  .symbols .star { top: 1px; right: 1px; }
  .symbols .star.on { color: #c58a00; }
  .symbols .star:hover, .symbols .mv:hover:not(:disabled) { color: var(--accent); }
  .symbols .mv { bottom: 1px; font-size: .65rem; }
  .symbols .mv:disabled { opacity: .3; }
  .symbols .mv.left { left: 1px; }
  .symbols .mv.right { right: 1px; }
  details { margin-top: .6rem; }
  .adv { margin-top: .8rem; }
  .clip { margin-top: .4rem; gap: .4rem; }
  .colors { margin-top: .6rem; }
  .swatches { display: flex; flex-wrap: wrap; gap: .35rem; margin: .3rem 0 .2rem; }
  .swatch { display: flex; flex-direction: column; align-items: center; gap: .05rem; cursor: pointer; }
  .swatch input { width: 2.1rem; height: 1.7rem; padding: 0; border: 1px solid var(--line); border-radius: 4px; background: none; cursor: pointer; }
  .selector-cfg { margin-top: .5rem; }
  .selector-cfg input { flex: 1; min-width: 0; }
  summary { cursor: pointer; font-weight: 600; font-size: .9rem; margin-bottom: .4rem; }
  .symbols svg { width: 44px; height: 40px; }
  .size-panel { margin: .25rem 0 .5rem; display: grid; gap: .4rem; }
  .size-panel .num { width: 5.5rem; }
</style>
