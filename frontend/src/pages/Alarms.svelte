<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import BackToDrawing from '../lib/BackToDrawing.svelte';
  import { get, post, type Alarm, type AlarmSummary, type ShelvedAlarm } from '../lib/api';
  import ShelveDialog from '../lib/ShelveDialog.svelte';
  import { canShelve, remainingNow, remainingText } from '../lib/shelf';
  import { LiveClient } from '../lib/live';
  import { askAssist, assist } from '../lib/assistStore.svelte';
  import { defaultSystem, inSystem, NO_SYSTEM, systemsOf, type AlarmSystem } from '../lib/alarmSystems';
  import { lastDrawing } from '../lib/backToDrawing';
  import { rationaleLines } from '../lib/tagAlarm';
  import { alarmPriorityText, alarmTypeText } from '../lib/alarmType';
  import { exportUrl, historyUrl, isFiltered, type HistoryFilter } from '../lib/alarmHistory';

  let { canAck = false }: { canAck?: boolean } = $props();

  interface Event { id: number; ts: number; key: string; tag: string; plc: string; level: string; priority: string;
    event: 'raise' | 'clear' | 'ack' | 'change' | 'shelve' | 'unshelve'; value: unknown; username: string; message: string }

  // Prioriteten (Høj/Medium/Lav) og typen (HH/H/L/LL/Til/Kommunikation/System/Afvigelse) står hver i sin kolonne (v6.18.0)
  const PRIO_TEXT: Record<string, string> = { high: 'Høj', medium: 'Medium', low: 'Lav' };
  const STATE_TEXT = { active_unack: 'Aktiv — ikke kvitteret', active_ack: 'Aktiv — kvitteret', rtn_unack: 'Ophørt — ikke kvitteret' };
  const EVENT_TEXT = { raise: 'Opstået', clear: 'Ophørt', ack: 'Kvitteret', change: 'Ændret niveau', shelve: 'Udsat', unshelve: 'Genindsat' };

  let summary = $state<AlarmSummary>({ active: 0, unacked: 0, high: 0, shelved: 0 });
  let active = $state<Alarm[]>([]);
  let history = $state<Event[]>([]);
  let tab = $state<'active' | 'shelved' | 'history'>('active');
  let error = $state('');
  // filter pr. system (tegning): åbner med den tegning, man kom fra (v6.16.3); "Alle systemer" er ét valg væk
  let systems = $state<AlarmSystem[]>([]);
  let systemId = $state('');
  function pickSystem(id: string): void {
    systemId = id;
  }
  const system = $derived(systems.find((s) => s.id === systemId) ?? null);
  const filterName = $derived(systemId === NO_SYSTEM ? 'uden system' : system?.name ?? '');
  const sysNames = (a: { key: string; kind?: string; tag?: string }) => systemsOf(systems, a).map((s) => s.name).join(', ') || '—';

  const live = new LiveClient(() => {});
  live.onAlarms = (s, a) => {
    summary = s;
    active = a;
    if (tab === 'shelved') void loadShelved();   // på fanen Udsatte hentes listen ved hvert push (udløb og ændringer fra andre)
  };
  live.subscribe([]);

  async function ack(keys: string[] | null): Promise<void> {
    error = '';
    try {
      await post('/api/alarms/ack', { keys });
    } catch (e) {
      error = (e as Error).message;
    }
  }

  // Udsatte alarme (v6.19.0): hentes fra serveren; resttiden regnes fra svaret og opdateres hvert 30. sekund
  let shelved = $state<ShelvedAlarm[]>([]);
  let shelvedAt = $state(Date.now());
  let nowMs = $state(Date.now());
  let shelveTarget = $state<Alarm | null>(null);
  let shelvedError = $state('');   // egen fejl for listen, så en vellykket hentning ikke sletter en kvitterings-/genindsætningsfejl
  let shelvedSeq = 0;
  async function loadShelved(): Promise<void> {
    const seq = ++shelvedSeq;
    try {
      const rows = await get<ShelvedAlarm[]>('/api/alarms/shelved');
      if (seq !== shelvedSeq) return;   // et nyere svar er på vej (eller er kommet): et ældre må ikke overskrive det
      shelved = rows;
      shelvedAt = Date.now();
      nowMs = shelvedAt;
      shelvedError = '';
    } catch (e) {
      if (seq !== shelvedSeq) return;
      shelvedError = (e as Error).message;
    }
  }
  async function unshelve(key: string): Promise<void> {
    error = '';
    try {
      await post('/api/alarms/unshelve', { key });
    } catch (e) {
      error = (e as Error).message;
    }
    await loadShelved();   // også efter en fejl (fx 404: en anden har allerede genindsat den)
  }
  async function shelveDone(): Promise<void> {
    shelveTarget = null;
    await Promise.all([loadShelved(), loadActive()]);
  }
  async function loadActive(): Promise<void> {
    try {
      const r = await get<{ summary: AlarmSummary; active: Alarm[] }>('/api/alarms');
      summary = r.summary;
      active = r.active;
    } catch (e) {
      error = (e as Error).message;
    }
  }
  // En udsættelse ændret af andre (eller udløbet) ses som en ny tæller i opsummeringen → hent listen igen
  let lastShelvedCount = -1;
  $effect(() => {
    const n = summary.shelved ?? 0;
    if (n !== lastShelvedCount) {
      lastShelvedCount = n;
      if (n !== shelved.length) void loadShelved();
    }
  });
  const tick = setInterval(() => (nowMs = Date.now()), 30_000);

  // Historik: søgning/filtre afgøres på serveren, så listen og CSV-eksporten viser det samme
  const HISTORY_LIMIT = 500;
  let hq = $state('');
  let hFrom = $state('');
  let hTo = $state('');
  let hEvent = $state('');
  let hPriority = $state('');
  let histError = $state('');
  let histLoaded = $state(false);
  const hFilter = $derived<HistoryFilter>({ q: hq, from: hFrom, to: hTo, event: hEvent, priority: hPriority, system: systemId });
  const filtered = $derived(isFiltered(hFilter));
  const csvHref = $derived(exportUrl(hFilter));
  let loadSeq = 0;
  let lastQ = '';
  let timer: ReturnType<typeof setTimeout> | undefined;

  async function loadHistory(): Promise<void> {
    const seq = ++loadSeq;
    try {
      const rows = await get<Event[]>(historyUrl(hFilter, HISTORY_LIMIT));
      if (seq !== loadSeq) return;   // et nyere svar er på vej
      history = rows;
      histError = '';
      histLoaded = true;
    } catch (e) {
      if (seq !== loadSeq) return;
      histError = (e as Error).message;
      history = [];   // ingen gamle rækker under en fejlbesked
    }
  }

  function resetFilter(): void {
    hq = ''; hFrom = ''; hTo = ''; hEvent = ''; hPriority = '';
  }

  // Hent igen ved ændring af filtre (søgefeltet med 300 ms debounce) eller når fanen åbnes
  $effect(() => {
    const f = hFilter;
    if (tab !== 'history') return;
    clearTimeout(timer);
    const delay = f.q !== lastQ ? 300 : 0;
    lastQ = f.q;
    timer = setTimeout(loadHistory, delay);
    return () => clearTimeout(timer);
  });

  const fmt = (ts: number | null) => (ts ? new Date(ts * 1000).toLocaleString('da-DK') : '');
  const shown = $derived(active.filter((a) => inSystem(systems, systemId, a)));
  const shownHistory = $derived(history);
  const unacked = $derived(shown.filter((a) => a.state !== 'active_ack'));

  onMount(async () => {
    await loadActive();
    try {
      systems = await get<AlarmSystem[]>('/api/alarms/systems');
      systemId = defaultSystem(systems, lastDrawing());
    } catch { /* uden filter ses alle alarmer */ }
  });
  onDestroy(() => {
    live.close();
    clearInterval(tick);
  });
