<script lang="ts">
  import { onDestroy, onMount, tick, untrack } from 'svelte';
  import BackToDrawing from '../lib/BackToDrawing.svelte';
  import { ask as askUser, askText } from '../lib/ask';
  import { api, get, patch } from '../lib/api';
  import { availableHeight, onLayoutChange } from '../lib/canvas';
  import TrendChart, { type ChartSeries } from '../lib/TrendChart.svelte';
  import { align, AVERAGE_CHOICES, assignColors, colorOf, dashOf, groupTags, MAX_SERIES, movingAverage, type Divider, RANGES, type Point } from '../lib/trendData';
  import { FROZEN_DEFAULT_S, affectedPoints, analyze, fillGaps, formatShare, hideSpikes, irregularShare, ISSUE_LABEL, type Issue, type IssueKind } from '../lib/trendAnalysis';
  import { byDrawing, keyFromRoute, symbolKey, symbolSeries, type TrendSymbol } from '../lib/trendSymbols';
  import { applyView, sameView, viewFrom, type TrendView } from '../lib/trendViews';

  let { canEdit = false, route = 'trends' }: { canEdit?: boolean; route?: string } = $props();

  interface InfoTag { name: string; unit: string; description: string; plc: string; trend: boolean;
    trend_interval_s: number; samples: number; oldest: number | null; is_bool: boolean }
  interface Info { retention_days: number; db_size: number; tags: InfoTag[] }
  interface DataResp { start: number; end: number; series: Record<string, Point[]>;
    meta: Record<string, { unit: string; description: string; decimals: number | null }> }

  let info = $state<Info | null>(null);
  let selected = $state<string[]>(loadSelection());
  let colors = $state<Record<string, number>>({});
  let range = $state('1h');
  let customFrom = $state('');
  let customTo = $state('');
  let live = $state(true);
  let filter = $state('');
  let error = $state('');
  let loading = $state(false);
  let resp = $state<DataResp | null>(null);
  // Låst sammen: zoom/scroll i én graf flytter alle grafer
  let linked = $state(false);
  let view = $state<[number, number] | null>(null);
  let resetTick = $state(0);
  function setView(r: [number, number]): void {
    if (!view || Math.abs(view[0] - r[0]) > 0.5 || Math.abs(view[1] - r[1]) > 0.5) view = r;
  }
  function toggleLinked(): void { linked = !linked; view = null; }
  function resetView(): void { view = null; resetTick++; }
  let timer: ReturnType<typeof setInterval> | null = null;
  let enabling = $state('');
  // Analyse (tilvalg): find uregelmæssigheder i tal-kurverne; "skjul spikes" gør dem til huller i visningen (rådata uændret)
  // Stiplede skillelinjer ved hele timer/dage i graferne (til/fra)
  let divider = $state<Divider>(loadDivider());
  function loadDivider(): Divider {
    try {
      const v = localStorage.getItem('trend.divider');
      return v === 'hour' || v === 'day' ? v : 'none';
    } catch {
      return 'none';
    }
  }
  function saveDivider(): void {
    try { localStorage.setItem('trend.divider', divider); } catch { /* huskes bare ikke */ }
  }
  let analyse = $state(loadFlag('trend.analyse'));
  let showIssues = $state(false);   // oversigten over uregelmæssigheder som overlay
  let hide = $state(loadFlag('trend.hideSpikes'));
  // Middelværdi: kurven er den glidende middelværdi over de seneste N timer (0 = rå kurve) — fx 24 timer for en rolig, langsom kurve
  let avgHours = $state(loadAvg());
  function loadAvg(): number {
    try { const v = Number(localStorage.getItem('trend.avgHours')); return Number.isFinite(v) && v > 0 && v <= 720 ? v : 0; } catch { return 0; }
  }
  function setAvg(h: number): void {
    avgHours = Number.isFinite(h) && h > 0 ? Math.min(h, 720) : 0;
    try { localStorage.setItem('trend.avgHours', String(avgHours)); } catch { /* huskes bare ikke */ }
    restartTimer();
    void load();
  }
  let fill = $state(loadFlag('trend.fillGaps'));   // kunstige, blinkende punkter i huller
  let rings = $state(loadFlag('trend.rings', true));   // ring om uregelmæssige punkter i graferne
  /** Hvor længe samme værdi skal stå før den er "fastfrosset" (sekunder; 0 = undersøges ikke). Langsomme følere står stille længe. */
  const FROZEN_CHOICES: { s: number; label: string }[] = [
    { s: 3600, label: '1 time' }, { s: 6 * 3600, label: '6 timer' }, { s: 24 * 3600, label: '1 døgn' }, { s: 3 * 86400, label: '3 døgn' },
    { s: 7 * 86400, label: '7 døgn' }, { s: 0, label: 'Aldrig' },
  ];
  let frozenS = $state(loadFrozen());
  function loadFrozen(): number {
    try {
      const v = Number(localStorage.getItem('trend.frozenS'));
      return FROZEN_CHOICES.some((c) => c.s === v) && localStorage.getItem('trend.frozenS') !== null ? v : FROZEN_DEFAULT_S;
    } catch {
      return FROZEN_DEFAULT_S;
    }
  }
  function saveFrozen(): void {
    try {
      localStorage.setItem('trend.frozenS', String(frozenS));
    } catch {
      // Valget huskes bare ikke.
    }
  }
  let manage = $state(false); // "Administrér historik": slå til/fra og slet pr. tag (tekniker/admin)
  let info2 = $state('');
  let chartsEl = $state<HTMLElement>();
  let room = $state(0); // ledig højde til graferne
  let listEl = $state<HTMLElement>();
  let listMax = $state(0); // tag-listens højde: ned til sidefoden, så siden ikke scroller pga. listen

  /** Tal-grafernes højde: del den ledige plads mellem graferne (til/fra-grafer er faste og lave). */
  // Titel, legend, kant og mellemrum pr. graf + hjælpeteksten — måles på de tegnede grafer (afhænger af skrift/zoom)
  let overhead = $state(90);
  let noteH = $state(30);
  // Dobbeltklik på en graf: vis kun den, i fuld størrelse (dobbeltklik igen eller Esc: tilbage)
  let expandedKey = $state<string | null>(null);
  const keyOf = (unit: string, tags: { name: string }[]) => unit + tags.map((t) => t.name).join(',');
  const fullHeight = $derived(Math.max(260, room - noteH - overhead));
  /** Fjern en graf fra visningen: dens tags fravælges (de kan vælges igen i listen). */
  function removeGroup(tags: { name: string }[]): void {
    const gone = new Set(tags.map((t) => t.name));
    selected = selected.filter((n) => !gone.has(n));
    colors = assignColors(selected, colors);
    saveSelection();
    load();
  }
  function toggleExpand(key: string): void { expandedKey = expanded === key ? null : key; tick().then(measure); }
  const plotHeight = $derived.by(() => {
    const bools = groups.filter(([, t]) => t.every((x) => x.isBool)).length;
    const numbers = groups.length - bools;
    if (!numbers || !room) return 260;
    const free = room - noteH - groups.length * overhead - bools * 160;
    return Math.max(150, Math.min(700, Math.floor(free / numbers)));
  });
  const measure = () => {
    if (chartsEl) room = availableHeight(chartsEl);
    const aside = listEl?.closest('aside');
    if (listEl && aside) {
      // Det der står under listen i panelet (hjælpetekst, polstring, panelets margen) skal også være der
      const below = aside.getBoundingClientRect().bottom - listEl.getBoundingClientRect().bottom
        + (parseFloat(getComputedStyle(aside).marginBottom) || 0);
      listMax = Math.max(160, Math.floor(availableHeight(listEl) - below));
    }
    const fig = chartsEl?.querySelector('figure');
    const plot = fig?.querySelector('.u-wrap');
    if (fig && plot) {
      const margin = parseFloat(getComputedStyle(fig).marginBottom) || 0;
      overhead = Math.ceil(fig.getBoundingClientRect().height + margin - plot.getBoundingClientRect().height);
    }
    const note = chartsEl?.querySelector(':scope > p') as HTMLElement | null;
    if (note) noteH = Math.ceil(note.getBoundingClientRect().height + parseFloat(getComputedStyle(note).marginTop) + parseFloat(getComputedStyle(note).marginBottom));
  };
  // Mål igen når graferne er tegnet (første gang og når antallet af grafer ændres)
  $effect(() => {
    void groups.length;
    void resp;
    tick().then(measure);
  });
  let stopLayout: (() => void) | null = null;

  // ---------------------------------------------------------------- vælg et symbol (v0.80.0)
  let symbols = $state<TrendSymbol[]>([]);
  let symKey = $state('');
  let symBusy = $state(false);
  const chosen = $derived(symbols.find((s) => symbolKey(s) === symKey) ?? null);
  const symSeries = $derived(chosen && info ? symbolSeries(chosen, info.tags, MAX_SERIES) : null);
  const label = (n: string) => tagInfo.get(n)?.description || n;

  /** Vis symbolets kurver (erstatter det valgte); '' = vælg tags selv. */
  // ---- Gemte visninger (v1.16.0): fx alle 8 temperaturfølere i en tank under navnet "Tank temp"; fælles for alle brugere
  let views = $state<TrendView[]>([]);
  let viewName = $state('');
  let viewMsg = $state('');
  const currentView = $derived(views.find((v) => v.name === viewName) ?? null);
  // funktioner (ikke $derived): `assign` erklæres længere nede i filen
  const viewChanged = (): boolean => !!currentView && !sameView(currentView, viewFrom(viewName, selected, assign, range, RANGES.map((r) => r.id)));
  async function loadViews(): Promise<void> {
    try { views = await get<TrendView[]>('/api/trends/views'); } catch (e) { viewMsg = `Visningerne kunne ikke hentes: ${(e as Error).message}`; }
  }
  let viewToken = 0;
  async function chooseView(name: string): Promise<void> {
    viewName = name;
    viewMsg = '';
    const v = views.find((x) => x.name === name);
    if (!v) return;
    if (!info) { viewMsg = 'Trends er ikke klar endnu — vælg visningen igen om et øjeblik.'; return; }
    const token = ++viewToken;
    try {
      // kun tags med historik (som afkrydsningerne i listen); resten meldes
      const r = applyView(v, new Set(info.tags.filter((t) => t.trend || t.samples).map((t) => t.name)), MAX_SERIES);
      const notes = [r.missing.length ? `Ikke tilgængelige (slettet, uden historik eller uden adgang): ${r.missing.map(label).join(', ')}.` : '',
        r.over.length ? `Højst ${MAX_SERIES} kurver ad gangen — ikke vist: ${r.over.map(label).join(', ')}.` : ''].filter(Boolean);
      if (!r.tags.length) { viewMsg = `Ingen af visningens tags kan vises. ${notes.join(' ')}`.trim(); return; }
      const nextRange = RANGES.some((x) => x.id === v.range) ? v.range : range;
      // Data hentes FØR udvalget skiftes, så graferne tegnes med data fra første billede (ikke først tomme og så fyldt op)
      const data = await fetchData(r.tags, nextRange);
      if (token !== viewToken) return;   // en nyere visning blev valgt imens
      symKey = '';
      history.replaceState(null, '', '#trends');
      range = nextRange;
      selected = r.tags;
      assign = r.assign;
      try { localStorage.setItem('trend.assign', JSON.stringify(assign)); } catch { /* huskes bare ikke */ }
      colors = assignColors(selected, {});
      saveSelection();
      resp = data;
      error = '';
      viewMsg = notes.join(' ');
      restartTimer();
    } catch (e) {
      viewMsg = `Visningen "${name}" kunne ikke vises: ${(e as Error).message}`;
    }
  }
  /** Nulstil: ingen tags valgt, ingen visning, graf-valg og zoom ryddet — tilbage til en tom side (periode og indstillinger beholdes). */
  function resetAll(): void {
    viewToken++;   // et igangværende valg af visning skal ikke komme bagefter
    symKey = '';
    history.replaceState(null, '', '#trends');
    selected = [];
    assign = {};
    try { localStorage.setItem('trend.assign', '{}'); } catch { /* huskes bare ikke */ }
    colors = {};
    viewName = '';
    viewMsg = '';
    expandedKey = null;
    saveSelection();
    resetTick++;
    void load();
  }
  async function saveView(asNew: boolean): Promise<void> {
    if (!selected.length) { viewMsg = 'Vælg først de tags, visningen skal vise.'; return; }
    let name = viewName;
    if (asNew || !name) {
      const typed = await askText('Navn på visningen (fx "Tank temp"):', { value: viewName, placeholder: 'Tank temp', ok: 'Gem visning' });
      if (!typed?.trim()) return;
      name = typed.trim();
      const same = views.find((v) => v.name.toLowerCase() === name.toLowerCase());
      if (same && !(await askUser(`Der findes allerede en visning "${same.name}". Erstat den med det nuværende udvalg?`, { ok: 'Erstat', danger: true }))) return;
    }
    try {
      const saved = await api<TrendView>('POST', '/api/trends/views', viewFrom(name, selected, assign, range, RANGES.map((r) => r.id)));
      await loadViews();
      viewName = saved.name;
      viewMsg = `Visningen "${saved.name}" er gemt (${saved.tags.length} tags).`;
    } catch (e) {
      viewMsg = (e as Error).message;
    }
  }
  async function deleteView(): Promise<void> {
    if (!currentView || !(await askUser(`Slet visningen "${currentView.name}"? Tags og historik røres ikke.`, { ok: 'Slet', danger: true }))) return;
    try {
      await api('DELETE', `/api/trends/views?name=${encodeURIComponent(currentView.name)}`);
      viewName = '';
      await loadViews();
      viewMsg = '';
    } catch (e) {
      viewMsg = (e as Error).message;
    }
  }

  function chooseSymbol(key: string, reload = true): void {
    symKey = key;
    history.replaceState(null, '', key ? `#trends/${key}` : '#trends');
    const sym = symbols.find((s) => symbolKey(s) === key);
    if (!sym || !info) return;
    selected = symbolSeries(sym, info.tags, MAX_SERIES).show;
    colors = assignColors(selected, {});
    saveSelection();
    if (reload) load();
  }

  const UNKNOWN = 'Symbolet findes ikke (mere), har ingen opsætning, eller du har ikke adgang til det — vælg tags selv.';
  function routeSymbol(k: string, reload = true): boolean {
    if (!symbols.some((s) => symbolKey(s) === k)) return false;
    chooseSymbol(k, reload);
    return true;
  }
  // Adressen ændret, mens siden er åben (fx skrevet i adresselinjen): vis det symbol
  let mounted = false;
  $effect(() => {
    const k = keyFromRoute(route);
    untrack(() => {
      if (!mounted || !k || k === symKey) return;
      error = routeSymbol(k) ? '' : UNKNOWN;
    });
  });

  /** Tekniker/admin: slå historik til for symbolets tags uden historik — kurverne fyldes op fra nu af. */
  async function enableSymbolTags(): Promise<void> {
    if (!symSeries || !info) return;
    error = '';
    symBusy = true;
    try {
      for (const name of symSeries.missing) {
        await patch(`/api/tags/${encodeURIComponent(name)}`, { trend: true });
        const t = info.tags.find((x) => x.name === name);
        if (t) t.trend = true;
      }
    } catch (e) {
      error = (e as Error).message;   // stop ved første fejl; dem der nåede at blive slået til, bliver vist
    } finally {
      symBusy = false;
      chooseSymbol(symKey);
    }
  }

  function loadFlag(key: string, fallback = false): boolean {
    try {
      const v = localStorage.getItem(key);
      return v === null ? fallback : v === '1';
    } catch {
      return fallback;
    }
  }
  function saveFlag(key: string, on: boolean): void {
    try {
      localStorage.setItem(key, on ? '1' : '0');
    } catch {
      // Valget huskes bare ikke.
    }
  }

  function loadSelection(): string[] {
    try {
      return JSON.parse(localStorage.getItem('trend.selected') ?? '[]');
    } catch {
      return []; // privat vindue / blokeret lager — start blot uden valg
    }
  }

  // Brugerens valg af graf pr. tag (Auto = ingen post) — huskes i browseren
  const MAX_CHARTS = 8;   // højst 8 selvvalgte grafer
  let assign = $state<Record<string, number>>(loadAssign());
  function loadAssign(): Record<string, number> {
    try {
      const v = JSON.parse(localStorage.getItem('trend.assign') ?? '{}');
      return v && typeof v === 'object' ? v : {};
    } catch {
      return {};
    }
  }
  function setAssign(name: string, n: number): void {
    const next = { ...assign };
    if (n > 0) next[name] = n; else delete next[name];
    assign = next;
    try { localStorage.setItem('trend.assign', JSON.stringify(assign)); } catch { /* huskes bare ikke */ }
  }

  function saveSelection(): void {
    try {
      localStorage.setItem('trend.selected', JSON.stringify(selected));
    } catch {
      // Valget huskes bare ikke — ingen funktionalitet afhænger af det.
    }
  }

  function period(rangeId: string = range): { start: number; end: number } {
    if (rangeId === 'custom') {
      const start = Date.parse(customFrom) / 1000;
      const end = Date.parse(customTo) / 1000;
      if (!Number.isFinite(start) || !Number.isFinite(end)) throw new Error('Vælg både fra- og til-tidspunkt');
      return { start, end };
    }
    const r = RANGES.find((x) => x.id === rangeId)!;
    const end = Date.now() / 1000;
    return { start: end - r.seconds, end };
  }

  async function fetchData(names: string[], rangeId: string): Promise<DataResp> {
    const { start, end } = period(rangeId);
    const width = Math.min(1600, Math.max(300, window.innerWidth - 100));
    const win = avgHours * 3600;
    // Middelværdi: hent forløbet før perioden med (til første punkt), regn og skær det ekstra af igen
    const pts = Math.min(2000, Math.round(width / 2 * (end - start + win) / (end - start)));
    const r = await get<DataResp>(`/api/trends/data?tags=${names.map(encodeURIComponent).join(',')}` +
      `&start=${start - win}&end=${end}&points=${pts}`);
    if (!win) return r;
    const series: Record<string, Point[]> = {};
    for (const [n, p] of Object.entries(r.series)) {
      const isBool = info?.tags.find((t) => t.name === n)?.is_bool;
      series[n] = isBool ? p.filter((x) => x[0] >= start) : movingAverage(p, win).filter((x) => x[0] >= start);
    }
    return { ...r, start, series };
  }

  async function load(): Promise<void> {
    if (!selected.length) {
      resp = null;
      return;
    }
    error = '';
    loading = true;
    try {
      resp = await fetchData(selected, range);
    } catch (e) {
      error = (e as Error).message;
    } finally {
      loading = false;
    }
  }

  function toggle(name: string): void {
    if (symKey) {
      symKey = '';   // valget er ikke længere "symbolets kurver"
      history.replaceState(null, '', '#trends');
    }
    if (selected.includes(name)) selected = selected.filter((n) => n !== name);
    else if (selected.length >= MAX_SERIES) {
      error = `Højst ${MAX_SERIES} tags ad gangen — fravælg et først`;
      return;
    } else selected = [...selected, name];
    colors = assignColors(selected, colors);
    saveSelection();
    load();
  }

  function setRange(id: string): void {
    range = id;
    if (id === 'custom') {
      const now = new Date();
      const pad = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
      customTo ||= pad(now);
      customFrom ||= pad(new Date(now.getTime() - 86400000));
      live = false;
    }
    restartTimer();
    load();
  }

  function restartTimer(): void {
    if (timer) clearInterval(timer);
    timer = null;
    const r = RANGES.find((x) => x.id === range);
    // Live-opdatering kun for korte perioder — lange perioder ændrer sig ikke synligt på 5 s
    if (live && r && r.seconds <= 86400) timer = setInterval(load, 5000);
  }

  /** Tekniker/admin: slå historik til direkte herfra og vælg tagget — kurven fyldes op fra nu af. */
  async function enableTrend(t: InfoTag): Promise<void> {
    error = '';
    enabling = t.name;
    try {
      await patch(`/api/tags/${encodeURIComponent(t.name)}`, { trend: true });
      t.trend = true;
      if (!selected.includes(t.name)) toggle(t.name);
    } catch (e) {
      error = (e as Error).message;
    } finally {
      enabling = '';
    }
  }

  /** Slå opsamlingen fra — det gemte bevares (indtil det udløber) og kan stadig vises. */
  async function stopTrend(t: InfoTag): Promise<void> {
    error = '';
    info2 = '';
    enabling = t.name;
    try {
      await patch(`/api/tags/${encodeURIComponent(t.name)}`, { trend: false });
      t.trend = false;
      info2 = `Historik for ${t.description || t.name} gemmes ikke længere. Det gemte kan stadig vises og slettes.`;
    } catch (e) {
      error = (e as Error).message;
    } finally {
      enabling = '';
    }
  }

  /** Tekniker/admin: kurvens navn (v0.81.0) = tagets beskrivelse — vises i stedet for tag-navnet; tomt = tag-navnet. */
  async function rename(t: InfoTag): Promise<void> {
    const v = await askText(`Navn på "${t.name}" i Trends — vises i stedet for tag-navnet. Tomt = tag-navnet.\n\n` +
      'Navnet er tagets beskrivelse, så det ses også under Alarmer og Tags.', { value: t.description, placeholder: t.name, allowEmpty: true });
    if (v === null) return;
    error = '';
    info2 = '';
    enabling = t.name;
    try {
      const row = await patch<{ description: string }>(`/api/tags/${encodeURIComponent(t.name)}`, { description: v.trim() });
      t.description = row.description;
    } catch (e) {
      error = (e as Error).message;
    } finally {
      enabling = '';
    }
  }

  async function deleteHistory(t: InfoTag): Promise<void> {
    const what = t.description || t.name;
    if (!await askUser(`Slet al gemt historik for "${what}" (${t.samples} værdier)? Det kan ikke fortrydes.` +
      (t.trend ? '\n\nOpsamlingen fortsætter — brug "Stop" hvis der heller ikke skal gemmes mere.' : ''))) return;
    error = '';
    info2 = '';
    enabling = t.name;
    try {
      const r = await api<{ deleted: number }>('DELETE', `/api/trends/history/${encodeURIComponent(t.name)}`);
      t.samples = 0;
      t.oldest = null;
      if (!t.trend && selected.includes(t.name)) toggle(t.name); // intet tilbage at vise
      else load();
      info2 = `Slettede ${r?.deleted ?? 0} værdier for ${what}.`;
    } catch (e) {
      error = (e as Error).message;
    } finally {
      enabling = '';
    }
  }

  const noHistory = $derived(!!info && info.tags.length > 0 && !info.tags.some((t) => t.trend || t.samples));

  const exportUrl = $derived.by(() => {
    try {
      const { start, end } = period();
      return `/api/trends/export?tags=${selected.map(encodeURIComponent).join(',')}&start=${start}&end=${end}`;
    } catch {
      return '';
    }
  });

  const tagInfo = $derived(new Map((info?.tags ?? []).map((t) => [t.name, t])));
  const groups = $derived(groupTags(selected.filter((n) => tagInfo.has(n)).map((n) => ({
    name: n, unit: tagInfo.get(n)!.unit, isBool: tagInfo.get(n)!.is_bool,
  })), assign));
  /** Grafens titel: kurvernes navne (tagget "navn"-parameter, ellers tag-navnet) og enheden. */
  function chartTitle(tags: { name: string }[]): string {
    const names = tags.map((t) => label(t.name)).join(', ');
    const unit = chartUnit(tags);
    return unit ? `${names} (${unit})` : names;
  }
  /** Y-aksens enhed: den fælles enhed for tal-kurverne i grafen (blandede enheder → ingen). */
  function chartUnit(tags: { name: string; isBool?: boolean }[]): string {
    if (tags.every((t) => t.isBool)) return '';
    const units = new Set(tags.filter((t) => !t.isBool).map((t) => tagInfo.get(t.name)?.unit ?? ''));
    return units.size === 1 ? [...units][0] : '';
  }
  const shown = $derived((info?.tags ?? []).filter((t) => !filter || `${t.name} ${t.description}`.toLowerCase().includes(filter.toLowerCase())));
  const expanded = $derived(expandedKey && groups.some(([u, t]) => keyOf(u, t) === expandedKey) ? expandedKey : null);

  /** Fund pr. tag (kun tal-kurver; til/fra analyseres ikke). Tom når analysen er slået fra. */
  const issues = $derived.by(() => {
    const out: Record<string, Issue[]> = {};
    if (!analyse || !resp) return out;
    for (const n of selected) {
      if (tagInfo.get(n)?.is_bool) continue;
      const found = analyze(resp.series[n] ?? [], { frozenMinS: frozenS > 0 ? frozenS : null });
      if (found.length) out[n] = found;
    }
    return out;
  });
  const issueTotals = $derived(Object.entries(issues).map(([n, list]) => {
    const counts: Partial<Record<IssueKind, number>> = {};
    for (const i of list) counts[i.kind] = (counts[i.kind] ?? 0) + 1;
    const total = resp?.series[n]?.length ?? 0, affected = Math.min(total, affectedPoints(list));
    return {
      name: n, affected, total,
      text: (Object.entries(counts) as [IssueKind, number][]).map(([k, c]) => `${c} × ${ISSUE_LABEL[k].toLowerCase()}`).join(', '),
      share: formatShare(irregularShare(affected, total)),
    };
  }));
  /** Samlet andel over alle analyserede kurver (kun tal-kurver; en kurve uden fund tæller med i nævneren). */
  const overall = $derived.by(() => {
    if (!analyse || !resp) return null;
    let affected = 0, total = 0;
    for (const n of selected) {
      if (tagInfo.get(n)?.is_bool) continue;
      total += resp.series[n]?.length ?? 0;
      affected += Math.min(resp.series[n]?.length ?? 0, affectedPoints(issues[n] ?? []));
    }
    return total ? { affected, total, share: formatShare(irregularShare(affected, total)) } : null;
  });

  function chartFor(names: { name: string; isBool?: boolean }[]): { series: ChartSeries[]; data: ReturnType<typeof align> } {
    const filled = names.map((t) => {
      const raw = resp?.series[t.name] ?? [];
      const base = hide && issues[t.name] ? hideSpikes(raw, issues[t.name]) : raw;
      return fill && !t.isBool ? fillGaps(base) : { points: base, synthetic: undefined };
    });
    const series = names.map((t, i) => ({
      synthetic: filled[i].synthetic,
      name: t.name,
      label: tagInfo.get(t.name)?.description || t.name,
      colorIndex: colors[t.name] ?? 0,
      isBool: Boolean(t.isBool),
      decimals: resp?.meta[t.name]?.decimals ?? null,
      issues: rings ? issues[t.name] : undefined,
    }));
    const pts = filled.map((f) => f.points);
    return { series, data: align(pts, names.map((t) => Boolean(t.isBool))) };
  }

  onMount(async () => {
    try {
      info = await get<Info>('/api/trends/info');
      selected = selected.filter((n) => info!.tags.some((t) => t.name === n));
      colors = assignColors(selected, {});
    } catch (e) {
      error = (e as Error).message;
    }
    void loadViews();
    try {
      symbols = await get<TrendSymbol[]>('/api/trends/symbols');
      const k = keyFromRoute(route);
      if (k) {
        if (!routeSymbol(k, false)) error = UNKNOWN;   // hentes nedenfor
      }
      // Uden tekniker-rettighed vælges tags ikke frit: start med det første opsatte symbol
      if (!canEdit && !symKey && symbols.length) chooseSymbol(symbolKey(symbols[0]), false);
    } catch (e) {
      error = `Symbolerne kunne ikke hentes: ${(e as Error).message}`;
    }
    mounted = true;
    restartTimer();
    load();
    measure();
    stopLayout = onLayoutChange(measure);
  });
  onDestroy(() => {
    if (timer) clearInterval(timer);
    stopLayout?.();
  });
