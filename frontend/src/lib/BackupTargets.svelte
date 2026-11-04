<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { api, del, get, patch, post } from './api';
  import { ask } from './ask';
  import {
    DAYS, METHODS, emptyTarget, fmtBytes, formFromTarget, needsPassword, scheduleText, targetBody, targetWhere,
    type Schedule, type Target, type TargetForm,
  } from './backupTargets';

  let sched = $state<Schedule | null>(null);
  let schedForm = $state<Schedule>({ mode: 'interval', every_h: 24, time: '02:30', days: [0, 1, 2, 3, 4, 5, 6] });
  let targets = $state<Target[]>([]);
  let form = $state<TargetForm>(emptyTarget());
  let editing = $state<string | null>(null);
  let showForm = $state(false);
  let busy = $state(false);
  let error = $state('');
  let msg = $state('');
  let tests = $state<Record<string, { ok: boolean; error: string; host_key: string | null }>>({});
  let timer: ReturnType<typeof setInterval> | undefined;

  const hint = $derived(METHODS.find((m) => m.id === form.method)?.hint ?? '');
  const current = $derived(editing ? targets.find((t) => t.id === editing) ?? null : null);
  const when = (ts: number | null | undefined) => (ts ? new Date(ts * 1000).toLocaleString('da-DK') : '—');

  async function load(): Promise<void> {
    try {
      [sched, targets] = await Promise.all([get<Schedule>('/api/backup/schedule'), get<Target[]>('/api/backup/targets')]);
    } catch (e) {
      error = (e as Error).message;
    }
  }
  onMount(async () => {
    await load();
    if (sched) schedForm = { mode: sched.mode, every_h: sched.every_h, time: sched.time, days: [...sched.days] };
    timer = setInterval(load, 10000);          // næste kørsel, resultater og "kører nu" holdes opdateret
  });
  onDestroy(() => clearInterval(timer));

  async function act(fn: () => Promise<void>): Promise<void> {
    busy = true; error = ''; msg = '';
    try {
      await fn();
      await load();
    } catch (e) {
      error = (e as Error).message;               // backendens præcise fejl
    } finally {
      busy = false;
    }
  }

  const saveSchedule = () => act(async () => {
    sched = await api<Schedule>('PUT', '/api/backup/schedule', { mode: schedForm.mode, every_h: Number(schedForm.every_h), time: schedForm.time, days: schedForm.days });
    msg = 'Tidsplanen er gemt.';
  });
  const runNow = () => act(async () => { await post('/api/backup/run', {}); msg = 'Backup startet — resultatet vises herunder om lidt.'; });

  function toggleDay(d: number): void {
    schedForm.days = schedForm.days.includes(d) ? schedForm.days.filter((x) => x !== d) : [...schedForm.days, d].sort();
  }

  function newTarget(): void { form = emptyTarget(); editing = null; showForm = true; error = ''; }
  function edit(t: Target): void { form = formFromTarget(t); editing = t.id; showForm = true; error = ''; }

  const saveTarget = () => act(async () => {
    const body = targetBody(form);
    if (editing) await patch(`/api/backup/targets/${editing}`, body);
    else await post('/api/backup/targets', body);
    showForm = false; editing = null;
  });

  const remove = async (t: Target) => {
    if (!(await ask(`Slet destinationen "${t.name}"? Filer, der allerede er sendt, bliver liggende på fjernsiden.`, { ok: 'Slet', danger: true }))) return;
    await act(async () => { await del(`/api/backup/targets/${t.id}`); if (editing === t.id) showForm = false; });
  };

  const test = (t: Target, trustFingerprint?: string) => act(async () => {
    tests[t.id] = await post(`/api/backup/targets/${t.id}/test`, trustFingerprint ? { trust_fingerprint: trustFingerprint } : {});
  });

  const makeKey = async (t: Target) => {
    if (t.public_key && !(await ask('Lav en ny SSH-nøgle? Den gamle virker ikke længere, og den nye skal lægges på serveren.', { ok: 'Ny nøgle' }))) return;
    await act(async () => { await post(`/api/backup/targets/${t.id}/ssh-key`, {}); });
  };
</script>

