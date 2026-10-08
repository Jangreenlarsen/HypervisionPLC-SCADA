<script lang="ts">
  import { onMount } from 'svelte';
  import { get } from '../lib/api';

  interface Entry {
    id: number; ts: number; username: string; ip: string; action: string; target: string;
    detail: Record<string, unknown>; result: 'ok' | 'warning' | 'error'; message: string;
  }

  const FILTERS = [
    { id: '', label: 'Alt' },
    { id: 'write', label: 'Skrivninger' },
    { id: 'toggle', label: 'Til/fra' },
    { id: 'pulse', label: 'Pulser' },
    { id: 'login', label: 'Login' },
    { id: 'tag.', label: 'Tags' },
    { id: 'binding.', label: 'Bindinger' },
    { id: 'drawing.', label: 'Tegninger' },
    { id: 'plc.', label: "PLC'er" },
    { id: 'user.', label: 'Brugere' },
  ];

  let entries = $state<Entry[]>([]);
  let filter = $state('');
  let error = $state('');

  async function refresh(): Promise<void> {
    error = '';
    try {
      entries = await get<Entry[]>(`/api/audit?limit=500${filter ? `&action=${encodeURIComponent(filter)}` : ''}`);
    } catch (e) {
      error = (e as Error).message;
    }
  }

  function summary(e: Entry): string {
    const d = e.detail ?? {};
    if (e.action === 'write') {
      const parts = [`→ ${d.written ?? d.requested}`];
      if (d.old !== undefined && d.old !== null) parts.unshift(`${d.old}`);
      if (d.readback !== undefined && d.readback !== d.written) parts.push(`(PLC: ${d.readback})`);
      return parts.join(' ');
    }
    if (e.action === 'pulse') return `${d.ms} ms`;
    const keys = Object.keys(d).filter((k) => k !== 'report' && k !== 'bindings');
    return keys.map((k) => `${k}=${typeof d[k] === 'object' ? JSON.stringify(d[k]) : d[k]}`).join(', ').slice(0, 160);
  }

  onMount(refresh);
</script>

<section class="panel">
  <div class="row" style="justify-content: space-between">
    <h2>Log</h2>
    <div class="row">
      <select bind:value={filter} onchange={refresh} aria-label="Filter">
        {#each FILTERS as f}<option value={f.id}>{f.label}</option>{/each}
      </select>
      <button onclick={refresh}>Opdatér</button>
    </div>
  </div>
  <p class="muted small">Alle skrivninger til PLC'erne og ændringer af konfigurationen — også afviste forsøg.</p>
  {#if error}<div class="error">{error}</div>{/if}
  <div class="table-wrap">
    <table>
      <thead><tr><th>Tid</th><th>Bruger</th><th>Handling</th><th>Mål</th><th>Detaljer</th><th>Resultat</th></tr></thead>
      <tbody>
        {#each entries as e (e.id)}
          <tr>
            <td class="small nowrap">{new Date(e.ts * 1000).toLocaleString('da-DK')}</td>
            <td>{e.username}<div class="muted small">{e.ip}</div></td>
            <td class="mono">{e.action}</td>
            <td class="mono">{e.target}</td>
            <td class="small">{summary(e)}</td>
            <td>
              <span class="badge {e.result === 'ok' ? 'ok' : e.result === 'error' ? 'error' : 'unknown'}">{e.result}</span>
              {#if e.message}<div class="small">{e.message}</div>{/if}
            </td>
          </tr>
        {:else}
          <tr><td colspan="6" class="muted">Ingen poster.</td></tr>
        {/each}
      </tbody>
    </table>
  </div>
</section>

<style>
  .nowrap { white-space: nowrap; }
</style>