</script>

<svelte:window onkeydown={(e) => { if (e.key === 'Escape' && expanded) expandedKey = null; }} />

<div class="row toolbar">
  <BackToDrawing />
  {#each RANGES as r}
    <button class:primary={range === r.id} onclick={() => setRange(r.id)}>{r.label}</button>
  {/each}
  <button class:primary={range === 'custom'} onclick={() => setRange('custom')}>Vælg periode</button>
  {#if range === 'custom'}
    <input type="datetime-local" bind:value={customFrom} onchange={load} aria-label="Fra" />
    <input type="datetime-local" bind:value={customTo} onchange={load} aria-label="Til" />
  {:else}
    <label class="row small"><input type="checkbox" bind:checked={live} onchange={restartTimer} /> Live</label>
  {/if}
  {#if selected.length && exportUrl}<a class="btn" href={exportUrl} download>CSV</a>{/if}
  <label class="row small" title="Stiplede lodrette linjer ved hele timer eller dage i graferne">Skillelinjer
    <select bind:value={divider} onchange={saveDivider} aria-label="Skillelinjer">
      <option value="none">Fra</option><option value="hour">Pr. time</option><option value="day">Pr. dag</option>
    </select>
  </label>
  <label class="row small" title="Vis kurven som glidende middelværdi over de seneste timer — en rolig kurve for langsomme forløb. Kun visning; de gemte data og CSV er uændrede. Til/fra-kurver røres ikke">Middel over
    <select value={AVERAGE_CHOICES.some((c) => c.hours === avgHours) ? avgHours : 'own'} onchange={(e) => { const v = e.currentTarget.value; setAvg(v === 'own' ? (avgHours || 2) : Number(v)); }} aria-label="Middel over">
      {#each AVERAGE_CHOICES as c}<option value={c.hours}>{c.label}</option>{/each}
      <option value="own">Egen tid …</option>
    </select>
    {#if !AVERAGE_CHOICES.some((c) => c.hours === avgHours)}
      <input type="number" min="0.1" max="720" step="0.5" value={avgHours} style="width:5em" aria-label="Timer" onchange={(e) => setAvg(Number(e.currentTarget.value))} /> timer
    {/if}
  </label>
  <label class="row small" title="Udfylder huller (ingen data) med kunstige, interpolerede punkter, der blinker, så de kan kendes fra målte data. Kun visning — de gemte data ændres ikke"><input type="checkbox" bind:checked={fill} onchange={() => saveFlag('trend.fillGaps', fill)} /> Udfyld huller (blinker)</label>
  <label class="row small" title="Find spikes, urealistiske spring, fastfrosne værdier og huller i tal-kurverne"><input type="checkbox" bind:checked={analyse} onchange={() => saveFlag('trend.analyse', analyse)} /> Analysér data</label>
  {#if analyse && resp && selected.length}
    <button class:primary={showIssues} onclick={() => (showIssues = !showIssues)} aria-pressed={showIssues} title="Vis oversigten over fundne uregelmæssigheder oven på skærmen">Uregelmæssigheder{issueTotals.length ? ` (${issueTotals.length})` : ''}</button>
  {/if}
  {#if analyse}
    <label class="row small" title="Skjul ringene i graferne — fundene står stadig i listen under graferne"><input type="checkbox" bind:checked={rings} onchange={() => saveFlag('trend.rings', rings)} /> Vis ringe</label>
    <label class="row small" title="Samme værdi så længe markeres som fastfrosset. Langsomme følere (fx temperatur) står stille længe, så vælg en lang tid for dem">Fastfrosset efter
      <select bind:value={frozenS} onchange={saveFrozen} aria-label="Fastfrosset efter">{#each FROZEN_CHOICES as c}<option value={c.s}>{c.label}</option>{/each}</select>
    </label>
    <label class="row small" title="Udfylder enkeltstående spikes med interpolerede værdier i visningen — de gemte data ændres ikke"><input type="checkbox" bind:checked={hide} onchange={() => saveFlag('trend.hideSpikes', hide)} /> Skjul spikes</label>
  {/if}
  {#if selected.length}
    <button class:primary={linked} onclick={toggleLinked} aria-pressed={linked} title="Når grafernes tid er låst sammen, flytter zoom og scroll i én graf alle grafer til samme tidsudsnit">{linked ? '🔒 Grafer låst sammen' : 'Lås graferne sammen'}</button>
    <button onclick={resetView} title="Zoom ud til hele den valgte periode i alle grafer">Nulstil visning</button>
  {/if}
  {#if loading}<span class="muted small">Henter …</span>{/if}
</div>

{#if error}<div class="error">{error}</div>{/if}
{#if info2}<div class="notice">{info2}</div>{/if}

<div class="layout">
  <aside class="panel">
    <div class="viewsel">
      <button class="small" onclick={resetAll} disabled={!selected.length && !viewName} title="Fravælg alle tags, ryd visning og graf-valg">Nulstil valg</button>
    </div>
    {#if views.length || canEdit}
      <div class="viewsel">
        <label class="small">Visning
          <select value={viewName} onchange={(e) => chooseView(e.currentTarget.value)} style="width:100%" aria-label="Gemte visninger">
            <option value="">— ingen valgt —</option>
            {#each views as v (v.name)}<option value={v.name}>{v.name} ({v.tags.length})</option>{/each}
          </select>
        </label>
        {#if canEdit}
          <div class="row wrap small">
            <button class="small" onclick={() => saveView(true)} disabled={!selected.length} title="Gem de valgte tags (og graf-valg og periode) under et navn">Gem som …</button>
            {#if currentView}
              <button class="small" onclick={() => saveView(false)} disabled={!viewChanged() || !selected.length} title="Overskriv den valgte visning med det nuværende udvalg">Opdatér{viewChanged() ? ' *' : ''}</button>
              <button class="small danger" onclick={deleteView}>Slet</button>
            {/if}
          </div>
        {/if}
        {#if viewMsg}<p class="small muted">{viewMsg}</p>{/if}
      </div>
    {/if}
    {#if symbols.length}
      <label class="small symsel">Symbol
        <select value={symKey} onchange={(e) => chooseSymbol(e.currentTarget.value)} style="width:100%">
          {#if canEdit}<option value="">— vælg tags selv —</option>{/if}
          {#each byDrawing(symbols) as [d, list] (d)}
            <optgroup label={d}>{#each list as s (symbolKey(s))}<option value={symbolKey(s)}>{s.name}</option>{/each}</optgroup>
          {/each}
        </select>
      </label>
      {#if symSeries}
        {#if symSeries.missing.length}
          <p class="small muted">Uden historik: {symSeries.missing.map(label).join(', ')}.</p>
          {#if canEdit}
            <button class="small" onclick={enableSymbolTags} disabled={symBusy}>{symBusy ? 'Slår til …' : `Gem historik for ${symSeries.missing.length === 1 ? 'det' : `de ${symSeries.missing.length}`}`}</button>
          {/if}
        {/if}
        {#if symSeries.over.length}<p class="small muted">Højst {MAX_SERIES} kurver ad gangen — ikke vist: {symSeries.over.map(label).join(', ')}.</p>{/if}
      {/if}
    {/if}
    {#if canEdit}
    <div class="row" style="justify-content: space-between">
      <h3>Tags</h3>
      {#if canEdit}
        <label class="small row" title="Slå historik til/fra og slet gemt historik pr. tag">
          <input type="checkbox" bind:checked={manage} /> Administrér
        </label>
      {/if}
    </div>
    <input bind:value={filter} placeholder="Søg" style="width:100%" />
    <ul bind:this={listEl} style={listMax ? `max-height:${listMax}px` : ''}>
      {#each shown as t (t.name)}
        <li>
          <label class:off={!t.trend && !t.samples} title={!t.trend ? `${t.name} — historik er ikke slået til for dette tag` : t.name}>
            <input type="checkbox" checked={selected.includes(t.name)} disabled={!t.trend && !t.samples} onchange={() => toggle(t.name)} />
            {#if selected.includes(t.name)}<span class="swatch" class:dashed={dashOf(colors[t.name] ?? 0)} style="--c:{colorOf(colors[t.name] ?? 0)}"></span>{/if}
            <span class="name">{t.description || t.name}</span>
            <span class="muted small">{t.unit}</span>
          </label>
          {#if selected.includes(t.name)}
            <select class="graphsel" value={assign[t.name] ?? 0} onchange={(e) => setAssign(t.name, Number(e.currentTarget.value))}
              title="Vælg hvilken graf kurven vises i. Auto = graf pr. enhed" aria-label="Graf for {t.description || t.name}">
              <option value={0}>Auto</option>
              {#each Array.from({ length: MAX_CHARTS }, (_, i) => i + 1) as n}<option value={n}>Graf {n}</option>{/each}
            </select>
          {/if}
          {#if canEdit && manage}
            <button class="small enable" disabled={enabling === t.name} onclick={() => rename(t)}
              title="Giv kurven et navn i stedet for tag-navnet">Navn</button>
            {#if t.trend}
              <button class="small enable" disabled={enabling === t.name} onclick={() => stopTrend(t)}
                title="Stop med at gemme historik — det gemte bevares">Stop</button>
            {:else}
              <button class="small enable" disabled={enabling === t.name} onclick={() => enableTrend(t)}
                title="Begynd at gemme historik for {t.name}">Gem</button>
            {/if}
            <button class="small enable danger" disabled={enabling === t.name || !t.samples} onclick={() => deleteHistory(t)}
              title={t.samples ? `Slet de ${t.samples} gemte værdier` : 'Ingen gemte værdier'}>Slet</button>
          {:else if !t.trend && !t.samples && canEdit}
            <button class="small enable" disabled={enabling === t.name} onclick={() => enableTrend(t)}
              title="Begynd at gemme historik for {t.name}">Gem historik</button>
          {/if}
        </li>
      {/each}
    </ul>
    {:else if !symbols.length}
      <p class="muted small">Der er ikke sat nogen trends op i dine tegninger. En tekniker opretter dem under Tegn (symbolets opsætning eller en trendgraf).</p>
    {/if}
    {#if info}
      <p class="muted small">
        Historik gemmes i {info.retention_days} dage · {Math.round(info.db_size / 1024 / 1024 * 10) / 10} MB.
        {#if canEdit}Slå historik til pr. tag under <a href="#tags">Tags</a>; <em>Administrér</em> giver kurverne navne.{/if}
      </p>
    {/if}
  </aside>

  <section class="charts" bind:this={chartsEl}>
    {#if noHistory}
      <div class="panel notice">
        <strong>Ingen tags gemmer historik endnu</strong> — derfor er de grå.
        {#if canEdit}
          Tryk <em>Gem historik</em> ud for et tag til venstre; så gemmer serveren dets værdier fra nu af, og kurven fyldes op.
          Interval og andre indstillinger findes under <a href="#tags">Tags</a>.
        {:else}
          Bed en tekniker eller administrator om at slå historik til for de tags, du vil se.
        {/if}
      </div>
    {:else if !selected.length}
      <div class="panel muted">Vælg et eller flere tags til venstre.</div>
    {:else if resp}
      {#each groups as [unit, tags] (keyOf(unit, tags))}
        {#if !expanded || expanded === keyOf(unit, tags)}
        {@const c = chartFor(tags)}
        <TrendChart title={chartTitle(tags)} unit={chartUnit(tags)} series={c.series} data={c.data} xRange={[resp.start, resp.end]} height={expanded ? fullHeight : plotHeight} expanded={expanded !== null} ondblclick={() => toggleExpand(keyOf(unit, tags))} onclose={() => removeGroup(tags)} {divider} {linked} {view} onview={setView} {resetTick} />
        {/if}
      {/each}
      <p class="muted small">Dobbeltklik på en graf for at se den i fuld størrelse (dobbeltklik igen eller Esc for at gå tilbage). Træk vandret i en graf for at zoome; når der er zoomet ind, scroller du i tid med musehjulet (eller træk med Shift nede); <em>Nulstil visning</em> zoomer ud. Med vælgeren <em>Graf</em> ud for et valgt tag bestemmer du selv, hvilken graf kurven vises i. <em>Lås graferne sammen</em> får alle grafer til at zoome og scrolle sammen. Brud i linjen = ingen gyldig værdi (fx PLC uden forbindelse).</p>
    {/if}
  </section>
</div>

{#if showIssues && analyse && resp && selected.length}
  <div class="issues-overlay panel small" role="dialog" aria-label="Uregelmæssigheder">
    <button class="close" onclick={() => (showIssues = false)} aria-label="Luk" title="Luk">×</button>
          {#if issueTotals.length}
            <strong>Uregelmæssigheder{rings ? ' (ring om punktet)' : ''}:</strong>
            <ul class="found">{#each issueTotals as f (f.name)}<li>{label(f.name)}: {f.text} — <strong>{f.share}</strong> af punkterne ({f.affected} af {f.total})</li>{/each}</ul>
            {#if overall}<div>I alt: <strong>{overall.share}</strong> af alle punkter ({overall.affected} af {overall.total}) har uregelmæssigheder.</div>{/if}
            <span class="muted">{hide ? 'Spikes er udfyldt ved interpolation. ' : ''}Spring, fastfrosne værdier og huller markeres kun. Rådata er uændrede (CSV indeholder alt).</span>
          {:else}
            <span class="muted">Ingen uregelmæssigheder fundet i den viste periode.</span>
          {/if}
  </div>
{/if}

<style>
  .viewsel { display: grid; gap: .3rem; margin-bottom: .6rem; padding-bottom: .5rem; border-bottom: 1px solid var(--line); }
  .toolbar { margin-bottom: .75rem; }
  .layout { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 1rem; align-items: start; }
  @media (max-width: 800px) { .layout { grid-template-columns: minmax(0, 1fr); } }
  ul { list-style: none; padding: 0; margin: .5rem 0; max-height: 60vh; overflow-y: auto; }
  li { display: flex; align-items: center; gap: .4rem; }
  li label { flex: 1; min-width: 0; display: flex; align-items: center; gap: .4rem; padding: .2rem 0; cursor: pointer; }
  li label.off { opacity: .5; cursor: default; }
  .issues-overlay { position: fixed; top: 5rem; right: 1rem; width: min(26rem, calc(100vw - 2rem)); max-height: 70vh; overflow: auto; z-index: 40; box-shadow: 0 6px 24px rgba(0,0,0,.25); }
  .issues-overlay .close { position: absolute; top: .25rem; right: .4rem; border: 0; background: none; font-size: 1.3rem; line-height: 1; cursor: pointer; }
  .issues-overlay ul.found { margin: .25rem 0; }
  .graphsel { width: auto; flex: none; font-size: .75rem; padding: .1rem .2rem; }
  .name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .enable { flex: none; padding: .1rem .45rem; font-size: .75rem; }
  .notice { border-left: 4px solid #2a78d6; }
  .symsel { display: block; margin-bottom: .5rem; }
  .swatch { width: 12px; height: 4px; border-radius: 2px; flex: none; background: var(--c); }
  .swatch.dashed { background: repeating-linear-gradient(90deg, var(--c) 0 4px, transparent 4px 6px); }
  ul.found { max-height: none; margin: .25rem 0; padding-left: 1.1rem; list-style: disc; display: block; }
  ul.found li { display: list-item; }
</style>
