<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import BackToDrawing from '../lib/BackToDrawing.svelte';
  import { get, post, type Alarm, type AlarmSummary } from '../lib/api';
  import { LiveClient } from '../lib/live';

  let { canAck = false }: { canAck?: boolean } = $props();

  interface Event { id: number; ts: number; key: string; tag: string; plc: string; level: string; priority: string;
    event: 'raise' | 'clear' | 'ack' | 'change'; value: unknown; username: string; message: string }

  // Symbolernes afvigelsesalarm har intet grænseniveau (H/HH …) — der vises det valgte alarmniveau
  const PRIO_TEXT: Record<string, string> = { high: 'Høj', medium: 'Medium', low: 'Lav' };
  const levelText = (level: string, priority: string) => (level === 'AFV' ? PRIO_TEXT[priority] ?? priority : level);
  const STATE_TEXT = { active_unack: 'Aktiv — ikke kvitteret', active_ack: 'Aktiv — kvitteret', rtn_unack: 'Ophørt — ikke kvitteret' };
  const EVENT_TEXT = { raise: 'Opstået', clear: 'Ophørt', ack: 'Kvitteret', change: 'Ændret niveau' };

  let summary = $state<AlarmSummary>({ active: 0, unacked: 0, high: 0 });
  let active = $state<Alarm[]>([]);
  let history = $state<Event[]>([]);
  let tab = $state<'active' | 'history'>('active');
  let error = $state('');

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
  const unacked = $derived(active.filter((a) => a.state !== 'active_ack'));

  onMount(async () => {
    try {
      const r = await get<{ summary: AlarmSummary; active: Alarm[] }>('/api/alarms');
      summary = r.summary;
      active = r.active;
    } catch (e) {
      error = (e as Error).message;
    }
  });
  onDestroy(() => live.close());
</script>

{#if error}<div class="error">{error}</div>{/if}

<section class="panel">
  <div class="row" style="justify-content: space-between">
    <div class="row">
      <BackToDrawing />
      <button class:primary={tab === 'active'} onclick={() => (tab = 'active')}>Aktive ({summary.active})</button>
      <button class:primary={tab === 'history'} onclick={loadHistory}>Historik</button>
    </div>
    {#if tab === 'active' && canAck && unacked.length}
      <button class="primary" onclick={() => ack(null)}>Kvittér alle ({unacked.length})</button>
    {/if}
  </div>

  {#if tab === 'active'}
    <div class="table-wrap">
      <table>
        <thead><tr><th>Tid</th><th>Prioritet</th><th>Alarm</th><th>Tilstand</th><th></th></tr></thead>
        <tbody>
          {#each active as a (a.key)}
            <tr class:unacked={a.state !== 'active_ack'}>
              <td class="small nowrap">{fmt(a.raised_at)}</td>
              <td><span class="prio-{a.priority}">{levelText(a.level, a.priority)}</span></td>
              <td>{a.message}<div class="muted small mono">{a.kind === 'symbol' ? `symbol ${a.key.split(':').slice(2).join(':')}` : a.tag || a.plc}</div></td>
              <td class="small">
                {STATE_TEXT[a.state]}
                {#if a.acked_by}<div class="muted">af {a.acked_by} {fmt(a.acked_at)}</div>{/if}
              </td>
              <td>{#if canAck && a.state !== 'active_ack'}<button onclick={() => ack([a.key])}>Kvittér</button>{/if}</td>
            </tr>
          {:else}
            <tr><td colspan="5" class="muted">Ingen aktive alarmer.</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
    {#if !canAck && unacked.length}<p class="small muted">Kvittering kræver rollen operatør.</p>{/if}
  {:else}
    <div class="table-wrap">
      <table>
        <thead><tr><th>Tid</th><th>Hændelse</th><th>Niveau</th><th>Alarm</th><th>Bruger</th></tr></thead>
        <tbody>
          {#each history as e (e.id)}
            <tr>
              <td class="small nowrap">{fmt(e.ts)}</td>
              <td>{EVENT_TEXT[e.event] ?? e.event}</td>
              <td><span class="prio-{e.priority}">{levelText(e.level, e.priority)}</span></td>
              <td class="small">{e.message}</td>
              <td class="small">{e.username}</td>
            </tr>
          {:else}
            <tr><td colspan="5" class="muted">Ingen hændelser.</td></tr>
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
