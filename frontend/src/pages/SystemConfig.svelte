<script lang="ts">
  import { onMount } from 'svelte';
  import { api, get } from '../lib/api';

  interface Nic { name: string; mac: string; state: string; addresses: { ip: string; prefix: number | null }[] }
  interface Config {
    storage: { path: string; files: { name: string; size: number }[]; folders: { name: string; size: number }[];
      disk: { total: number; used: number; free: number } | null };
    trends: { retention_days: number; flush_s: number; energy_days: number; overridden: boolean;
      limits: Record<string, { min: number; max: number }>; tags: number; samples: number;
      write: { since: number; uptime_s: number; rows: number; flushes: number; rows_per_day: number | null; flushes_per_day: number | null } };
    network: { available: boolean; hostname: string; interfaces: Nic[]; gateway: string; dns: string[]; error: string };
  }

  let cfg = $state<Config | null>(null);
  let error = $state('');
  let busy = $state(false);
  // Trend-indstillinger (redigeres her, gemmes med knappen)
  let retention = $state(30);
  let flush = $state(5);
  let energy = $state(400);
  let saving = $state(false);
  let saved = $state('');
  let saveError = $state('');

  const fmtBytes = (b: number): string =>
    b >= 1024 ** 3 ? `${(b / 1024 ** 3).toFixed(1)} GB` : b >= 1024 ** 2 ? `${(b / 1024 ** 2).toFixed(1)} MB` : `${Math.round(b / 1024)} kB`;
  const fmtUp = (s: number): string => (s >= 86400 ? `${(s / 86400).toFixed(1)} døgn` : s >= 3600 ? `${(s / 3600).toFixed(1)} t` : `${Math.round(s / 60)} min`);
  const fmtNum = (n: number): string => n.toLocaleString('da-DK');

  async function refresh(): Promise<void> {
    busy = true;
    error = '';
    try {
      cfg = await get<Config>('/api/system/config');
      fillForm(cfg.trends);
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }
  function fillForm(t: Config['trends']): void {
    retention = t.retention_days;
    flush = t.flush_s;
    energy = t.energy_days;
  }

  const dirty = $derived(!!cfg && (retention !== cfg.trends.retention_days || flush !== cfg.trends.flush_s || energy !== cfg.trends.energy_days));

  async function saveTrends(): Promise<void> {
    saving = true;
    saveError = '';
    saved = '';
    try {
      const t = await api<Config['trends']>('PUT', '/api/system/config/trends',
        { retention_days: Number(retention), flush_s: Number(flush), energy_days: Number(energy) });
      if (cfg) cfg.trends = t;
      fillForm(t);
      saved = 'Gemt — gælder straks.';
    } catch (e) {
      saveError = (e as Error).message;
    } finally {
      saving = false;
    }
  }
  onMount(refresh);
</script>

<section class="panel">
  <div class="row" style="justify-content: space-between">
    <h2>Konfiguration</h2>
    <button onclick={refresh} disabled={busy}>{busy ? 'Henter …' : 'Opdatér'}</button>
  </div>
  <p class="muted small">Visning af hvor data ligger, hvor meget der skrives, og hvilket netværk maskinen kører på. Netværk (IP, subnet, gateway, DNS) og placering af data kan sættes herfra i et senere trin — alle indstillinger samles på denne side, så de kan indtastes færdige og anvendes samlet.</p>
  {#if error}<div class="error">{error}</div>{/if}
</section>

{#if cfg}
  <section class="panel">
    <h3>Lagring</h3>
    <p>Datamappe: <code>{cfg.storage.path}</code></p>
    {#if cfg.storage.disk}
      {@const d = cfg.storage.disk}
      <p>Disk: <strong>{fmtBytes(d.free)}</strong> ledig af {fmtBytes(d.total)} ({Math.round((d.used / d.total) * 100)} % brugt)</p>
    {/if}
    <table class="grid">
      <thead><tr><th>Fil / mappe</th><th class="num">Størrelse</th></tr></thead>
      <tbody>
        {#each cfg.storage.files as f (f.name)}<tr><td><code>{f.name}</code></td><td class="num">{fmtBytes(f.size)}</td></tr>{/each}
        {#each cfg.storage.folders as f (f.name)}<tr><td><code>{f.name}/</code></td><td class="num">{fmtBytes(f.size)}</td></tr>{/each}
      </tbody>
    </table>
  </section>

  <section class="panel">
    <h3>Trend-historik og skrivning til disken</h3>
    <p>{fmtNum(cfg.trends.samples)} gemte værdier for {cfg.trends.tags} tags · opbevares i {cfg.trends.retention_days} dage (energi: {cfg.trends.energy_days} dage) · skrives samlet hvert {cfg.trends.flush_s} s.</p>
    {#if cfg.trends.write}
      {@const w = cfg.trends.write}
    <p>Siden tjenesten startede ({fmtUp(w.uptime_s)} siden): <strong>{fmtNum(w.rows)}</strong> rækker i {fmtNum(w.flushes)} skrivninger.
      {#if w.rows_per_day !== null}Overslag: <strong>ca. {fmtNum(w.rows_per_day)} rækker</strong> og {fmtNum(w.flushes_per_day ?? 0)} skrivninger pr. døgn.
      {:else}<span class="muted">Overslag pr. døgn vises efter 10 minutters drift.</span>{/if}</p>
    {/if}
    <h4>Indstillinger</h4>
    <form class="settings" onsubmit={(e) => { e.preventDefault(); saveTrends(); }}>
      <label>Opbevaring af historik (dage)
        <input type="number" bind:value={retention} min={cfg.trends.limits.retention_days.min} max={cfg.trends.limits.retention_days.max} step="1" />
      </label>
      <label>Skriveinterval (sekunder)
        <input type="number" bind:value={flush} min={cfg.trends.limits.flush_s.min} max={cfg.trends.limits.flush_s.max} step="1" />
      </label>
      <label>Opbevaring af energi (dage)
        <input type="number" bind:value={energy} min={cfg.trends.limits.energy_days.min} max={cfg.trends.limits.energy_days.max} step="1" />
      </label>
      <div class="row">
        <button class="primary" type="submit" disabled={saving || !dirty}>{saving ? 'Gemmer …' : 'Gem'}</button>
        {#if dirty}<button type="button" onclick={() => cfg && fillForm(cfg.trends)}>Fortryd</button>{/if}
        {#if saved && !dirty}<span class="muted small">{saved}</span>{/if}
        {#if cfg.trends.overridden && !dirty && !saved}<span class="muted small">Værdierne er sat her (overstyrer standarden fra serverens opsætning).</span>{/if}
      </div>
      {#if saveError}<div class="error">{saveError}</div>{/if}
      <p class="muted small">Et længere skriveinterval giver færre skrivninger til disken, men ved strømsvigt kan op til så mange sekunder af de nyeste værdier gå tabt. Ældre historik end opbevaringstiden slettes hver time.</p>
    </form>
    <p class="muted small">Rækkerne er ca. 20–40 byte hver; SQLite skriver desuden journal (WAL), så den faktiske skrivning til flash er et par gange større. Er datamappen på et SD-kort, så flyt den til en USB-SSD ved mange tags.</p>
  </section>

  <section class="panel">
    <h3>Netværk</h3>
    {#if !cfg.network.available}
      <div class="notice">{cfg.network.error || 'Netværksstatus er ikke tilgængelig'}</div>
    {/if}
    <p>Værtsnavn: <strong>{cfg.network.hostname}</strong>
      {#if cfg.network.gateway} · Gateway: <strong>{cfg.network.gateway}</strong>{/if}
      {#if cfg.network.dns.length} · DNS: <strong>{cfg.network.dns.join(', ')}</strong>{/if}</p>
    {#if cfg.network.interfaces.length}
      <table class="grid">
        <thead><tr><th>Netkort</th><th>Link</th><th>MAC</th><th>IPv4-adresser</th></tr></thead>
        <tbody>
          {#each cfg.network.interfaces as n (n.name)}
            <tr>
              <td><code>{n.name}</code></td><td>{n.state || '—'}</td><td><code>{n.mac || '—'}</code></td>
              <td>{#each n.addresses as a, i}{i ? ', ' : ''}<strong>{a.ip}</strong>{a.prefix !== null ? `/${a.prefix}` : ''}{:else}ingen{/each}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </section>
{/if}

<style>
  .settings { display: grid; gap: .5rem; max-width: 24rem; margin: .5rem 0; }
  .settings label { display: grid; gap: .15rem; font-size: .9rem; }
  .num { text-align: right; white-space: nowrap; }
  code { word-break: break-all; }
  table.grid { border-collapse: collapse; width: 100%; max-width: 48rem; }
  table.grid th, table.grid td { padding: .25rem .5rem; border-bottom: 1px solid var(--line); text-align: left; }
  table.grid th.num, table.grid td.num { text-align: right; }
</style>