</script>

{#if error}<div class="error">{error}</div>{/if}
{#if shelvedError}<div class="error">Udsatte alarmer kunne ikke hentes: {shelvedError}</div>{/if}

<section class="panel">
  <div class="row" style="justify-content: space-between">
    <div class="row">
      <BackToDrawing />
      <button class="tab-count" class:primary={tab === 'active'} onclick={() => (tab = 'active')}>Aktive ({system ? shown.length : summary.active})</button>
      <button class="tab-count" class:primary={tab === 'shelved'} onclick={() => { tab = 'shelved'; void loadShelved(); }}>Udsatte ({summary.shelved ?? shelved.length})</button>
      <button class:primary={tab === 'history'} onclick={() => (tab = 'history')}>Historik</button>
      {#if systems.length > 1}
        <label class="small">System
          <select value={systemId} onchange={(e) => pickSystem(e.currentTarget.value)} aria-label="System">
            <option value="">Alle systemer</option>
            <option value={NO_SYSTEM}>Uden system</option>
            {#each systems as s (s.id)}<option value={s.id}>{s.name}</option>{/each}
          </select>
        </label>
      {/if}
      {#if assist.available && assist.canAsk}
        <button title="Hjælperen opsummerer alarmerne fra de seneste 24 timer: hvad skete der, hvad gentog sig, og hvad bør undersøges"
                onclick={() => askAssist({ question: 'Opsummér alarmerne fra det seneste døgn: hvad skete der, hvad gentog sig, og hvad bør jeg undersøge?', label: 'Døgnets alarmer', summary: true })}>Opsummér døgnet</button>
      {/if}
    </div>
    {#if tab === 'active' && canAck && unacked.length}
      <button class="primary" onclick={() => ack(systemId ? unacked.map((a) => a.key) : null)}>Kvittér alle{systemId ? ` (${filterName})` : ''} ({unacked.length})</button>
    {/if}
  </div>

  {#if tab === 'active'}
    <div class="table-wrap">
      <table class="fixed t-active">
        <colgroup><col class="c-tid" /><col class="c-prio" /><col class="c-type" /><col class="c-sys" /><col /><col class="c-state" /><col class="c-act" /></colgroup>
        <thead><tr><th>Tid</th><th>Prioritet</th><th>Type</th><th>System</th><th>Alarm</th><th>Tilstand</th><th></th></tr></thead>
        <tbody>
          {#each shown as a (a.key)}
            <tr class:unacked={a.state !== 'active_ack'}>
              <td class="small nowrap g-tid">{fmt(a.raised_at)}</td>
              <td class="g-prio"><span class="prio-{a.priority}">{alarmPriorityText(a.priority)}</span></td>
              <td class="small g-type">{alarmTypeText(a.level)}</td>
              <td class="small g-sys">{sysNames(a)}</td>
              <td class="g-alarm">{a.message}<div class="muted small mono">{a.kind === 'symbol' ? `symbol ${a.key.split(':').slice(2).join(':')}` : a.kind === 'sys' ? 'SCADA-serveren' : a.tag || a.plc}</div>{#each rationaleLines(a) as line}<div class="muted small rat">{line}</div>{/each}</td>
              <td class="small g-state">
                {STATE_TEXT[a.state]}
                {#if a.acked_by}<div class="muted">af {a.acked_by} {fmt(a.acked_at)}</div>{/if}
              </td>
              <td class="nowrap g-act">
                {#if canAck && a.state !== 'active_ack'}<button onclick={() => ack([a.key])}>Kvittér</button>{/if}
                {#if canAck && canShelve(a)}<button title="Skjul alarmen midlertidigt med en begrundelse" onclick={() => (shelveTarget = a)}>Udsæt</button>{/if}
                {#if assist.available && assist.canAsk}
                  <button title="Spørg hjælperen: hvad betyder alarmen, og hvad kan man gøre?"
                          onclick={() => askAssist({ question: 'Forklar alarmen: hvad betyder den, og hvad bør jeg tjekke?', label: a.message, alarm: a.key })}>Forklar</button>
                {/if}
              </td>
            </tr>
          {:else}
            <tr><td colspan="7" class="muted g-empty">Ingen aktive alarmer{systemId ? ` — ${filterName}` : ''}.</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
    {#if !canAck && unacked.length}<p class="small muted">Kvittering kræver rollen operatør.</p>{/if}
  {:else if tab === 'shelved'}
    <div class="table-wrap">
      <table class="fixed t-shelved">
        <colgroup><col class="c-tid" /><col /><col class="c-user" /><col class="c-reason" /><col class="c-rest" /><col class="c-act2" /></colgroup>
        <thead><tr><th>Udsat</th><th>Alarm</th><th>Af</th><th>Begrundelse</th><th>Resttid</th><th></th></tr></thead>
        <tbody>
          {#each shelved as s (s.key)}
            <tr>
              <td class="small nowrap g-tid">{fmt(s.shelved_at)}</td>
              <td class="g-alarm">{s.message}<div class="muted small mono">{s.tag || s.plc}</div></td>
              <td class="small g-user">{s.shelved_by}</td>
              <td class="small g-reason">{s.reason}</td>
              <td class="small nowrap g-rest num">{remainingText(remainingNow(s.remaining_s, shelvedAt, nowMs))}</td>
              <td class="nowrap g-act">{#if canAck}<button onclick={() => unshelve(s.key)}>Genindsæt</button>{/if}</td>
            </tr>
          {:else}
            <tr><td colspan="6" class="muted g-empty">Ingen udsatte alarme.</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
    {#if !canAck && shelved.length}<p class="small muted">Genindsættelse kræver rollen operatør.</p>{/if}
  {:else}
    <div class="row hfilter">
      <input type="search" class="hq" placeholder="Søg i tag, PLC og besked" aria-label="Søg i historikken" bind:value={hq} />
      <label class="small">Fra <input type="date" max={hTo || undefined} bind:value={hFrom} aria-label="Fra dato" /></label>
      <label class="small">Til <input type="date" min={hFrom || undefined} bind:value={hTo} aria-label="Til dato" /></label>
      <select bind:value={hEvent} aria-label="Hændelse">
        <option value="">Alle hændelser</option>
        {#each Object.entries(EVENT_TEXT) as [k, t] (k)}<option value={k}>{t}</option>{/each}
      </select>
      <select bind:value={hPriority} aria-label="Prioritet">
        <option value="">Alle prioriteter</option>
        {#each Object.entries(PRIO_TEXT) as [k, t] (k)}<option value={k}>{t}</option>{/each}
      </select>
      <button onclick={resetFilter} disabled={!filtered}>Nulstil</button>
      <!-- Ved en filterfejl ville download gemme backendens JSON-fejl som en fil; fejlen står i tælleren -->
      <a class="btn" class:disabled={!!histError} aria-disabled={histError ? 'true' : undefined} href={csvHref} download
         onclick={(e) => { if (histError) e.preventDefault(); }}>CSV</a>
    </div>
    <div class="hcount small" class:error={!!histError} aria-live="polite">
      {#if histError}{histError}
      {:else if !histLoaded}Henter …
      {:else}{history.length} hændelser{history.length >= HISTORY_LIMIT ? ` — afkortet til de nyeste ${HISTORY_LIMIT}; CSV indeholder alle` : ''}{/if}
    </div>
    <div class="table-wrap">
      <table class="fixed t-hist">
        <colgroup><col class="c-tid" /><col class="c-event" /><col class="c-prio" /><col class="c-type" /><col class="c-sys" /><col /><col class="c-user" /></colgroup>
        <thead><tr><th>Tid</th><th>Hændelse</th><th>Prioritet</th><th>Type</th><th>System</th><th>Alarm</th><th>Bruger</th></tr></thead>
        <tbody>
          {#each shownHistory as e (e.id)}
            <tr>
              <td class="small nowrap g-tid">{fmt(e.ts)}</td>
              <td class="g-event">{EVENT_TEXT[e.event] ?? e.event}</td>
              <td class="g-prio"><span class="prio-{e.priority}">{alarmPriorityText(e.priority)}</span></td>
              <td class="small g-type">{alarmTypeText(e.level)}</td>
              <td class="small g-sys">{sysNames(e)}</td>
              <td class="small g-alarm">{e.message}</td>
              <td class="small g-user">{e.username}</td>
            </tr>
          {:else}
            <tr><td colspan="7" class="muted g-empty">Ingen hændelser.</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</section>

{#if shelveTarget}
  <ShelveDialog alarm={shelveTarget} onclose={() => (shelveTarget = null)} ondone={shelveDone} />
{/if}

<style>
  .nowrap { white-space: nowrap; }
  /* Faste kolonnebredder: skiftende tekster (prioritet, type, tilstand) må ikke flytte kolonnerne */
  table.fixed { table-layout: fixed; width: 100%; min-width: 62rem; }
  table.fixed.t-active { min-width: 70rem; }
  table.fixed td { overflow-wrap: anywhere; }
  .c-tid { width: 10.5rem; } .c-prio { width: 5.5rem; } .c-type { width: 8rem; } .c-sys { width: 9rem; }
  .c-state { width: 11rem; } .c-act { width: 17rem; } .c-event { width: 7rem; } .c-user { width: 7rem; }
  .c-reason { width: 16rem; } .c-rest { width: 7.5rem; } .c-act2 { width: 8rem; }
  .tab-count { min-width: 7.5rem; }   /* tælleren i fanen må ikke flytte knapperne ved siden af */
  .num { font-variant-numeric: tabular-nums; }
  /* Under 1120 px (tabellens mindstebredde): hver række bliver et kort — alarmteksten får hele bredden, og Kvittér er altid synlig */
  @media (max-width: 1120px) {
    table.fixed, table.fixed tbody { display: block; width: 100%; min-width: 0; }
    table.fixed thead, table.fixed colgroup { display: none; }
    table.fixed tr { display: grid; grid-template-columns: auto auto 1fr; gap: 0.15rem 0.8rem; align-items: baseline; padding: 0.5rem 0.4rem; border-bottom: 1px solid var(--line); }
    table.fixed td { display: block; padding: 0; border: 0; min-width: 0; }
    table.t-active tr { grid-template-areas: "tid prio type" "alarm alarm alarm" "sys state state" "act act act"; }
    table.t-hist tr { grid-template-areas: "tid prio type" "alarm alarm alarm" "event sys user"; }
    table.t-shelved tr { grid-template-areas: "tid rest rest" "alarm alarm alarm" "user reason reason" "act act act"; }
    .g-rest { grid-area: rest; text-align: right; } .g-reason { grid-area: reason; }
    .g-tid { grid-area: tid; } .g-prio { grid-area: prio; } .g-type { grid-area: type; } .g-sys { grid-area: sys; }
    .g-alarm { grid-area: alarm; } .g-state { grid-area: state; } .g-act { grid-area: act; padding-top: 0.2rem !important; }
    .g-event { grid-area: event; } .g-user { grid-area: user; }
    table.fixed td.g-empty { grid-area: auto; grid-column: 1 / -1; }
    tr.unacked { border-left: 4px solid var(--alarm); }
    tr.unacked td:first-child { border-left: 0; }
  }
  .rat { overflow-wrap: anywhere; }
  .hfilter { flex-wrap: wrap; margin: 0.6rem 0 0.2rem; }
  .hq { width: 18rem; max-width: 100%; }
  .hcount { min-height: 1.4em; margin: 0 0 0.4rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .btn.disabled { opacity: 0.5; pointer-events: none; }
  .hcount.error { background: none; border: 0; padding: 0; color: var(--alarm); }
  tr.unacked td:first-child { border-left: 4px solid var(--alarm); }
</style>
