<script lang="ts">
  import { onDestroy, onMount, tick } from 'svelte';
  import { alarmMarks } from '../lib/alarmMark';
  import { mountCharts } from '../lib/chartRender';
  import { applyAlarmBadges, markNavClickable, navTarget, NAV_TARGETS } from '../lib/navSymbols';
  import { loadAcked, pruneAcked, saveAcked, splitProblems } from '../lib/plcAck';
  import MessageSlot from '../lib/MessageSlot.svelte';
  import type { Msg } from '../lib/messages';
  import { get, post, type Binding, type DrawingView, type LiveValue, type PlcSummary } from '../lib/api';
  import { clickFor, parseSetpoint, positionLabel, positions, rangeText, toggleQuestion } from '../lib/actions';
  import { formatValue } from '../lib/animate';
  import { byTag as indexByTag, fitSvg, mountSvg, onLayoutChange, renderAll, renderBinding } from '../lib/canvas';
  import { LiveClient } from '../lib/live';
  import { clearOverlays, drawOverlay } from '../lib/symbolOverlay';
  import { clickAction, clickSide, lockedPosition, needsPin, operateLabel, pickAction, STATE_TXT, stepTarget, type SymbolState, type SymbolView } from '../lib/symbolUi';
  import { panBy, pickDrawing, zoomAt, zoomLevel, type View } from '../lib/viewport';

  let { route = 'overview', canEdit = false, canOperate = false, panel = false, sourceUrl = '', onlogout }: {
    route?: string; canEdit?: boolean; canOperate?: boolean;
    /** Driftpanel: kun tegningen — ingen værktøjslinje; "Log ud" (og evt. tegningerne) i en smal kolonne til venstre. */
    panel?: boolean; sourceUrl?: string; onlogout?: () => void;
  } = $props();

  interface Dialog { binding: Binding; step: 'input' | 'confirm'; input: string; value: number | null; error: string; busy: boolean }
  interface Toast { kind: 'ok' | 'warn' | 'error'; text: string }
  /** Dialog for et symbol efter symbolstandarden (positioner, trykknap eller setpunkt). */
  interface SymDialog {
    element: string; name: string; sym: SymbolView; pick: number | null; pin: string; entry: string;
    writes: { tag: string; value: number; pulse: boolean }[] | null; error: string; busy: boolean;
  }

  let drawings = $state<{ id: string; name: string; start?: boolean; disabled?: boolean }[]>([]);
  let selected = $state('');
  let view = $state<DrawingView | null>(null);
  let error = $state('');
  let plcs = $state<Record<string, PlcSummary>>({});
  // Kvitterede PLC-fejl (v1.9.0): skjules som banner, til PLC'en har været i orden igen
  let acked = $state<Set<string>>(loadAcked());
  function ackPlc(key: string): void { acked = new Set([...acked, key]); saveAcked(acked); }
  function unackAll(): void { acked = new Set(); saveAcked(acked); }
  let connected = $state(false);
  let dialog = $state<Dialog | null>(null);
  let symDialog = $state<SymDialog | null>(null);
  let toast = $state<Toast | null>(null);
  let container: HTMLDivElement;
  let svgRoot: SVGSVGElement | null = null;
  let stopLayout: (() => void) | null = null;

  /** Tegningen fylder den ledige plads i vinduet med sine proportioner (genberegnes ved resize/zoom). */
  const fit = () => fitSvg(svgRoot, container);

  // ---- zoom og panorering (ændrer kun viewBox — tegningen fylder stadig den samme plads)
  let full: View | null = null;
  let cur: View | null = null;
  let zoom = $state(1);
  const pointers = new Map<number, { x: number; y: number }>();
  let dragStart: { x: number; y: number } | null = null;
  let dragged = false; // et træk må ikke udløse klik-handlinger i tegningen
  let pinchDist = 0;

  function applyView(v: View): void {
    if (!svgRoot || !full) return;
    cur = v;
    svgRoot.setAttribute('viewBox', `${v.x} ${v.y} ${v.w} ${v.h}`);
    zoom = zoomLevel(v, full);
  }

  /** Skærmpunkt → tegningens koordinater i det aktuelle udsnit. */
  function toDrawing(clientX: number, clientY: number): { x: number; y: number } | null {
    if (!svgRoot || !cur) return null;
    const r = svgRoot.getBoundingClientRect();
    if (!r.width || !r.height) return null;
    return { x: cur.x + ((clientX - r.left) / r.width) * cur.w, y: cur.y + ((clientY - r.top) / r.height) * cur.h };
  }

  function zoomBy(k: number, clientX?: number, clientY?: number): void {
    if (!full || !cur || !svgRoot) return;
    const r = svgRoot.getBoundingClientRect();
    const p = toDrawing(clientX ?? r.left + r.width / 2, clientY ?? r.top + r.height / 2);
    if (p) applyView(zoomAt(cur, full, k, p.x, p.y));
  }

  const resetView = () => full && applyView(full);

  function onWheel(e: WheelEvent): void {
    if (!full) return;
    e.preventDefault(); // siden scroller ikke — hjulet zoomer i tegningen
    zoomBy(e.deltaY < 0 ? 1.25 : 1 / 1.25, e.clientX, e.clientY);
  }

  function onPointerDown(e: PointerEvent): void {
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.size === 1) {
      dragStart = { x: e.clientX, y: e.clientY };
      dragged = false;
    } else if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinchDist = Math.hypot(a.x - b.x, a.y - b.y);
    }
  }

  function onPointerMove(e: PointerEvent): void {
    const prev = pointers.get(e.pointerId);
    if (!prev || !full || !cur || !svgRoot) return;
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.size === 2) {
      // Knib: zoom om midtpunktet mellem fingrene
      const [a, b] = [...pointers.values()];
      const dist = Math.hypot(a.x - b.x, a.y - b.y);
      if (pinchDist > 0 && dist > 0) zoomBy(dist / pinchDist, (a.x + b.x) / 2, (a.y + b.y) / 2);
      pinchDist = dist;
      dragged = true;
      return;
    }
    if (dragStart && !dragged && Math.hypot(e.clientX - dragStart.x, e.clientY - dragStart.y) < 5) return;
    if (zoom <= 1.0001) return; // hele tegningen vises — intet at panorere
    dragged = true;
    const r = svgRoot.getBoundingClientRect();
    applyView(panBy(cur, full, -((e.clientX - prev.x) / r.width) * cur.w, -((e.clientY - prev.y) / r.height) * cur.h));
  }

  function onPointerUp(e: PointerEvent): void {
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinchDist = 0;
    if (!pointers.size) dragStart = null;
  }
  let toastTimer: ReturnType<typeof setTimeout>;

  const values: Record<string, LiveValue> = {};
  let byTag = new Map<string, Binding[]>();

  let alarmTags = new Map<string, 'unack' | 'ack'>();

  /** Rød alarmmarkering på de dele, der viser et tag i alarm som værdi (v0.87.0: kun Værdi/Niveau — se lib/alarmMark). */
  function markAlarms(): void {
    if (!container || !view) return;
    const marks = alarmMarks(view.bindings, alarmTags);
    for (const element of new Set(view.bindings.map((b) => b.element))) {
      const el = container.querySelector(`#${CSS.escape(element)}`);
      if (!el) continue;
      const st = marks.get(element);
      el.classList.toggle('hv-alarm-unack', st === 'unack');
      el.classList.toggle('hv-alarm-ack', st === 'ack');
    }
  }

  // ---- symbolstandarden: pseudo-tag → symbol (til tilstandsmærker)
  let pseudoOf = new Map<string, string>();

  const symbolsOf = (): Record<string, SymbolView> => view?.symbol_config ?? {};
  let stopCharts: () => void = () => {};
  const shownPos = (element: string): number | null => {
    const v = values[symbolsOf()[element]?.pseudo?.pos ?? '']?.value;
    return typeof v === 'number' ? v : null;
  };
  const symState = (element: string): SymbolState | null => {
    const p = symbolsOf()[element]?.pseudo;
    if (!p) return null;
    const lv = values[p.state];
    return (lv?.value as SymbolState) ?? 'unknown';
  };
  const symName = (element: string): string =>
    svgRoot?.querySelector(`#${CSS.escape(element)}`)?.getAttribute('data-hv-name') || element;

  function overlay(element: string): void {
    const s = symbolsOf()[element];
    if (!svgRoot || !s || s.op !== 'positions') return;
    const remote = values[s.pseudo?.remote ?? '']?.value;
    drawOverlay(svgRoot, element, {
      state: symState(element),
      remoteLabel: typeof remote === 'number' ? s.labels[remote] ?? null : null,
      locked: values[s.pseudo?.locked ?? '']?.value === true,
    });
  }

  const live = new LiveClient(
    (changes) => {
      Object.assign(values, changes);
      for (const name of Object.keys(changes)) for (const b of byTag.get(name) ?? []) render(b);
      for (const name of Object.keys(changes)) {
        const el = pseudoOf.get(name);
        if (el) overlay(el);
      }
    },
    (p, c) => {
      plcs = p;
      connected = c;
      const kept = pruneAcked(acked, p);   // en PLC der er i orden igen: ny fejl vises igen
      if (kept.size !== acked.size) { acked = kept; saveAcked(acked); }
    },
  );

  let alarmSummaryNow: { active: number; unacked: number } | null = null;   // til genvejen til Alarmer (v0.75.0)
  live.onAlarms = (summary, active) => {
    alarmSummaryNow = summary;
    applyAlarmBadges(container, summary);
    const next = new Map<string, 'unack' | 'ack'>();
    for (const a of active) {
      if (!a.tag) continue; // PLC-kommunikationsalarmer vises i banneret, ikke på elementer
      const st = a.state === 'active_ack' ? 'ack' : 'unack';
      if (next.get(a.tag) !== 'unack') next.set(a.tag, st);
    }
    alarmTags = next;
    markAlarms();
  };

  function render(b: Binding): void {
    if (container && view) renderBinding(container, b, values, view.tags);
  }

  async function load(id: string): Promise<void> {
    error = '';
    if (!id) return;
    try {
      view = await get<DrawingView>(`/api/drawings/${encodeURIComponent(id)}/view`);
      selected = id;
      if (location.hash !== `#overview/${id}`) history.replaceState(null, '', `#overview/${id}`);
      await tick();
      svgRoot = mountSvg(container, view.svg, view.symbols);
      const vb = svgRoot?.viewBox.baseVal;
      full = vb && vb.width > 0 && vb.height > 0 ? { x: vb.x, y: vb.y, w: vb.width, h: vb.height } : null;
      cur = full;
      zoom = 1;
      fit();
      try {
        sessionStorage.setItem('overview.last', id); // husk tegningen i denne fane (fx efter et besøg på Tags)
      } catch {
        // Huskes bare ikke — ingen funktion afhænger af det
      }
      if (view.disabled) {
        // Deaktiveret tegning (v1.6.0): offline — tegningen vises som tegnet, uden live-data, bindinger og betjening
        byTag = indexByTag([]);
        pseudoOf = new Map();
        live.subscribe([]);
        stopCharts();
        return;
      }
      byTag = indexByTag(view.bindings.filter((b) => b.tag));
      renderAll(container, view.bindings, values, view.tags);
      markAlarms();
      markNavClickable(svgRoot);
      applyAlarmBadges(svgRoot, alarmSummaryNow);
      clearOverlays(svgRoot);
      pseudoOf = new Map();
      for (const [element, s] of Object.entries(symbolsOf())) {
        for (const name of Object.values(s.pseudo ?? {})) pseudoOf.set(name, element);
        if (s.fault) pseudoOf.set(s.fault, element);
        if (s.op !== 'view') svgRoot?.querySelector(`#${CSS.escape(element)}`)?.classList.add('hv-clickable');
        if (s.op === 'positions' && s.click === 'step') svgRoot?.querySelector(`#${CSS.escape(element)}`)?.classList.add('hv-step');
        overlay(element);
      }
      live.subscribe([...new Set([...byTag.keys(), ...pseudoOf.keys(), ...Object.values(symbolsOf()).map((s) => s.tag ?? '').filter(Boolean)])]);
      stopCharts();
      stopCharts = mountCharts(svgRoot, symbolsOf(), view.tags);   // trendgrafer (v0.91.0)
    } catch (e) {
      view = null;
      error = `Kunne ikke vise tegningen: ${(e as Error).message}`;
    }
  }

  function showToast(kind: Toast['kind'], text: string): void {
    toast = { kind, text };
    clearTimeout(toastTimer);
    if (kind === 'ok') toastTimer = setTimeout(() => (toast = null), 4000);
  }

  /** Første forfader med en klik-handling (klik rammer ofte et barn, fx teksten i en knap). */
  function clickTarget(target: Element | null): Binding | null {
    let el = target;
    while (el && el !== svgRoot && view) {
      if (el.id) {
        const b = clickFor(view.bindings, el.id);
        if (b) return b;
      }
      el = el.parentElement;
    }
    return null;
  }

  /** Første forfader der er et konfigureret symbol (symbolstandarden). */
  function symbolTarget(target: Element | null): string | null {
    let el = target;
    const syms = symbolsOf();
    while (el && el !== svgRoot) {
      if (el.id && syms[el.id] && syms[el.id].op !== 'view') return el.id;
      el = el.parentElement;
    }
    return null;
  }

  async function onCanvasClick(e: MouseEvent): Promise<void> {
    if (view?.disabled) return;   // offline: ingen betjening, ingen genveje
    if (dragged) {
      dragged = false; // afslutningen på et træk/knib er ikke et klik
      return;
    }
    // Genvej (data-hv-nav): åbn Alarmer, Trends eller Energi
    const nav = navTarget(e.target as Element);
    if (nav) {
      // Driftpanelet må åbne Alarmer og Trends (v0.105.0); Energi hører ikke til driftbilledet
      if (panel && nav === 'energy') showToast('error', `${NAV_TARGETS[nav]} kan ikke åbnes på driftpanelet`);
      else location.hash = `#${nav}`;
      return;
    }
    const element = symbolTarget(e.target as Element);
    if (element) {
      await clickSymbol(element, e);
      return;
    }
    const b = clickTarget(e.target as Element);
    if (!b || !view) return;
    if (b.anim === 'click:goto') {
      if (drawings.some((d) => d.id === b.params.drawing)) await load(b.params.drawing);
      else showToast('error', `Tegningen "${b.params.drawing}" findes ikke længere`);
      return;
    }
    if (!canOperate) {
      showToast('error', 'Betjening kræver rollen operatør');
      return;
    }
    if (b.anim === 'click:write') {
      const v = values[b.tag]?.value;
      dialog = { binding: b, step: 'input', input: typeof v === 'number' ? String(v) : '', value: null, error: '', busy: false };
    } else if (b.anim === 'click:select') {
      dialog = { binding: b, step: 'input', input: '', value: null, error: '', busy: false };
    } else if (b.params.confirm) {
      dialog = { binding: b, step: 'confirm', input: '', value: null, error: '', busy: false };
    } else {
      await execute(b, null);
    }
  }

  /** Omskifter: en position er valgt — bekræft eller skriv straks. */
  async function choosePosition(value: number): Promise<void> {
    if (!dialog) return;
    dialog.value = value;
    dialog.error = '';
    if (dialog.binding.params.confirm) {
      dialog.step = 'confirm';
      return;
    }
    await submitDialog();
  }

  async function submitDialog(): Promise<void> {
    if (!dialog || !view) return;
    const b = dialog.binding;
    if (b.anim === 'click:select' && dialog.value === null) return; // vælg en position først
    if (b.anim === 'click:write' && dialog.step === 'input') {
      try {
        dialog.value = parseSetpoint(dialog.input, view.tags[b.tag]);
      } catch (e) {
        dialog.error = (e as Error).message;
        return;
      }
      if (view.tags[b.tag]?.confirm_write) {
        dialog.step = 'confirm';
        dialog.error = '';
        return;
      }
    }
    dialog.busy = true;
    const ok = await execute(b, dialog.value);
    if (ok) dialog = null;
    else if (dialog) dialog.busy = false;
  }

  /** Udfør handlingen. Ved fejl vises serverens/PLC'ens egen fejltekst. */
  async function execute(b: Binding, value: number | null): Promise<boolean> {
    const tag = encodeURIComponent(b.tag);
    const meta = view?.tags[b.tag];
    const name = b.params.title || meta?.description || b.tag;
    try {
      if (b.anim === 'click:write' || b.anim === 'click:select') {
        const r = await post<{ written: number; matches: boolean; warning: string }>(`/api/tags/${tag}/write`, { value });
        const shown = b.anim === 'click:select' ? `"${positionLabel(b.params, r.written) ?? formatValue(r.written, meta)}"` : formatValue(r.written, meta);
        if (r.matches) showToast('ok', `${name} sat til ${shown}`);
        else showToast('warn', r.warning);
      } else if (b.anim === 'click:toggle') {
        const r = await post<{ written: unknown; matches: boolean; warning: string }>(`/api/tags/${tag}/toggle`, {});
        if (r.matches) showToast('ok', `${name}: ${formatValue(r.written, meta)}`);
        else showToast('warn', r.warning);
      } else if (b.anim === 'click:pulse') {
        await post(`/api/tags/${tag}/pulse`, { ms: b.params.ms ?? 500 });
        showToast('ok', `Puls sendt til ${name}`);
      }
      return true;
    } catch (e) {
      if (dialog) dialog.error = (e as Error).message;
      else showToast('error', (e as Error).message);
      return false;
    }
  }

  // ---- symbolstandarden: betjening (serveren afgør — fejlbeskeder vises uændret)
  const symUrl = (element: string, what: string) =>
    `/api/drawings/${encodeURIComponent(view?.id ?? '')}/symbols/${encodeURIComponent(element)}/${what}`;

  // Venstre/højre-betjening: den position der sidst blev bestilt, til PLC'en har svaret (så hurtige tryk tæller videre fra den)
  let lastStep: { element: string; to: number; ts: number } | null = null;

  async function stepSymbol(element: string, s: SymbolView, e: MouseEvent): Promise<void> {
    const node = svgRoot?.querySelector(`#${CSS.escape(element)}`);
    const rect = node?.getBoundingClientRect();
    const shown = shownPos(element);
    const recent = lastStep && lastStep.element === element && Date.now() - lastStep.ts < 4000 && shown !== lastStep.to ? lastStep.to : null;
    const r = rect ? stepTarget(s, recent ?? shown, clickSide(e.clientX, rect)) : ({ kind: 'dialog' } as const);
    if (r.kind === 'limit') {
      showToast('warn', `${symName(element)} står allerede i ${r.end === 'first' ? 'første' : 'sidste'} position`);
      return;
    }
    if (r.kind === 'dialog') {
      symDialog = { element, name: symName(element), sym: s, pick: null, pin: '', entry: '', writes: null, error: '', busy: false };
      return;
    }
    lastStep = { element, to: r.to, ts: Date.now() };
    if (pickAction(s, shown, r.to) === 'operate') {
      if (!(await doOperate(element, r.to, ''))) lastStep = null;
    } else {
      // bekræftelse eller kode kræves: dialogen åbnes med den valgte position (som ved to positioner)
      symDialog = { element, name: symName(element), sym: s, pick: r.to, pin: '', entry: '', writes: null, error: '', busy: false };
      await loadPlan(r.to);
    }
  }

  async function clickSymbol(element: string, e?: MouseEvent): Promise<void> {
    const s = symbolsOf()[element];
    if (!s) return;
    if (!canOperate) {
      showToast('error', 'Betjening kræver rollen operatør');
      return;
    }
    if (e && s.op === 'positions' && s.click === 'step') {
      await stepSymbol(element, s, e);
      return;
    }
    const action = clickAction(s, shownPos(element));
    if (action.kind === 'pulse') await doPulse(element);
    else if (action.kind === 'operate') await doOperate(element, action.to, '');
    else if (action.kind === 'dialog') {
      const v = s.tag ? values[s.tag]?.value : undefined;
      symDialog = { element, name: symName(element), sym: s, pick: action.pick, pin: '', entry: typeof v === 'number' ? String(v) : '',
        writes: null, error: '', busy: false };
      if (action.pick !== null) await loadPlan(action.pick);
    }
  }

  async function loadPlan(position: number): Promise<void> {
    if (!symDialog) return;
    try {
      const r = await get<{ writes: SymDialog['writes'] }>(symUrl(symDialog.element, `plan/${position}`));
      if (symDialog && symDialog.pick === position) symDialog.writes = r.writes;
    } catch (e) {
      if (symDialog) symDialog.error = (e as Error).message;
    }
  }

  async function pickPosition(j: number): Promise<void> {
    if (!symDialog) return;
    symDialog.error = '';
    if (pickAction(symDialog.sym, shownPos(symDialog.element), j) === 'operate') {
      await submitSymbol(j);
      return;
    }
    symDialog.pick = j;
    symDialog.pin = '';
    symDialog.writes = null;
    await loadPlan(j);
  }

  async function doOperate(element: string, position: number, pin: string): Promise<boolean> {
    const s = symbolsOf()[element];
    try {
      const r = await post<{ label: string; writes: unknown[] }>(symUrl(element, 'operate'), pin ? { position, pin } : { position });
      showToast('ok', `${symName(element)}: ${r.label} valgt${r.writes.length ? '' : ' (intet at skrive)'}`);
      return true;
    } catch (e) {
      if (symDialog) symDialog.error = (e as Error).message;
      else showToast('error', `${symName(element)} → ${s?.labels[position] ?? ''}: ${(e as Error).message}`);
      return false;
    }
  }

  async function doPulse(element: string): Promise<boolean> {
    try {
      await post(symUrl(element, 'pulse'), {});
      showToast('ok', `Puls sendt: ${symName(element)}`);
      return true;
    } catch (e) {
      if (symDialog) symDialog.error = (e as Error).message;
      else showToast('error', `${symName(element)}: ${(e as Error).message}`);
      return false;
    }
  }

  async function submitSymbol(position: number | null = null): Promise<void> {
    if (!symDialog || !view) return;
    const d = symDialog;
    d.busy = true;
    d.error = '';
    let ok = false;
    if (d.sym.op === 'pulse') ok = await doPulse(d.element);
    else if (d.sym.op === 'entry') {
      try {
        const value = parseSetpoint(d.entry, d.sym.tag ? view.tags[d.sym.tag] : undefined);
        const r = await post<{ written: number; matches: boolean; warning: string }>(symUrl(d.element, 'entry'), { value });
        if (r.matches) showToast('ok', `${d.name} sat til ${formatValue(r.written, d.sym.tag ? view.tags[d.sym.tag] : undefined)}`);
        else showToast('warn', r.warning);
        ok = true;
      } catch (e) {
        d.error = (e as Error).message;
      }
    } else {
      const to = position ?? d.pick;
      if (to !== null) ok = await doOperate(d.element, to, d.pin.trim());
    }
    if (ok) symDialog = null;
    else if (symDialog) symDialog.busy = false;
  }

  async function acceptPlc(): Promise<void> {
    if (!symDialog) return;
    try {
      const r = await post<{ label: string }>(symUrl(symDialog.element, 'accept'), {});
      showToast('ok', `${symDialog.name}: PLC'ens position "${r.label}" accepteret`);
      symDialog = null;
    } catch (e) {
      if (symDialog) symDialog.error = (e as Error).message;
    }
  }

  function onKey(e: KeyboardEvent): void {
    if (symDialog && !symDialog.busy) {
      if (e.key === 'Escape') symDialog = null;
      return;
    }
    if (!dialog || dialog.busy) return;
    if (e.key === 'Escape') dialog = null;
    else if (e.key === 'Enter') submitDialog();
  }

  onMount(async () => {
    stopLayout = onLayoutChange(fit, container);
    container.addEventListener('wheel', onWheel, { passive: false }); // passive:false — ellers kan siden ikke forhindres i at scrolle
    try {
      drawings = await get<{ id: string; name: string; disabled?: boolean }[]>('/api/drawings');
    } catch (e) {
      error = (e as Error).message;
      return;
    }
    let last: string | null = null;
    try {
      last = sessionStorage.getItem('overview.last');
    } catch {
      // Ingen adgang til sessionStorage — start-tegningen bruges
    }
    selected = pickDrawing(drawings, route.split('/')[1], last);
    await load(selected);
  });

  onDestroy(() => {
    stopCharts();
    stopLayout?.();
    container?.removeEventListener('wheel', onWheel);
    live.close();
    clearTimeout(toastTimer);
  });

  const problems = $derived(splitProblems(plcs, acked));
  // Alle beskeder samles ét sted og vises i MessageSlot (fast plads i værktøjslinjen) — aldrig som bannere, der skubber tegningen
  const messages = $derived.by((): Msg[] => {
    const out: Msg[] = [];
    if (toast) {
      out.push({ id: 'toast', kind: toast.kind === 'error' ? 'error' : toast.kind === 'warn' ? 'warn' : 'ok', text: toast.text,
        action: toast.kind !== 'ok' ? { label: 'OK', run: () => (toast = null) } : undefined });
    }
    if (error) out.push({ id: 'error', kind: 'error', text: error, action: { label: 'OK', run: () => (error = '') } });
    for (const [key, p] of problems.open) {
      out.push({ id: `plc:${key}`, kind: 'error', text: `PLC ${p.name || key}: ${p.message}`,
        action: { label: 'Kvittér', run: () => ackPlc(key), title: "Skjul fejlen her, til PLC'en har været i orden igen (gælder kun denne browser)" } });
    }
    if (!connected) out.push({ id: 'offline', kind: 'warn', text: 'Forbindelsen til SCADA-serveren er afbrudt — værdierne er ikke opdaterede. Forsøger igen …' });
    if (view?.disabled) {
      out.push({ id: 'disabled', kind: 'warn', text: 'Tegningen er deaktiveret — den er offline: ingen live-værdier og ingen betjening. En tekniker kan aktivere den igen under Tegninger.' });
    }
    if (view && view.orphaned_bindings.length) {
      const o = view.orphaned_bindings;
      const list = o.length > 4 ? `${o.slice(0, 4).join(', ')} og ${o.length - 4} flere` : o.join(', ');
      const fixable = !!(canEdit && selected);
      out.push({ id: 'orphans', kind: 'warn',
        text: `Bindinger til elementer der ikke findes i denne version: ${list} — elementerne er slettet i Tegn eller har fået et nyt id, så bindingerne virker ikke.${fixable ? '' : ' Bed en tekniker om at rette det under Bindinger.'}`,
        link: fixable ? { href: `#editor/${selected}`, label: 'Ret under Bindinger → Forsvundne elementer' } : undefined });
    }
    if (problems.acked.length) {
      out.push({ id: 'acked', kind: 'info', text: `Kvitterede PLC-fejl: ${problems.acked.map(([k, p]) => p.name || k).join(', ')}`,
        action: { label: 'Vis igen', run: unackAll } });
    }
    return out;
  });
  const dMeta = $derived(dialog && view ? view.tags[dialog.binding.tag] : undefined);
  const dName = $derived(dialog ? dialog.binding.params.title || dMeta?.description || dialog.binding.tag : '');
  const dLive = $derived(dialog ? values[dialog.binding.tag] : undefined);