{#if error}<div class="error">{error}</div>{/if}
{#if msg}<div class="notice ok-box">{msg}</div>{/if}

<section class="panel">
  <h2>Automatisk backup — tidsplan</h2>
  <p class="muted small">
    Tager en backup af konfigurationen og et øjebliksbillede af trend-historikken på serveren og sender dem til destinationerne nedenfor.
    {#if sched}<br />Nu: <strong>{scheduleText(sched)}</strong> · næste kørsel {when(sched.next_run)} · seneste {when(sched.last_run)}{#if sched.running} · <strong>kører nu …</strong>{/if}{/if}
  </p>
  <div class="row wrap">
    <select bind:value={schedForm.mode} disabled={busy} aria-label="Tidsplan">
      <option value="interval">Med fast interval</option><option value="daily">Dagligt</option><option value="weekly">Bestemte ugedage</option><option value="off">Slået fra</option>
    </select>
    {#if schedForm.mode === 'interval'}
      <label class="inline">hver <input type="number" min="1" max="744" step="1" bind:value={schedForm.every_h} disabled={busy} /> time</label>
    {:else if schedForm.mode !== 'off'}
      {#if schedForm.mode === 'weekly'}
        {#each DAYS as d, i (d)}<label class="inline"><input type="checkbox" checked={schedForm.days.includes(i)} onchange={() => toggleDay(i)} disabled={busy} />{d}</label>{/each}
      {/if}
      <label class="inline">kl. <input type="time" bind:value={schedForm.time} disabled={busy} /></label>
    {/if}
    <button class="primary" onclick={saveSchedule} disabled={busy}>Gem tidsplan</button>
    <button onclick={runNow} disabled={busy || sched?.running}>Kør backup nu</button>
  </div>
</section>

<section class="panel">
  <h2>Destinationer</h2>
  <p class="muted small">Backuppen sendes til hver destination, der er slået til. Adgangskoder og nøgler kan ikke læses igen. Fejler en destination to gange i træk, vises det på Status og som systemalarm.</p>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Navn</th><th>Hvor</th><th>Sender</th><th>Seneste</th><th></th></tr></thead>
      <tbody>
        {#each targets as t (t.id)}
          <tr>
            <td>{t.name}{#if !t.enabled} <span class="badge off">slået fra</span>{/if}<div class="muted small">{t.method.toUpperCase()}{#if t.keep} · behold {t.keep}{/if}</div></td>
            <td class="small mono">{targetWhere(t)}
              {#if t.host_key}<div class="muted">værtsnøgle {t.host_key}</div>{/if}
              {#if t.mount}<div class={t.mount.ok ? 'muted' : 'error-text'}>{t.mount.ok ? 'monteret' : `ikke monteret: ${t.mount.error}`}</div>{/if}</td>
            <td class="small">{[t.send_config && 'konfiguration', t.send_trends && 'historik'].filter(Boolean).join(' + ')}</td>
            <td class="small">
              {#if t.last}
                <span class="badge {t.last.ok ? 'ok' : 'err'}">{t.last.ok ? 'ok' : 'fejl'}</span> {when(t.last.at)}
                {#if t.last.ok}<div class="muted">{t.last.files.length} filer · {fmtBytes(t.last.bytes)} · {t.last.duration_s} s</div>{:else}<div class="error-text">{t.last.error}</div>{/if}
              {:else}<span class="muted">ikke kørt endnu</span>{/if}
              {#if tests[t.id]}
                <div class={tests[t.id].ok ? 'ok-text' : 'error-text'}>Test: {tests[t.id].ok ? 'forbindelsen virker (testfil skrevet og slettet)' : tests[t.id].error}</div>
                {#if tests[t.id].host_key}
                  <div class="small">Serverens værtsnøgle: <span class="mono">{tests[t.id].host_key}</span> — sammenlign med serveren, før du godkender.
                    <button onclick={() => test(t, tests[t.id].host_key!)} disabled={busy}>Godkend og test igen</button></div>
                {/if}
              {/if}
            </td>
            <td class="nowrap">
              <button onclick={() => test(t)} disabled={busy}>Test forbindelse</button>
              <button onclick={() => edit(t)} disabled={busy}>Redigér</button>
              <button onclick={() => remove(t)} disabled={busy}>Slet</button>
            </td>
          </tr>
        {:else}
          <tr><td colspan="5" class="muted">Ingen destinationer — backuppen gemmes kun på serveren selv.</td></tr>
        {/each}
      </tbody>
    </table>
  </div>
  {#if !showForm}<button onclick={newTarget} disabled={busy}>Tilføj destination</button>{/if}

  {#if showForm}
    <h3>{editing ? 'Redigér destination' : 'Ny destination'}</h3>
    <form class="grid" onsubmit={(e) => { e.preventDefault(); saveTarget(); }}>
      <label>Navn <input bind:value={form.name} placeholder="NAS i kontoret" disabled={busy} /></label>
      <label>Metode
        <select bind:value={form.method} disabled={busy}>{#each METHODS as m (m.id)}<option value={m.id}>{m.label}</option>{/each}</select>
        <span class="muted small">{hint}</span>
      </label>
      {#if ['sftp', 'scp', 'ftp', 'ftps', 'smb'].includes(form.method)}
        <div class="two">
          <label>Server (navn eller IP) <input bind:value={form.host} placeholder="nas.local" disabled={busy} /></label>
          <label>Port <input bind:value={form.port} placeholder="standard" inputmode="numeric" disabled={busy} /></label>
        </div>
        {#if form.method === 'smb'}<label>Share <input bind:value={form.share} placeholder="backup" disabled={busy} /></label>{/if}
        <label>Brugernavn <input bind:value={form.username} autocomplete="off" disabled={busy} /></label>
      {/if}
      {#if form.method === 'sftp' || form.method === 'scp'}
        <fieldset class="opts"><legend>Login</legend>
          <label class="check"><input type="radio" bind:group={form.auth} value="password" disabled={busy} /> Adgangskode</label>
          <label class="check"><input type="radio" bind:group={form.auth} value="key" disabled={busy} /> SSH-nøgle (laves her; den offentlige del lægges i serverens authorized_keys)</label>
        </fieldset>
        {#if form.auth === 'key' && current}
          <div class="small">
            {#if current.public_key}<textarea class="mono" readonly rows="2" onclick={(e) => e.currentTarget.select()}>{current.public_key}</textarea>{/if}
            <button type="button" onclick={() => makeKey(current!)} disabled={busy}>{current.public_key ? 'Lav ny nøgle' : 'Lav SSH-nøgle'}</button>
          </div>
        {:else if form.auth === 'key'}<p class="muted small">Gem destinationen først — derefter kan nøglen laves.</p>{/if}
      {/if}
      {#if form.method === 'https'}
        <label>Adresse (filen lægges som &lt;adresse&gt;/&lt;filnavn&gt;) <input bind:value={form.url} placeholder="https://cloud.example.com/remote.php/dav/files/scada/backup" disabled={busy} /></label>
        <label>Login <select bind:value={form.http_auth} disabled={busy}><option value="none">Intet</option><option value="basic">Brugernavn + adgangskode</option><option value="bearer">Token (Bearer)</option></select></label>
        {#if form.http_auth === 'basic'}<label>Brugernavn <input bind:value={form.username} autocomplete="off" disabled={busy} /></label>{/if}
      {/if}
      {#if form.method === 'nfs'}
        <label>NFS-eksport (vært:/sti) <input bind:value={form.export} placeholder="nas.local:/volume1/backup" disabled={busy} />
          <span class="muted small">Eksporten skal tillade skrivning for Pi'ens IP-adresse (brugeren scada).</span></label>
      {/if}
      {#if needsPassword(form)}
        <label>{form.method === 'https' && form.http_auth === 'bearer' ? 'Token' : 'Adgangskode'}
          <input type="password" bind:value={form.password} autocomplete="new-password" disabled={busy}
                 placeholder={current?.has_password ? 'gemt — udfyld kun for at ændre' : ''} /></label>
      {/if}
      <label>Mappe på fjernsiden (valgfri) <input bind:value={form.path} placeholder="scada/pi1" disabled={busy} /></label>
      {#if form.method === 'ftps' || form.method === 'https'}
        <label class="check"><input type="checkbox" bind:checked={form.verify_tls} disabled={busy} /> Kontrollér serverens certifikat (slå kun fra ved selvsigneret)</label>
      {/if}
      <fieldset class="opts"><legend>Send</legend>
        <label class="check"><input type="checkbox" bind:checked={form.send_config} disabled={busy} /> Konfiguration (lille)</label>
        <label class="check"><input type="checkbox" bind:checked={form.send_trends} disabled={busy} /> Trend-historik (kan være stor)</label>
      </fieldset>
      {#if form.method !== 'https'}
        <label>Behold de seneste <input type="number" min="0" max="365" bind:value={form.keep} disabled={busy} /> <span class="muted small">af hver slags på fjernsiden (0 = ryd aldrig op; kun egne filer slettes)</span></label>
      {/if}
      <label class="check"><input type="checkbox" bind:checked={form.enabled} disabled={busy} /> Slået til</label>
      <div class="row">
        <button class="primary" type="submit" disabled={busy}>{editing ? 'Gem ændringer' : 'Opret destination'}</button>
        <button type="button" onclick={() => { showForm = false; editing = null; }} disabled={busy}>Annullér</button>
      </div>
      {#if !editing && (form.method === 'sftp' || form.method === 'scp')}<p class="muted small">Efter oprettelsen: tryk <em>Test forbindelse</em> og godkend serverens værtsnøgle.</p>{/if}
    </form>
  {/if}
</section>

<style>
  .grid { display: grid; gap: 0.5rem; max-width: 36rem; }
  .grid label { display: grid; gap: 0.2rem; }
  .grid label.check { display: flex; gap: 0.4rem; align-items: center; }
  .two { display: grid; grid-template-columns: 1fr 7rem; gap: 0.5rem; }
  fieldset.opts { border: 1px solid var(--line); border-radius: var(--radius); padding: 0.4rem 0.6rem; }
  .wrap { flex-wrap: wrap; align-items: center; gap: 0.5rem; }
  label.inline { display: inline-flex; gap: 0.3rem; align-items: center; }
  label.inline input[type='number'] { width: 5rem; }
  h3 { margin: 1rem 0 0.2rem; font-size: 1rem; }
  textarea { width: 100%; box-sizing: border-box; font: inherit; }
  .nowrap { white-space: nowrap; }
  .ok-box { background: #e8f5e9; border-color: #a5d6a7; }
  .error-text { color: var(--err, #b3261e); }
  .ok-text { color: #2e7d32; }
</style>
