<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { get } from '../lib/api';
  import MetricsToken from '../lib/MetricsToken.svelte';
  import { AREA_TEXT, LEVEL_TEXT, fmtBytes, fmtDuration, fmtMs, fmtPercent, levelClass, type Health } from '../lib/status';

  const REFRESH_MS = 5000;
  let health = $state<Health | null>(null);
  let error = $state('');
  let updated = $state<Date | null>(null);
  let timer: ReturnType<typeof setInterval> | undefined;

  async function refresh(): Promise<void> {
    try {
      health = await get<Health>('/api/health/details');
      updated = new Date();
      error = '';
    } catch (e) {
      error = (e as Error).message;   // fx serveren genstarter: vis fejlen, og prøv igen ved næste tik
    }
  }

  onMount(() => {
    refresh();
    timer = setInterval(() => { if (document.visibilityState === 'visible') refresh(); }, REFRESH_MS);
  });
  onDestroy(() => clearInterval(timer));

  const rate = (r: number | null) => (r === null ? '—' : `${r.toFixed(1)} kald/s`);
  const plcBadge = (p: Health['plcs'][number]): string =>
    p.state === 'ok' ? (p.partial.length ? 'warn' : 'ok') : p.state === 'error' ? 'error' : 'unknown';
</script>

<section class="panel">
  <div class="row" style="justify-content: space-between">
    <h2>Status</h2>
    <div class="row">
      {#if updated}<span class="muted small">Opdateret {updated.toLocaleTimeString('da-DK')}</span>{/if}
      <button onclick={refresh}>Opdatér</button>
    </div>
  </div>
  <p class="muted small">Hvordan SCADA-serveren og PLC'erne har det lige nu. Siden opdaterer sig selv hvert {REFRESH_MS / 1000}. sekund.</p>
  {#if error}<div class="error">{error}</div>{/if}

  {#if health}
    <div class="summary {levelClass(health.level)}" role="status">
      <strong>{LEVEL_TEXT[health.level]}</strong>
      <span class="muted small">v{health.version.version} · b{health.version.build} · kørt i {fmtDuration(health.uptime_s)}</span>
    </div>
    {#if health.problems.length}
      <ul class="problems">
        {#each health.problems as p}
          <li><span class="badge {levelClass(p.level)}">{AREA_TEXT[p.area] ?? p.area}</span> {p.message}</li>
        {/each}
      </ul>
    {/if}

    <h3>PLC'er</h3>
    <div class="table-wrap">
      <table>
        <thead><tr><th>PLC</th><th>Forbindelse</th><th>Seneste svar</th><th>Kald</th><th>Afvist (429)</th><th>SSE</th></tr></thead>
        <tbody>
          {#each health.plcs as p (p.key)}
            <tr>
              <td>{p.name}<div class="muted small mono">{p.key}</div></td>
              <td>
                {#if !p.enabled}<span class="badge off">deaktiveret</span>
                {:else}<span class="badge {plcBadge(p)}">{p.state === 'ok' && p.partial.length ? 'delvis fejl' : p.state}</span>{/if}
                {#if p.message}<div class="small">{p.message}</div>{/if}
                {#each p.partial as f}<div class="small">{f.what}: {f.message} ({f.tags} tag)</div>{/each}
              </td>
              <td>{p.last_ok_age_s === null ? '—' : `${fmtDuration(p.last_ok_age_s)} siden`}</td>
              <td>{rate(p.request_rate)}<div class="muted small">{p.requests_per_cycle ?? '—'} pr. runde · loft 5/s</div></td>
              <td>{p.throttled}{#if p.last_throttled}<div class="muted small">senest {new Date(p.last_throttled * 1000).toLocaleTimeString('da-DK')}</div>{/if}</td>
              <td>{p.sse ?? '—'}</td>
            </tr>
          {:else}
            <tr><td colspan="6" class="muted">Ingen PLC'er er sat op.</td></tr>
          {/each}
        </tbody>
      </table>
    </div>

    <h3>Server</h3>
    <div class="cards">
      <div class="card"><div class="muted small">Event-loop-lag (seneste minut)</div>
        <strong>{fmtMs(health.loop.lag_max_s)}</strong><div class="muted small">nu {fmtMs(health.loop.lag_last_s)} · højt = serveren var optaget</div></div>
      <div class="card"><div class="muted small">Database</div>
        <strong>{health.db.ok ? fmtMs(health.db.latency_s) : 'svarer ikke'}</strong>{#if health.db.error}<div class="small">{health.db.error}</div>{/if}</div>
      <div class="card"><div class="muted small">Live-forbindelser</div><strong>{health.ws_clients}</strong><div class="muted small">åbne sider (WebSocket)</div></div>
      <div class="card"><div class="muted small">Alarmer</div>
        <strong>{health.alarms.active} aktive</strong><div class="muted small">{health.alarms.unacked} ukvitterede · {health.alarms.high} høj prioritet</div></div>
      <div class="card"><div class="muted small">Trend-historik</div>
        <strong>{fmtBytes(health.trends.db_bytes)}</strong><div class="muted small">{health.trends.rows} rækker skrevet siden start{health.trends.rows_per_day !== null ? ` · ca. ${health.trends.rows_per_day}/døgn` : ''}</div></div>
      <div class="card"><div class="muted small">Seneste backup</div>
        <strong>{health.backup.last_age_s === null ? 'ingen' : `${fmtDuration(health.backup.last_age_s)} siden`}</strong>
        <div class="muted small">{health.backup.interval_h > 0 ? `automatisk hver ${health.backup.interval_h}. time · ${health.backup.count} gemt` : 'automatisk backup er slået fra'}</div></div>
    </div>

    <h3>Maskine</h3>
    <div class="cards">
      <div class="card"><div class="muted small">Ledig disk</div>
        <strong>{health.disk ? fmtBytes(health.disk.free) : '—'}</strong>
        <div class="muted small">{health.disk ? `${fmtPercent(health.disk.used, health.disk.total)} brugt af ${fmtBytes(health.disk.total)}` : 'kan ikke aflæses'}</div></div>
      <div class="card"><div class="muted small">Hukommelse</div>
        <strong>{fmtBytes(health.host.mem_available)} ledig</strong><div class="muted small">af {fmtBytes(health.host.mem_total)}</div></div>
      <div class="card"><div class="muted small">CPU-temperatur</div>
        <strong>{health.host.cpu_temp_c === null ? '—' : `${health.host.cpu_temp_c.toFixed(0)} °C`}</strong>
        {#if health.host.load}<div class="muted small">belastning {health.host.load.map((x) => x.toFixed(2)).join(' / ')}</div>{/if}</div>
      <div class="card"><div class="muted small">Strøm og varme (Pi)</div>
        {#if health.host.throttled === null}<strong>—</strong><div class="muted small">kun på en Raspberry Pi</div>
        {:else if health.host.throttled.now.length}<strong class="bad">{health.host.throttled.now.join(', ')}</strong>
        {:else if health.host.throttled.past.length}<strong class="warnText">ok nu</strong><div class="muted small">siden opstart: {health.host.throttled.past.join(', ')}</div>
        {:else}<strong>ok</strong>{/if}</div>
    </div>
  {:else if !error}
    <p class="muted">Henter …</p>
  {/if}
  <MetricsToken />
</section>

<style>
  .summary { display: flex; gap: 1rem; align-items: baseline; padding: 0.6rem 0.8rem; border-radius: var(--radius); border: 1px solid var(--line); margin: 0.6rem 0; }
  .summary.ok { border-color: var(--ok); color: var(--ok); }
  .summary.warn { border-color: var(--warn); color: var(--warn); }
  .summary.error { border-color: var(--alarm); color: var(--alarm); }
  .summary strong { font-size: 1.1rem; }
  .problems { list-style: none; padding: 0; margin: 0.4rem 0 0.8rem; display: grid; gap: 0.3rem; }
  .badge.warn { border-color: var(--warn); color: var(--warn); }
  h3 { margin: 1.1rem 0 0.4rem; font-size: 1rem; }
  .cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(14rem, 1fr)); gap: 0.6rem; }
  .card { border: 1px solid var(--line); background: var(--panel-2); border-radius: var(--radius); padding: 0.55rem 0.7rem; }
  .card strong { display: block; font-size: 1.15rem; margin: 0.1rem 0; }
  .bad { color: var(--alarm); }
  .warnText { color: var(--warn); }
</style>