</script>

<svelte:window onkeydown={onKey} />

<div class="panel-main" class:is-panel={panel}>
{#if panel}
  <nav class="float-bar" aria-label="Driftpanel">
    <button class="logout" onclick={() => onlogout?.()}>Log ud</button>
    {#if drawings.length > 1}
      {#each drawings as d}
        <button class="drawing" class:active={selected === d.id} onclick={() => load(d.id)}>{d.name}</button>
      {/each}
    {/if}
    {#if !connected}<span class="badge error" title="Forbindelsen til SCADA-serveren er afbrudt">Ingen forbindelse</span>{/if}
  </nav>
  <!-- AGPL-3.0 §13: link til kildekoden skal altid være synligt -->
  <a class="src-float" href={sourceUrl || 'https://github.com/Jangreenlarsen/HypervisionPLC-SCADA'} target="_blank" rel="noopener">AGPL · kildekode</a>
{/if}
{#if !panel}
<div class="toolbar row">
  <select bind:value={selected} onchange={() => load(selected)} aria-label="Vælg tegning">
    {#each drawings as d}<option value={d.id}>{d.name}{d.disabled ? ' (deaktiveret)' : ''}</option>{/each}
  </select>
  {#if canEdit && selected}<a href={'#editor/' + selected}>Redigér bindinger</a>{/if}
  {#if view}
    <span class="zoom row" role="group" aria-label="Zoom">
      <button class="small" onclick={() => zoomBy(1 / 1.5)} disabled={zoom <= 1.0001} title="Zoom ud">−</button>
      <span class="small muted" title="Zoom: musehjul, knib eller knapperne; træk for at flytte rundt">{Math.round(zoom * 100)} %</span>
      <button class="small" onclick={() => zoomBy(1.5)} disabled={zoom >= 19.99} title="Zoom ind">+</button>
      <button class="small" onclick={resetView} disabled={zoom <= 1.0001} title="Vis hele tegningen">Tilpas</button>
    </span>
  {/if}
  <span class="badge {connected ? 'connected' : 'error'}">{connected ? 'Live' : 'Ingen forbindelse'}</span>
  {#each Object.entries(plcs) as [key, p]}
    <span class="badge {p.state}" title={p.message || p.state}>{p.name || key}: {p.state}{p.sse === 'connected' ? ' · SSE' : ''}</span>
  {/each}
  <MessageSlot {messages} />
</div>
{:else}
  <div class="panel-msg"><MessageSlot {messages} /></div>
{/if}

{#if !drawings.length && !error}
  <div class="panel">Ingen tegninger endnu. <a href="#drawings">Upload en SVG-tegning</a> for at komme i gang.</div>
{/if}

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="canvas" class:zoomed={zoom > 1.0001} class:off={view?.disabled} bind:this={container} onclick={onCanvasClick}
  onpointerdown={onPointerDown} onpointermove={onPointerMove} onpointerup={onPointerUp} onpointercancel={onPointerUp}
  onpointerleave={onPointerUp}></div>
{#if panel && zoom > 1.0001}
  <button class="fit-btn" onclick={resetView} title="Vis hele tegningen">Tilpas</button>
{/if}
</div>

{#if symDialog}
  {@const d = symDialog}
  {@const shown = shownPos(d.element)}
  {@const st = symState(d.element)}
  {@const remote = values[d.sym.pseudo?.remote ?? '']?.value}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="backdrop" onclick={() => !d.busy && (symDialog = null)}>
    <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
    <div class="panel dialog" role="dialog" aria-modal="true" aria-label={d.name} tabindex="-1" onclick={(e) => e.stopPropagation()}>
      <h2>{d.name}</h2>
      {#if d.sym.op === 'positions'}
        <p class="muted small">
          Nu: <strong>{shown !== null ? d.sym.labels[shown] : 'ingen position'}</strong>
          {#if st}<span class="state-chip {st}">{STATE_TXT[st]}</span>{/if}
          {#if d.sym.display === 'local'}<span class="small muted"> · lokal visning</span>{/if}
        </p>
        {#if st === 'mismatch' && typeof remote === 'number'}
          <div class="notice">PLC'en viser <strong>{d.sym.labels[remote]}</strong>.
            <button class="small" onclick={acceptPlc} disabled={d.busy}>Acceptér {d.sym.labels[remote]}</button></div>
        {/if}
        <div class="positions" role="group" aria-label="Vælg position">
          {#each d.sym.labels as label, j}
            <button class:primary={d.pick === j} aria-pressed={d.pick === j} class:current={shown === j}
              onclick={() => pickPosition(j)} disabled={d.busy}>
              {#if lockedPosition(d.sym, j)}<span aria-label="låst">🔒 </span>{/if}{label}
            </button>
          {/each}
        </div>
        {#if d.pick !== null}
          {#if needsPin(d.sym, shown, d.pick)}
            <label class="field">Kode (4 cifre)
              <!-- svelte-ignore a11y_autofocus -->
              <input bind:value={d.pin} inputmode="numeric" maxlength="4" autocomplete="off" autofocus
                onkeydown={(e) => e.key === 'Enter' && submitSymbol()} />
            </label>
          {/if}
          {#if d.writes}
            <p class="small muted">{d.writes.length ? 'Skrives:' : 'Intet at skrive — PLC\'en står allerede sådan.'}
              {d.writes.map((w) => `${w.tag} ← ${w.value}${w.pulse ? ' (puls)' : ''}`).join(' · ')}</p>
          {/if}
        {/if}
      {:else if d.sym.op === 'entry'}
        <p class="muted small">Nu: <strong>{formatValue(values[d.sym.tag ?? '']?.value, view?.tags[d.sym.tag ?? ''])}</strong></p>
        <label class="field">Ny værdi
          <!-- svelte-ignore a11y_autofocus -->
          <input bind:value={d.entry} inputmode="decimal" autofocus onkeydown={(e) => e.key === 'Enter' && submitSymbol()} />
        </label>
        <p class="muted small">Tilladt: {rangeText(view?.tags[d.sym.tag ?? ''])}</p>
      {:else}
        <p>Send en puls på {d.sym.pulse_ms ?? 500} ms?</p>
      {/if}
      {#if d.error}<div class="error">{d.error}</div>{/if}
      <div class="row">
        {#if d.sym.op === 'positions'}
          {#if d.pick !== null}
            <button class="primary" onclick={() => submitSymbol()} disabled={d.busy}>{operateLabel(d.sym, shown, d.pick)}</button>
          {/if}
        {:else}
          <button class="primary" onclick={() => submitSymbol()} disabled={d.busy}>{d.sym.op === 'entry' ? 'OK' : 'Send puls'}</button>
        {/if}
        <button onclick={() => (symDialog = null)} disabled={d.busy}>Annullér</button>
      </div>
    </div>
  </div>
{/if}

{#if dialog}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="backdrop" onclick={() => !dialog?.busy && (dialog = null)}>
    <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
    <div class="panel dialog" role="dialog" aria-modal="true" aria-label={dName} tabindex="-1" onclick={(e) => e.stopPropagation()}>
      <h2>{dName}</h2>
      <p class="muted small">
        Nu: <strong>{dialog.binding.anim === 'click:select' ? (positionLabel(dialog.binding.params, dLive?.value) ?? formatValue(dLive?.value, dMeta)) : formatValue(dLive?.value, dMeta)}</strong>
        {#if dLive && dLive.quality !== 'good'}<span class="badge comm_error">{dLive.quality}</span>{/if}
      </p>
      {#if dialog.binding.anim === 'click:write' && dialog.step === 'input'}
        <label class="field">Ny værdi{dMeta?.unit ? ` (${dMeta.unit})` : ''}
          <!-- svelte-ignore a11y_autofocus -->
          <input bind:value={dialog.input} inputmode="decimal" autofocus />
        </label>
        <p class="muted small">Tilladt: {rangeText(dMeta)}</p>
      {:else if dialog.binding.anim === 'click:write'}
        <p>Sæt <strong>{dName}</strong> til <strong>{formatValue(dialog.value, dMeta)}</strong>?</p>
      {:else if dialog.binding.anim === 'click:select' && dialog.step === 'input'}
        <div class="positions" role="group" aria-label="Vælg position">
          {#each positions(dialog.binding.params) as p}
            {@const active = positionLabel(dialog.binding.params, dLive?.value) === p.label}
            <button class:primary={active} aria-pressed={active} onclick={() => choosePosition(p.value)} disabled={dialog.busy}>{p.label}</button>
          {/each}
        </div>
      {:else if dialog.binding.anim === 'click:select'}
        <p>Sæt <strong>{dName}</strong> til <strong>"{positionLabel(dialog.binding.params, dialog.value)}"</strong>?</p>
      {:else if dialog.binding.anim === 'click:toggle'}
        <p>{toggleQuestion(dialog.binding.tag, dLive, dMeta)}</p>
      {:else}
        <p>Send en puls på {dialog.binding.params.ms ?? 500} ms til <strong>{dName}</strong>?</p>
      {/if}
      {#if dialog.error}<div class="error">{dialog.error}</div>{/if}
      <div class="row">
        {#if !(dialog.binding.anim === 'click:select' && dialog.step === 'input')}
          <button class="primary" onclick={submitDialog} disabled={dialog.busy}>
            {dialog.binding.anim === 'click:write' && dialog.step === 'input' ? 'OK' : 'Bekræft'}
          </button>
        {/if}
        {#if (dialog.binding.anim === 'click:write' || dialog.binding.anim === 'click:select') && dialog.step === 'confirm'}
          <button onclick={() => dialog && (dialog.step = 'input')} disabled={dialog.busy}>Tilbage</button>
        {/if}
        <button onclick={() => (dialog = null)} disabled={dialog.busy}>Annullér</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .toolbar { margin-bottom: .75rem; }
  /* Driftpanel (ingen værktøjslinje): beskeder øverst til højre OVER tegningen, så den ikke flytter sig */
  .panel-msg { position: absolute; top: .75rem; right: .75rem; z-index: 6; max-width: 60%; }
  .link-btn { background: none; border: none; padding: 0; color: var(--accent); text-decoration: underline; cursor: pointer; font: inherit; }
  /* Driftpanel: tegningen fylder hele skærmen; knapperne flyder som overlay øverst til venstre */
  .float-bar {
    position: absolute; left: .75rem; top: .75rem; z-index: 5;
    display: flex; flex-wrap: wrap; align-items: center; gap: .4rem; max-width: calc(100% - 1.5rem);
  }
  .float-bar button { padding: .35rem .6rem; font-size: .85rem; box-shadow: 0 2px 8px rgba(0, 0, 0, .25); }
  .float-bar .logout { font-weight: 600; background: #eeeeee; color: #1f1f1f; border-color: #bbbbbb; }
  .float-bar .drawing { background: #4a4a4a; color: #eee; border-color: #5a5a5a; }
  .float-bar .drawing.active { background: var(--accent); border-color: var(--accent); color: #fff; }
  .src-float { position: absolute; left: .75rem; bottom: .5rem; z-index: 5; color: #888; font-size: .7rem; }
  .panel-main.is-panel { position: relative; }
  .fit-btn { position: absolute; right: 1rem; bottom: 1rem; z-index: 4; box-shadow: 0 2px 8px rgba(0, 0, 0, .25); }
  .positions { display: flex; flex-wrap: wrap; gap: .4rem; margin: .4rem 0 .8rem; }
  .positions button { min-width: 4.5rem; padding: .6rem .9rem; font-size: 1rem; }
  .positions button.current { outline: 2px solid var(--ok); outline-offset: 1px; }
  .state-chip { display: inline-block; margin-left: .4rem; padding: 0 .45rem; border-radius: 999px; border: 1px solid var(--line); font-size: .8rem; }
  .state-chip.confirmed { color: var(--ok); border-color: var(--ok); }
  .state-chip.pending { color: var(--warn); border-color: var(--warn); }
  .state-chip.mismatch { color: var(--alarm); border-color: var(--alarm); }
  .canvas {
    background: var(--panel-2);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    padding: .5rem;
    min-height: 200px;
  }
  .canvas { touch-action: none; } /* knib/træk styres af os, ikke browserens side-zoom */
  .canvas.off { filter: grayscale(1); opacity: .55; }
  .canvas.zoomed { cursor: grab; }
  .canvas.zoomed:active { cursor: grabbing; }
  .zoom { gap: .25rem; align-items: center; }
  .zoom button { min-width: 2rem; }
  .canvas :global(svg) {
    display: block;
    width: 100%; /* overskrives af fit() med tegningens præcise størrelse */
    height: auto;
    margin: 0 auto;
  }
  .ok-toast { background: #e8f5e9; border-color: #a5d6a7; }
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, .35);
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding: 12vh 16px 0;
    z-index: 10;
  }
  .dialog { width: 100%; max-width: 380px; box-shadow: 0 8px 30px rgba(0, 0, 0, .25); }
  .field { display: flex; flex-direction: column; gap: .25rem; font-size: .9rem; color: var(--muted); }
  .field input { font-size: 1.3rem; }
</style>
