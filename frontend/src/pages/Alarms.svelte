<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import BackToDrawing from '../lib/BackToDrawing.svelte';
  import { get, post, type Alarm, type AlarmSummary } from '../lib/api';
  import { LiveClient } from '../lib/live';
  import { askAssist, assist } from '../lib/assistStore.svelte';
  import { defaultSystem, inSystem, NO_SYSTEM, systemsOf, type AlarmSystem } from '../lib/alarmSystems';
  import { lastDrawing } from '../lib/backToDrawing';

  let { canAck = false }: { canAck?: boolean } = $props();

  interface Event { id: number; ts: number; key: string; tag: string; plc: string; level: string; priority: string;
    event: 'raise' | 'clear' | 'ack' | 'change'; value: unknown; username: string; message: string }

  // Symbolernes afvigelsesalarm har intet grænseniveau (H/HH …) — der vises det valgte alarmniveau
  const PRIO_TEXT: Record<string, string> = { high: 'Høj', medium: 'Medium', low: 'Lav' };
  const levelText = (level: string, priority: string) => (level === 'AFV' ? PRIO_TEXT[priority] ?? priority : level);   // SYS vises som "SYS"
  const STATE_TEXT = { active_unack: 'Aktiv — ikke kvitteret', active_ack: 'Aktiv — kvitteret', rtn_unack: 'Ophørt — ikke kvitteret' };
  const EVENT_TEXT = { raise: 'Opstået', clear: 'Ophørt', ack: 'Kvitteret', change: 'Ændret niveau' };

  let summary = $state<AlarmSummary>({ active: 0, unacked: 0, high: 0 });
  let active = $state<Alarm[]>([]);
  let history = $state<Event[]>([]);
  let tab = $state<'active' | 'history'>('active');
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

  async function loadHistory(): Promise<void> {
    tab = 'history';
    try {
      history = await get<Event[]>('/api/alarms/history?limit=500');
    } catch (e) {
      error = (e as Error).message;
    }
  }

  const fmt = (ts: number | null) => (ts ? new Date(ts * 1000).toLocaleString('da-DK') : '');
  const shown = $derived(active.filter((a) => inSystem(systems, systemId, a)));
  const shownHistory = $derived(history.filter((e) => inSystem(systems, systemId, e)));
  const unacked = $derived(shown.filter((a) => a.state !== 'active_ack'));

  onMount(async () => {
    try {
      const r = await get<{ summary: AlarmSummary; active: Alarm[] }>('/api/alarms');
      summary = r.summary;
      active = r.active;
    } catch (e) {
      error = (e as Error).message;
    }
    try {
      systems = await get<AlarmSystem[]>('/api/alarms/systems');
      systemId = defaultSystem(systems, lastDrawing());
    } catch { /* uden filter ses alle alarmer */ }
  });
  onDestroy(() => live.close());
</script>

{#if error}<div class="error">{error}</div>{/if}

<section class="panel">
  <div class="row" style="justify-content: space-between">
    <div class="row">
      <BackToDrawing />
      <button class:primary={tab === 'active'} onclick={() => (tab = 'active')}>Aktive ({system ? shown.length : summary.active})</button>
      <button class:primary={tab === 'history'} onclick={loadHistory}>Historik</button>
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
      <table>
        <thead><tr><th>Tid</th><th>Prioritet</th><th>System</th><th>Alarm</th><th>Tilstand</th><th></th></tr></thead>
        <tbody>
          {#each shown as a (a.key)}
            <tr class:unacked={a.state !== 'active_ack'}>
              <td class="small nowrap">{fmt(a.raised_at)}</td>
              <td><span class="prio-{a.priority}">{levelText(a.level, a.priority)}</span></td>
              <td class="small">{sysNames(a)}</td>
              <td>{a.message}<div class="muted small mono">{a.kind === 'symbol' ? `symbol ${a.key.split(':').slice(2).join(':')}` : a.kind === 'sys' ? 'SCADA-serveren' : a.tag || a.plc}</div></td>
              <td class="small">
                {STATE_TEXT[a.state]}
                {#if a.acked_by}<div class="muted">af {a.acked_by} {fmt(a.acked_at)}</div>{/if}
              </td>
              <td class="nowrap">
                {#if canAck && a.state !== 'active_ack'}<button onclick={() => ack([a.key])}>Kvittér</button>{/if}
                {#if assist.available && assist.canAsk}
                  <button title="Spørg hjælperen: hvad betyder alarmen, og hvad kan man gøre?"
                          onclick={() => askAssist({ question: 'Forklar alarmen: hvad betyder den, og hvad bør jeg tjekke?', label: a.message, alarm: a.key })}>Forklar</button>
                {/if}
              </td>
            </tr>
          {:else}
            <tr><td colspan="6" class="muted">Ingen aktive alarmer{systemId ? ` — ${filterName}` : ''}.</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
    {#if !canAck && unacked.length}<p class="small muted">Kvittering kræver rollen operatør.</p>{/if}
  {:else}
    <div class="table-wrap">
      <table>
        <thead><tr><th>Tid</th><th>Hændelse</th><th>Niveau</th><th>System</th><th>Alarm</th><th>Bruger</th></tr></thead>
        <tbody>
          {#each shownHistory as e (e.id)}
            <tr>
              <td class="small nowrap">{fmt(e.ts)}</td>
              <td>{EVENT_TEXT[e.event] ?? e.event}</td>
              <td><span class="prio-{e.priority}">{levelText(e.level, e.priority)}</span></td>
              <td class="small">{sysNames(e)}</td>
              <td class="small">{e.message}</td>
              <td class="small">{e.username}</td>
            </tr>
          {:else}
            <tr><td colspan="6" class="muted">Ingen hændelser.</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</section>

<style>
  .nowrap { white-space: nowrap; }
  tr.unacked td:first-child { border-left: 4px solid var(--alarm); }
</style>
