<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { ask } from '../lib/ask';
  import { api, get } from '../lib/api';

  interface Nic { name: string; mac: string; state: string; addresses: { ip: string; prefix: number | null }[] }
  interface Config {
    storage: { path: string; files: { name: string; size: number }[]; folders: { name: string; size: number }[];
      disk: { total: number; used: number; free: number } | null };
    trends: { retention_days: number; flush_s: number; energy_days: number; overridden: boolean;
      limits: Record<string, { min: number; max: number }>;
      storage: { path: string; configured: string; warning: string; roots: string[] }; tags: number; samples: number;
      write: { since: number; uptime_s: number; rows: number; flushes: number; rows_per_day: number | null; flushes_per_day: number | null } };
    network_config: NetState;
    network: { available: boolean; hostname: string; interfaces: Nic[]; gateway: string; dns: string[]; error: string };
  }

  interface NetTarget { interface: string; mode: string; ip: string; prefix: number; gateway: string; dns: string[]; hostname: string; fallback_after?: number }
  interface Watchdog { state: string; message: string; mode: string; fails: number; threshold: number; fallback_active: boolean; ts: number; stale?: boolean }
  interface NetState { enabled: boolean; disabled_reason?: string; watchdog?: Watchdog | null; state: string; message: string; deadline: number | null; confirm_s: number; busy: boolean;
    target: NetTarget | null; saved: NetTarget | null }

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
      net = cfg.network_config;
      if (!netFilled) { fillNet(net.saved); netFilled = true; }
      if (net.busy) startPolling();
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

  // ---- Placering af trend-databasen
  let moveDir = $state('');
  let moving = $state(false);
  let moveError = $state('');
  let moveDone = $state('');

  async function moveDb(dir: string): Promise<void> {
    moveError = moveDone = '';
    const text = dir === ''
      ? 'Flyt trend-databasen tilbage til datamappen?\n\nHistorikken kopieres, kontrolleres og tages i brug. Den gamle fil gemmes som trends.db.moved.'
      : `Flyt trend-databasen til ${dir}?\n\nHistorikken kopieres, kontrolleres og tages i brug mens SCADA'en kører (trends står stille et øjeblik). Den gamle fil gemmes som trends.db.moved, til du selv sletter den.`;
    if (!await ask(text)) return;
    moving = true;
    try {
      const t = await api<Config['trends']>('PUT', '/api/system/config/storage', { trend_dir: dir });
      if (cfg) cfg.trends = t;
      moveDone = `Databasen ligger nu i ${t.storage.path}`;
      moveDir = '';
      await refresh();
    } catch (e) {
      moveError = (e as Error).message;
    } finally {
      moving = false;
    }
  }

  // ---- Netværk: formular, anvend, bekræft
  let nIface = $state('');
  let nMode = $state('dhcp');
  let nIp = $state('');
  let nPrefix = $state(24);
  let nGateway = $state('');
  let nDns = $state('');
  let nHost = $state('');
  let nFallback = $state(5);
  let net = $state<NetState | null>(null);
  let netBusy = $state(false);
  let netError = $state('');
  let now = $state(Date.now() / 1000);
  let poll: ReturnType<typeof setInterval> | null = null;
  let netFilled = false;

  const MODE_TEXT: Record<string, string> = { dhcp: 'DHCP', static: 'Fast IP', dhcp_static: 'DHCP + fast IP som sekundær', dhcp_fallback: 'DHCP, fast IP efter N fejl' };
  const STATE_TEXT: Record<string, string> = {
    idle: '', queued: 'Anmodning sendt …', applying: 'Anvender …', waiting_confirm: 'Venter på din bekræftelse',
    confirmed: 'Bekræftet', reverted: 'Gendannet', failed: 'Mislykkedes', stalled: 'Hjælperen svarer ikke',
  };
  const dnsList = (): string[] => nDns.split(/[\s,;]+/).filter(Boolean);
  const left = $derived(net?.deadline ? Math.max(0, Math.ceil(net.deadline - now)) : 0);

  function fillNet(t: NetTarget | null): void {
    const nic = cfg?.network.interfaces ?? [];
    nIface = t?.interface && nic.some((n) => n.name === t.interface) ? t.interface : (nic[0]?.name ?? '');
    const first = nic.find((n) => n.name === nIface)?.addresses[0];
    nMode = t?.mode ?? 'dhcp';
    nIp = t?.ip || first?.ip || '';
    nPrefix = t?.prefix || first?.prefix || 24;
    nGateway = t?.gateway ?? cfg?.network.gateway ?? '';
    nDns = (t?.dns ?? cfg?.network.dns ?? []).join(', ');
    nHost = t?.hostname || cfg?.network.hostname || '';
    nFallback = t?.fallback_after || 5;
  }

  async function refreshNet(): Promise<void> {
    try {
      net = await get<NetState>('/api/system/config/network');
      netError = '';
    } catch (e) {
      // Under en ændring kan forbindelsen forsvinde et øjeblik (ny adresse) — det er en del af forløbet
      if (net?.busy) netError = 'Forbindelsen til serveren er afbrudt — hvis adressen er ændret, så åbn siden på den nye adresse og tryk Bekræft.';
      else netError = (e as Error).message;
    }
    now = Date.now() / 1000;
    if (net && !net.busy && poll) { clearInterval(poll); poll = null; }
  }
  function startPolling(): void {
    if (!poll) poll = setInterval(refreshNet, 2000);
  }

  async function applyNet(): Promise<void> {
    netError = '';
    const msg = nMode === 'dhcp'
      ? 'Skift til DHCP?\n\nAdressen bestemmes af routeren og kan ændre sig. Du får 90 sekunder til at åbne siden på den nye adresse og trykke Bekræft — ellers gendannes den gamle opsætning.'
      : `Skift til ${MODE_TEXT[nMode]} med ${nIp}/${nPrefix}?\n\nDu får 90 sekunder til at åbne siden på ${nIp} og trykke Bekræft — ellers gendannes den gamle opsætning automatisk.`;
    if (!await ask(msg, { danger: true })) return;
    netBusy = true;
    try {
      net = await api<NetState>('PUT', '/api/system/config/network', {
        interface: nIface, mode: nMode, ip: nMode === 'dhcp' ? '' : nIp, prefix: nMode === 'dhcp' ? 0 : Number(nPrefix),
        gateway: nMode === 'static' || nMode === 'dhcp_fallback' ? nGateway : '', dns: dnsList(), hostname: nHost,
        fallback_after: Number(nFallback),
      });
      startPolling();
    } catch (e) {
      netError = (e as Error).message;
    } finally {
      netBusy = false;
    }
  }
  async function confirmNet(): Promise<void> {
    netBusy = true;
    try {
      net = await api<NetState>('POST', '/api/system/config/network/confirm');
      netError = '';
      await refresh();
    } catch (e) {
      netError = (e as Error).message;
    } finally {
      netBusy = false;
    }
  }
  async function revertNet(): Promise<void> {
    netBusy = true;
    try {
      net = await api<NetState>('POST', '/api/system/config/network/revert');
      startPolling();
    } catch (e) {
      netError = (e as Error).message;
    } finally {
      netBusy = false;
    }
  }
  onDestroy(() => { if (poll) clearInterval(poll); });

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
    <h4>Placering af trend-databasen</h4>
    <p>Ligger i: <code>{cfg.trends.storage.path}</code></p>
    {#if cfg.trends.storage.warning}<div class="notice warn">{cfg.trends.storage.warning}</div>{/if}
    <form class="settings" onsubmit={(e) => { e.preventDefault(); moveDb(moveDir.trim()); }}>
      <label>Flyt til mappe (under {cfg.trends.storage.roots.join(' eller ')})
        <input bind:value={moveDir} placeholder="/mnt/ssd/scada" disabled={moving} />
      </label>
      <div class="row">
        <button class="primary" type="submit" disabled={moving || !moveDir.trim()}>{moving ? 'Flytter …' : 'Flyt databasen'}</button>
        {#if cfg.trends.storage.configured}<button type="button" onclick={() => moveDb('')} disabled={moving}>Tilbage til datamappen</button>{/if}
      </div>
      {#if moveDone}<span class="muted small">{moveDone}</span>{/if}
      {#if moveError}<div class="error">{moveError}</div>{/if}
      <p class="muted small">Brug en USB-SSD i stedet for SD-kortet til historikken. Monter disken først, og opret mappen én gang på maskinen med
        <code>sudo install -d -o scada -g scada -m 0750 /mnt/ssd/scada</code>. Historikken kopieres og kontrolleres, før den tages i brug;
        den gamle fil bliver liggende som <code>trends.db.moved</code>. Mangler disken ved en genstart, starter SCADA'en alligevel med en tom database i datamappen og viser en advarsel her.</p>
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
    <h4>Netværksopsætning</h4>
    {#if !net?.enabled}
      <div class="notice">
        {#if net?.disabled_reason === 'no_nmcli'}
          <strong>NetworkManager (<code>nmcli</code>) findes ikke på denne maskine</strong>, så netværket kan ikke ændres fra web. Raspberry Pi OS Bookworm har det som standard;
          ældre systemer bruger <code>dhcpcd</code>/<code>ifupdown</code>. Tjek med <code>command -v nmcli</code> og <code>nmcli general status</code>.
        {:else}
          <strong>Netværkshjælperen er ikke installeret.</strong> Kør <code>sudo sh deploy/install.sh --update</code> på maskinen (en OTA-opdatering gør det automatisk). Tjek derefter
          <code>ls /var/lib/hypervisionplc-scada-net</code> — filen <code>enabled</code> skal findes.
        {/if}
      </div>
    {:else}
      {#if net.watchdog && !net.watchdog.stale && net.watchdog.mode !== 'static'}
        <p class="small">DHCP-vagt: <strong>{net.watchdog.message}</strong>
          {#if net.watchdog.state === 'searching'} ({net.watchdog.fails}{net.watchdog.mode === 'dhcp_fallback' ? ` af ${net.watchdog.threshold}` : ''} kontroller uden svar){/if}</p>
      {/if}
      {#if net.busy || ['confirmed', 'reverted', 'failed', 'stalled'].includes(net.state)}
        <div class="notice" class:warn={net.state === 'waiting_confirm'}>
          <strong>{STATE_TEXT[net.state] ?? net.state}</strong>{net.message ? ` — ${net.message}` : ''}
          {#if net.state === 'waiting_confirm'}
            <p>Du har <strong>{left} sekunder</strong>.
              {#if net.target && net.target.mode !== 'dhcp'}Åbn siden på <a href="http://{net.target.ip}/">http://{net.target.ip}/</a> og tryk <em>Bekræft</em>.{:else}Find maskinens nye adresse (routerens liste) og tryk <em>Bekræft</em> derfra.{/if}
              Trykker du ikke, gendannes den gamle opsætning.</p>
            <div class="row">
              <button class="primary" onclick={confirmNet} disabled={netBusy}>Bekræft</button>
              <button onclick={revertNet} disabled={netBusy}>Fortryd nu</button>
            </div>
          {/if}
        </div>
      {/if}
      {#if netError}<div class="error">{netError}</div>{/if}
      <form class="settings" onsubmit={(e) => { e.preventDefault(); applyNet(); }}>
        <label>Netkort
          <select bind:value={nIface} disabled={net.busy}>{#each cfg.network.interfaces as n (n.name)}<option value={n.name}>{n.name}</option>{/each}</select>
        </label>
        <label>Tilstand
          <select bind:value={nMode} disabled={net.busy}>
            <option value="dhcp">DHCP (adresse fra routeren)</option>
            <option value="static">Fast IP</option>
            <option value="dhcp_static">DHCP + fast IP som sekundær adresse</option>
            <option value="dhcp_fallback">DHCP, fast IP først efter N fejl</option>
          </select>
        </label>
        {#if nMode !== 'dhcp'}
          <label>IP-adresse <input bind:value={nIp} placeholder="192.168.1.50" disabled={net.busy} /></label>
          <label>Subnet-præfiks (24 = 255.255.255.0) <input type="number" min="8" max="30" bind:value={nPrefix} disabled={net.busy} /></label>
        {/if}
        {#if nMode === 'dhcp_fallback'}
          <label>Tag reserve-IP'en efter så mange kontroller uden DHCP-svar (à 30 sekunder)
            <input type="number" min="1" max="20" bind:value={nFallback} disabled={net.busy} />
          </label>
        {/if}
        {#if nMode === 'static' || nMode === 'dhcp_fallback'}
          <label>Gateway (valgfri) <input bind:value={nGateway} placeholder="192.168.1.1" disabled={net.busy} /></label>
        {/if}
        <label>DNS-servere (kommasepareret, højst 3){nMode === 'static' ? '' : ' — tom = fra DHCP'}
          <input bind:value={nDns} placeholder="192.168.1.1, 8.8.8.8" disabled={net.busy} />
        </label>
        <label>Værtsnavn <input bind:value={nHost} placeholder="scada" disabled={net.busy} /></label>
        <div class="row"><button class="primary" type="submit" disabled={netBusy || net.busy || !nIface}>Anvend netværksopsætning</button></div>
        <p class="muted small">Opsætningen anvendes med det samme. Du har derefter {net.confirm_s} sekunder til at bekræfte fra den nye adresse — ellers gendannes den gamle automatisk, så du ikke låser dig ude.</p>
      </form>
    {/if}
  </section>
{/if}

<style>
  .notice.warn { border-left-color: #d9822b; }
  .settings { display: grid; gap: .5rem; max-width: 24rem; margin: .5rem 0; }
  .settings label { display: grid; gap: .15rem; font-size: .9rem; }
  .num { text-align: right; white-space: nowrap; }
  code { word-break: break-all; }
  table.grid { border-collapse: collapse; width: 100%; max-width: 48rem; }
  table.grid th, table.grid td { padding: .25rem .5rem; border-bottom: 1px solid var(--line); text-align: left; }
  table.grid th.num, table.grid td.num { text-align: right; }
</style>
