<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { ask as askUser } from '../lib/ask';
  import { get, patch, post, put } from '../lib/api';
  import { knownFavorites, moveFavorite, toggleFavorite } from '../lib/palette';
  import { availableHeight, onLayoutChange } from '../lib/canvas';
  import { deleteDrawingFlow } from '../lib/drawingDelete';
  import GroupBasis from '../lib/GroupBasis.svelte';
  import { BUNDLE } from '../lib/staleCheck';
  import SymbolGuide from '../lib/SymbolGuide.svelte';
  import SymbolReplace, { type ReplaceOptions } from '../lib/SymbolReplace.svelte';
  import { configGroups, pasteReport, pasteTargets, type ConfigClip, type ConfigGroup, type CopyResponse, type Member, type SymbolRow } from '../lib/symbolCopy';
  import type { SymbolConfig, SymbolInfo } from '../lib/symbolConfig';
  import type { SelectionInfo } from '../lib/symbolSuggest';
  import { CATEGORIES, FITTING_LEGS, PIPE_IDS, previewViewBox, SYMBOLS, selectorSymbol, withName, type SymbolDef } from '../lib/symbols';

  let { route = 'draw' }: { route?: string } = $props();

  interface Version { version: number; comment: string; created_at: number }
  interface Detail { id: string; name: string; active_version: number; versions: Version[] }
  interface Report { removed_elements: Record<string, number>; removed_attributes: Record<string, number>; element_count: number; orphaned_bindings?: string[] }
  interface Sel { id: string; tag: string; interactive?: boolean; name?: string; desc?: string; children?: number; type?: string; onePath?: boolean }
  interface ScadaApi {
    build?: string;
    ready: Promise<void>;
    load(svg: string): boolean;
    newDrawing(w: number, h: number): void;
    getSvg(): string;
    onSelection(fn: (sel: Sel[]) => void): void;
    onChange(fn: () => void): void;
    setSelectedId(id: string): string;
    setSelectedText(attr: 'data-hv-name' | 'data-hv-desc', value: string): string;
    uniqueName(base: string): string;
    insertSymbol(fragment: string, baseId: string): string;
    setGuides(opts: { grid: boolean; snapGrid: boolean; snapObjects: boolean; step: number }): void;
    describeSelection(): SelectionInfo | null;
    replaceSelected(fragment: string, baseId: string, opts: { name?: string; namePrefix?: string; keepId?: boolean; stretch?: boolean; useText?: boolean; similar?: false | 'same' | 'any'; protectIds?: string[]; apexNative?: number; axisNative?: number; mirror?: boolean }):
      { ok?: boolean; replaced?: number; skipped?: number; ids?: string[]; error?: string };
    ungroupSelected(): string;
    selectionColors(): { color: string; uses: number }[];
    recolorSelection(from: string, to: string): number;
    nameElements(ids: string[], base: string): Record<string, string>;
    setReservedIds(ids: string[]): void;
    splitFitting(id: string, legs: string): { ok?: boolean; removed?: string[]; parts?: string[]; error?: string };
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
  function loadGuides(): { grid: boolean; snapGrid: boolean; snapObjects: boolean; step: number } {
    const fallback = { grid: false, snapGrid: false, snapObjects: false, step: 10 };
    try {
      const raw = JSON.parse(localStorage.getItem('draw.guides') ?? '{}');
      return { grid: !!raw.grid, snapGrid: !!raw.snapGrid, snapObjects: !!raw.snapObjects, step: GUIDE_STEPS.includes(Number(raw.step)) ? Number(raw.step) : 10 };
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
  let guideFor = $state<{ id: string; name: string } | null>(null); // symbol-guiden (6 trin) er åben
  let tags = $state<{ name: string; source: string; unit: string; writable: boolean; plc: string }[]>([]);
  let iframe: HTMLIFrameElement;
  let ed: ScadaApi | null = null;

  async function connect(): Promise<void> {
    const win = iframe.contentWindow as (Window & { scada?: ScadaApi }) | null;
    // Vent på at værtssiden har lavet window.scada
    for (let i = 0; i < 200 && !win?.scada; i++) await new Promise((r) => setTimeout(r, 50));
    if (!win?.scada) {
      error = 'Tegne-editoren kunne ikke indlæses';
      return;
    }
    ed = win.scada;
    if (ed.build !== BUNDLE.build) {
      // browseren har en gammel kopi af tegneeditoren — nye funktioner (fx navngivning ved indsæt) mangler i den
      error = `Tegneeditoren er en ældre version (build ${ed.build ?? 'ukendt'}, siden er build ${BUNDLE.build}). Genindlæs siden med Ctrl+F5.`;
    }
    await ed.ready;
    ed.onSelection((sel) => {
      selection = sel;
      colors = sel.length && ed ? ed.selectionColors() : [];
      idInput = sel.length === 1 ? sel[0].id : '';
      nameInput = sel.length === 1 ? sel[0].name ?? '' : '';
    });
    ed.onChange(() => (dirty = true));
    ready = true;
    const fromRoute = route.split('/')[1];
    if (fromRoute && drawings.some((d) => d.id === fromRoute)) await open(fromRoute);
    else startNew(true);
  }

  async function confirmDiscard(): Promise<boolean> {
    return !dirty || await askUser('Der er ændringer der ikke er gemt. Kassér dem?');
  }

  async function startNew(force = false): Promise<void> {
    if (!ed || (!force && !(await confirmDiscard()))) return;
    ed.newDrawing(1200, 700);
    ed.setReservedIds([]);
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
  const KNOWN = new Set(SYMBOLS.map((s) => s.id));
  let favorites = $state<string[]>([]);
  let favError = $state('');
  async function loadFavorites(): Promise<void> {
    try {
      favorites = knownFavorites((await get<{ symbols: string[] }>('/api/auth/me/palette')).symbols, KNOWN);
    } catch (e) {
      favError = `Mine symboler kunne ikke hentes: ${(e as Error).message}`;
    }
  }
  async function saveFavorites(next: string[]): Promise<void> {
    const before = favorites;
    favorites = next;   // vis ændringen med det samme; rul tilbage, hvis serveren afviser
    favError = '';
    try {
      favorites = knownFavorites((await put<{ symbols: string[] }>('/api/auth/me/palette', { symbols: next })).symbols, KNOWN);
    } catch (e) {
      favorites = before;
      favError = `Mine symboler kunne ikke gemmes: ${(e as Error).message}`;
    }
  }
  const mine = (): SymbolDef[] => {
    const q = symbolFilter.trim().toLowerCase();
    return favorites.map((id) => SYMBOLS.find((s) => s.id === id)).filter((s): s is SymbolDef => !!s && (!q || s.label.toLowerCase().includes(q) || s.hint.toLowerCase().includes(q)));
  };
  const symbolsIn = (cat: string): SymbolDef[] => {
    const q = symbolFilter.trim().toLowerCase();
    return SYMBOLS.filter((s) => s.category === cat && (!q || s.label.toLowerCase().includes(q) || s.hint.toLowerCase().includes(q)));
  };

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

  function insert(symbolId: string): void {
    const s = SYMBOLS.find((x) => x.id === symbolId);
    if (!ed || !s) return;
    ed.insertSymbol(withName(s.svg, ed.uniqueName(s.label)), s.id);
    dirty = true;
    info = 'Symbolet er indsat — tryk "Opsæt symbol (6 trin)" i panelet til højre for at sætte tag, positioner og animationer.';
  }

  const onBeforeUnload = (e: BeforeUnloadEvent) => {
    if (dirty) e.preventDefault();
  };

  // Tegne-editoren fylder højden ned til sidefoden (mindst 600 px, så hele SVG-Edits værktøjslinje ses — ellers scrolles siden)
  // Sidepanelet får samme højde som editoren, så symbolbiblioteket ruller for sig selv (v0.75.1); på smalle skærme
  // ligger panelet under tegningen og har sin naturlige højde.
  let aside: HTMLElement;
  const fitFrame = () => {
    if (!iframe) return;
    const h = Math.max(600, availableHeight(iframe) - 2);
    iframe.style.height = `${h}px`;
    if (aside) aside.style.height = window.matchMedia('(max-width: 900px)').matches ? '' : `${h}px`;
  };
  let stopLayout: (() => void) | null = null;

  onMount(async () => {
    window.addEventListener('beforeunload', onBeforeUnload);
    loadFavorites();
    fitFrame();
    stopLayout = onLayoutChange(fitFrame);
    try {
      drawings = await get<{ id: string; name: string }[]>('/api/drawings');
    } catch (e) {
      error = (e as Error).message;
    }
  });
  onDestroy(() => {
    window.removeEventListener('beforeunload', onBeforeUnload);
    stopLayout?.();
  });

  const single = $derived(selection.length === 1 ? selection[0] : null);
  const isActive = $derived(current !== null && loadedVersion === current.active_version);
  const entries = (o: Record<string, number>) => Object.entries(o).map(([k, v]) => `${k} ×${v}`).join(', ');
</script>

<div class="row toolbar">
  <select value={current?.id ?? ''} onchange={(e) => { const v = (e.currentTarget as HTMLSelectElement).value; if (v) open(v); else startNew(); }} aria-label="Tegning" disabled={!ready}>
    <option value="">— Ny tegning —</option>
    {#each drawings as d}<option value={d.id}>{d.name}</option>{/each}
  </select>
  {#if current}
    <select value={loadedVersion} onchange={(e) => current && open(current.id, Number((e.currentTarget as HTMLSelectElement).value))} aria-label="Version">
      {#each current.versions as v}
        <option value={v.version}>v{v.version}{v.version === current.active_version ? ' (udgivet)' : ' (kladde)'}{v.comment ? ` — ${v.comment}` : ''}</option>
      {/each}
    </select>
    {#if !isActive}<button onclick={publishLoaded}>Udgiv denne version</button>{/if}
  {:else}
    <input bind:value={newName} placeholder="Navn på ny tegning" maxlength="80" />
  {/if}
  <input bind:value={comment} placeholder="Kommentar til versionen" maxlength="200" class="comment" />
  {#if current}
    <button onclick={() => save(false)} disabled={busy || !ready}>Gem kladde</button>
    <button class="primary" onclick={() => save(true)} disabled={busy || !ready}>Gem og udgiv</button>
    <a class="btn" href={'#editor/' + current.id}>Bindinger</a>
    <button class="danger" onclick={removeCurrent} disabled={busy || !ready} title="Slet tegningen med alle versioner og bindinger">Slet tegning</button>
  {:else}
    <button class="primary" onclick={() => save(true)} disabled={busy || !ready}>Opret tegning</button>
  {/if}
  {#if dirty}<span class="badge">ikke gemt</span>{/if}
</div>

<div class="row guides small" role="group" aria-label="Tegnehjælp">
  <strong>Tegnehjælp</strong>
  <label class="opt"><input type="checkbox" bind:checked={guides.grid} /> Vis gitter</label>
  <label class="opt"><input type="checkbox" bind:checked={guides.snapGrid} /> Fang til gitter</label>
  <label class="opt">Gitterafstand
    <select bind:value={guides.step} aria-label="Gitterafstand">{#each GUIDE_STEPS as s}<option value={s}>{s}</option>{/each}</select>
  </label>
  <label class="opt" title="Når du slipper et objekt, lægges det kant mod kant eller midte mod midte med nærmeste objekt, hvis det er tæt på"><input type="checkbox" bind:checked={guides.snapObjects} /> Fang til objekter</label>
  <span class="muted">Rotation sker i 15°-trin — hold <kbd>Shift</kbd> nede for fri rotation</span>
</div>

{#if error}<div class="error">{error}</div>{/if}
{#if info}
  <div class="notice">
    {info}
    {#if report && (Object.keys(report.removed_elements).length || Object.keys(report.removed_attributes).length)}
      <br /><span class="small muted">Renset ved gem: {entries(report.removed_elements)} {entries(report.removed_attributes)}</span>
    {/if}
    {#if report?.orphaned_bindings?.length}<br />Bindinger uden element nu: {report.orphaned_bindings.join(', ')}{/if}
  </div>
{/if}

<div class="layout">
  <iframe bind:this={iframe} src="/svgedit/scada-editor.html?v={BUNDLE.build}" title="Tegne-editor" onload={connect}></iframe>

  <aside bind:this={aside}>
    <section class="panel sel-panel">
      <h3>Valgt element</h3>
      {#if !single}
        <p class="muted small">{selection.length > 1 ? `${selection.length} elementer valgt` : 'Vælg et element i tegningen.'}</p>
        {#if selection.length > 1}
          <div class="row"><button class="primary" onclick={() => guarded('Opsæt de valgte samlet', openGroupGuide)} disabled={!ready || busy} title="Rediger tag og animationer for alle de valgte på én gang — guiden redigerer ét af dem, og Gem giver alle opsætningen">Opsæt de valgte samlet ({selection.length})</button></div>
          <div class="row"><button onclick={openReplace} disabled={!ready || busy} title="Erstat de valgte dele samlet med ét symbol — fx en ventil tegnet af flere løse figurer">Erstat markeringen med symbol …</button></div>
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
          {@render clipRow(true)}
          <p class="small muted">Tag, positioner, animationer og nøglelås sættes i guiden — samme guide findes under <strong>Bindinger</strong>.{!current || dirty ? ' Tegningen gemmes og udgives først.' : ''}</p>
        {:else}
          <p class="small muted">Giv elementet et <strong>navn</strong> for at gøre det til et symbol, der kan konfigureres under <strong>Bindinger</strong>. Uden navn er det kun tegning.</p>
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
        {@render colorRow()}
        <details class="adv">
          <summary class="small">Avanceret</summary>
          <label class="field">Id (teknisk)
            <span class="row"><input bind:value={idInput} /><button onclick={() => applyId(idInput.trim())} disabled={!idInput.trim() || idInput === single.id}>Sæt</button></span>
          </label>
        </details>
      {/if}
    </section>

    <section class="panel sym-panel">
      <div class="sym-head">
        <h3>Symboler</h3>
        <input bind:value={symbolFilter} placeholder="Søg symbol (fx bøjning, kontaktor)" style="width:100%" />
      </div>
      {#if favError}<p class="small error">{favError}</p>{/if}
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
      {#each CATEGORIES as cat (cat.id)}
        {@const list = symbolsIn(cat.id)}
        {#if list.length}
          <details open>
            <summary>{cat.label} <span class="muted small">({list.length})</span></summary>
            <div class="symbols">
              {#each list as s (s.id)}{@render tile(s, false)}{/each}
            </div>
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
      {#if CATEGORIES.every((c) => !symbolsIn(c.id).length)}<p class="small muted">Ingen symboler matcher "{symbolFilter}".</p>{/if}
      <p class="small muted">Symbolerne er grå i normaltilstand (ISA-101). Farve og animation kommer fra bindingerne.</p>
    </section>
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
    <button class="ins" onclick={() => insert(s.id)} disabled={!ready} title={s.hint}>
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
  <SymbolReplace info={replaceInfo} lostBindings={replaceLost} onreplace={doReplace} onclose={() => (replaceInfo = null)} />
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
    onsaved={() => { info = `${gf.others.length + 1} symboler er opsat ud fra "${gf.basis.name}".`; groupFor = null; refreshReservedIds(); }} />
{/if}

{#if guideFor && current}
  <SymbolGuide drawingId={current.id} element={guideFor.id} name={guideFor.name} {tags}
    onclose={() => (guideFor = null)}
    onsaved={() => { info = `Symbolet "${guideFor?.name ?? ''}" er opsat.`; guideFor = null; refreshReservedIds(); }} />
{/if}

<style>
  .toolbar { margin-bottom: .35rem; }
  .guides { margin-bottom: .6rem; flex-wrap: wrap; gap: .3rem 1rem; align-items: center; }
  .guides kbd { border: 1px solid var(--line); border-bottom-width: 2px; border-radius: 3px; padding: 0 .3rem; background: var(--panel-2); font-size: .85em; }
  .comment { flex: 1; min-width: 12rem; }
  .layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 280px;
    gap: 1rem;
    align-items: start;
  }
  @media (max-width: 900px) { .layout { grid-template-columns: minmax(0, 1fr); } }
  iframe {
    width: 100%;
    height: 600px; /* sættes af fitFrame */
    display: block;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: #fff;
  }
  aside { min-width: 0; }
  /* Sidepanelet har editorens højde (fitFrame): "Valgt element" efter behov (højst 55 %), symbolbiblioteket ruller for sig selv */
  @media (min-width: 901px) {
    aside { display: flex; flex-direction: column; gap: .8rem; overflow: hidden; }
    aside > .panel { margin: 0; }
    .sel-panel { flex: 0 1 auto; max-height: 55%; overflow-y: auto; }
    .sym-panel { flex: 1 1 0; min-height: 8rem; overflow-y: auto; padding-top: 0; }
    .sym-head { position: sticky; top: 0; z-index: 1; background: var(--panel); padding: .8rem 0 .4rem; }
  }
  .field { display: flex; flex-direction: column; gap: .25rem; font-size: .85rem; color: var(--muted); margin-bottom: .5rem; }
  .field :global(select), .field input { width: 100%; }
  /* minmax(0, 1fr): lange navne må ikke gøre en kolonne bredere end panelet */
  .symbols { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .4rem; }
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
</style>
