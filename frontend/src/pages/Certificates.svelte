<script lang="ts">
  import { onMount } from 'svelte';
  import { del, get, post } from '../lib/api';
  import { ask } from '../lib/ask';
  import {
    KEY_TYPES, KIND_LABEL, LE_ACTION, daysLeft, leBusy, leHostOk, emptySubject, fileBase64, fmtDate, hostCovered, parseSans, subjectBody,
    type LeStatus, type SubjectForm, type TlsStatus,
  } from '../lib/certificates';

  const host = location.hostname;
  let st = $state<TlsStatus | null>(null);
  let error = $state('');
  let notice = $state('');
  let warnings = $state<string[]>([]);
  let busy = $state(false);
  let mode = $state<'selfsigned' | 'csr' | 'import'>('selfsigned');
  let subj = $state<SubjectForm>(emptySubject(host));
  let days = $state(825);
  let signed = $state('');
  let fmt = $state<'pkcs12' | 'pem'>('pkcs12');
  let p12File = $state<File | null>(null);
  let certPem = $state('');
  let keyPem = $state('');
  let password = $state('');

  const cert = $derived(st?.cert ?? null);
  const covered = $derived(cert ? hostCovered(host, cert.sans) : true);
  const newCovers = $derived(hostCovered(host, parseSans(subj.sans)));

  async function load(): Promise<void> {
    try {
      st = await get<TlsStatus>('/api/system/tls');
      if (st.cert && subj.sans === host) {                     // forudfyld med det nuværende certifikats navne
        subj.sans = [...new Set([...st.cert.sans, host])].join(', ');
        if (st.cert.cn) subj.cn = st.cert.cn;
      }
      error = '';
    } catch (e) {
      error = (e as Error).message;
    }
  }
  // ---------- Let's Encrypt
  let le = $state<LeStatus | null>(null);
  let leMethod = $state<'http' | 'dns'>('http');
  let leHost = $state('');
  let leEmail = $state('');
  let leZone = $state('');
  let leSub = $state('scada-acme');
  let leToken = $state('');
  let leError = $state('');
  let showLog = $state(false);
  let pollTimer: ReturnType<typeof setTimeout> | undefined;
  let wasBusy = false;

  async function loadLe(): Promise<void> {
    clearTimeout(pollTimer);
    try {
      le = await get<LeStatus>('/api/system/tls/le');
      const i = le.info;
      if (i && !leZone && i.zone) { leZone = i.zone; leSub = i.sub || 'scada-acme'; }
      if (i?.last && !leHost) { leHost = i.last.host; leEmail = i.last.email; leMethod = i.last.method; }
      if (!leHost && cert?.cn && leHostOk(cert.cn)) leHost = cert.cn;
    } catch (e) {
      leError = (e as Error).message;
    }
    const busyNow = leBusy(le);
    if (wasBusy && !busyNow) await load();          // færdig → det installerede certifikat kan være skiftet
    wasBusy = busyNow;
    if (busyNow || !le?.info) pollTimer = setTimeout(loadLe, 2000);
  }

  async function leRun(path: string, body: unknown): Promise<void> {
    leError = '';
    try {
      await post(`/api/system/tls/le/${path}`, body);
      showLog = true;
    } catch (e) {
      leError = (e as Error).message;
    }
    await loadLe();
  }

  const leInstall = () => leRun('install', {});
  async function leDns(): Promise<void> {
    await leRun('dns', { zone: leZone, sub: leSub, token: leToken || undefined });
    leToken = '';
  }
  async function leIssue(dry: boolean): Promise<void> {
    if (!dry && !(await ask(`Udsted et Let's Encrypt-certifikat til ${leHost} og tag det i brug?\n\nLykkes det, installeres det automatisk (med kontrol og gendannelse ved fejl) og fornys derefter af sig selv. Kør gerne "Test (staging)" først — Let's Encrypt har grænser for, hvor mange rigtige forsøg man må lave.`, { ok: 'Udsted' }))) return;
    await leRun('issue', { method: leMethod, host: leHost.trim().toLowerCase(), email: leEmail.trim(), dry_run: dry });
  }

  onMount(() => { load().then(loadLe); return () => clearTimeout(pollTimer); });

  async function run(fn: () => Promise<TlsStatus | void>, done: string): Promise<void> {
    busy = true; error = ''; notice = ''; warnings = [];
    try {
      const r = await fn();
      if (r && 'cert' in r) { st = r; warnings = r.warnings ?? []; } else await load();
      notice = done;
    } catch (e) {
      error = (e as Error).message;
      await load();
    } finally {
      busy = false;
    }
  }

  const confirmSwitch = (what: string, covers: boolean) =>
    ask(`${what}\n\nnginx genindlæses med det nye certifikat. Passer det ikke, gendannes det forrige automatisk.` +
      (covers ? '' : `\n\nADVARSEL: "${host}" (adressen du bruger nu) står ikke i certifikatets navne — browseren vil advare.`),
      { ok: 'Installér', danger: !covers });

  async function makeSelfSigned(): Promise<void> {
    if (!(await confirmSwitch(`Lav og installér et selvsigneret certifikat for ${parseSans(subj.sans).join(', ')}?`, newCovers))) return;
    await run(() => post<TlsStatus>('/api/system/tls/selfsigned', subjectBody(subj, { days: Number(days) })), 'Det selvsignerede certifikat er installeret.');
  }

  const makeCsr = () => run(() => post('/api/system/tls/csr', subjectBody(subj)).then(() => undefined),
    'CSR er oprettet — hent den og send den til din CA. Den private nøgle bliver på serveren.');

  async function cancelCsr(): Promise<void> {
    if (!(await ask('Annullér den ventende CSR? Den private nøgle slettes, så et certifikat udstedt til den kan ikke længere bruges.', { ok: 'Annullér CSR', danger: true }))) return;
    await run(() => del('/api/system/tls/csr').then(() => undefined), 'Den ventende CSR er annulleret.');
  }

  async function installSigned(): Promise<void> {
    if (!(await confirmSwitch('Installér det signerede certifikat?', hostCovered(host, st?.pending_csr?.sans ?? [])))) return;
    await run(() => post<TlsStatus>('/api/system/tls/signed', { cert: signed }), 'Det signerede certifikat er installeret.');
    if (!error) signed = '';
  }

  async function doImport(): Promise<void> {
    if (!(await confirmSwitch('Importér og installér certifikatet?', true))) return;
    await run(async () => {
      if (fmt === 'pkcs12') {
        if (!p12File) throw new Error('Vælg en .p12/.pfx-fil');
        return post<TlsStatus>('/api/system/tls/import', { format: 'pkcs12', p12: await fileBase64(p12File), password });
      }
      return post<TlsStatus>('/api/system/tls/import', { format: 'pem', cert: certPem, key: keyPem, password });
    }, 'Certifikatet er importeret og installeret.');
    if (!error) { password = ''; keyPem = ''; certPem = ''; p12File = null; }
  }

  async function restore(which: 'prev' | 'selfsigned'): Promise<void> {
    const what = which === 'prev' ? 'det forrige certifikat' : 'det gemte selvsignerede certifikat';
    if (!(await ask(`Gendan ${what}? Det nuværende gemmes som "forrige".`, { ok: 'Gendan' }))) return;
    await run(() => post<TlsStatus>('/api/system/tls/restore', { which }), `${what[0].toUpperCase()}${what.slice(1)} er gendannet.`);
  }

  async function readFile(e: Event, set: (v: string) => void): Promise<void> {
    const f = (e.currentTarget as HTMLInputElement).files?.[0];
    if (f) set(await f.text());
  }

  function download(text: string, name: string): void {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], { type: 'application/pkcs10' }));
    a.download = name;
    a.click();
    URL.revokeObjectURL(a.href);
  }
</script>

<section class="panel">
  <h2>Certifikater</h2>
  <p class="muted small">
    Det certifikat, nginx bruger til HTTPS. Et nyt certifikat kontrolleres, før det tages i brug (passer nøglen, er det gyldigt, accepterer
    nginx det); går noget galt, gendannes det forrige automatisk. Private nøgler og adgangskoder sendes kun til serveren og vises aldrig igen.
  </p>
  {#if error}<div class="error">{error}</div>{/if}
  {#if notice}<div class="notice">{notice}</div>{/if}
  {#each warnings as w (w)}<div class="notice warn">{w}</div>{/each}

  <h3>Aktuelt certifikat</h3>
  {#if st === null}
    <p class="muted">Henter …</p>
  {:else if cert}
    {@const left = daysLeft(cert.not_after)}
    <table class="kv">
      <tbody>
        <tr><th>Type</th><td>{KIND_LABEL[cert.kind]}{st.chain ? ` (+ ${st.chain} i kæden)` : ''} · {cert.key}</td></tr>
        <tr><th>Navn (CN)</th><td class="mono">{cert.cn || '—'}</td></tr>
        <tr><th>Gælder for</th><td class="mono">{cert.sans.join(', ') || '—'}</td></tr>
        <tr><th>Udsteder</th><td class="mono small">{cert.issuer}</td></tr>
        <tr><th>Gyldig</th><td>{fmtDate(cert.not_before)} – {fmtDate(cert.not_after)}
          <span class:bad={left < 7} class:warn={left >= 7 && left < 21}>({left < 0 ? 'udløbet' : `${left} dage tilbage`})</span></td></tr>
        <tr><th>SHA-256</th><td class="mono small">{cert.fingerprint}</td></tr>
      </tbody>
    </table>
    {#if !covered}<div class="notice warn">"{host}" — adressen du bruger nu — står ikke i certifikatets navne, så browseren advarer.</div>{/if}
    <div class="row">
      <a class="button" href="/api/system/tls/cert.pem" download>Hent certifikat (PEM)</a>
      <button onclick={() => restore('prev')} disabled={busy || !st.has_prev}>Gendan forrige</button>
      <button onclick={() => restore('selfsigned')} disabled={busy || !st.has_selfsigned || cert.self_signed}>Tilbage til selvsigneret</button>
    </div>
  {:else}
    <p class="muted">Intet certifikat fundet — nginx/TLS er ikke installeret (install.sh --with-nginx), eller root-hjælperen har ikke kørt endnu.</p>
  {/if}
  {#if st?.last && !st.last.ok}<p class="small bad">Seneste forsøg ({fmtDate(st.last.at)}) mislykkedes: {st.last.message}</p>{/if}

  <h3>Nyt certifikat</h3>
  <div class="row">
    <label class="check"><input type="radio" bind:group={mode} value="selfsigned" /> Selvsigneret</label>
    <label class="check"><input type="radio" bind:group={mode} value="csr" /> CSR til en CA</label>
    <label class="check"><input type="radio" bind:group={mode} value="import" /> Importér (PKCS#12 / PEM)</label>
  </div>

  {#if mode === 'selfsigned' || (mode === 'csr' && !st?.pending_csr)}
    <p class="small muted">
      {#if mode === 'selfsigned'}
        Laves og installeres med det samme. Browsere advarer ved et selvsigneret certifikat, indtil det godkendes eller lægges ind som betroet.
      {:else}
        Nøglen laves på serveren og forlader den aldrig. Send CSR'en til din CA (fx virksomhedens interne CA) og læg det signerede certifikat ind bagefter.
      {/if}
    </p>
    <form class="grid" onsubmit={(e) => { e.preventDefault(); if (mode === 'selfsigned') makeSelfSigned(); else makeCsr(); }}>
      <label>Navn (CN) <input bind:value={subj.cn} required disabled={busy} /></label>
      <label>Gælder for — SAN (værtsnavne og IP-adresser, adskilt af komma)
        <textarea rows="2" bind:value={subj.sans} disabled={busy}></textarea>
        {#if !newCovers}<span class="small warn">"{host}" er ikke med — browseren vil advare, når du bruger den adresse.</span>{/if}
      </label>
      {#if mode === 'csr'}
        <label>Organisation (O) <input bind:value={subj.o} disabled={busy} /></label>
        <label>Afdeling (OU) <input bind:value={subj.ou} disabled={busy} /></label>
        <label>By (L) <input bind:value={subj.l} disabled={busy} /></label>
        <label>Region (ST) <input bind:value={subj.st} disabled={busy} /></label>
        <label>Land (C) <input bind:value={subj.c} maxlength="2" disabled={busy} /></label>
        <label>E-mail <input type="email" bind:value={subj.email} disabled={busy} /></label>
      {:else}
        <label>Gyldighed (dage) <input type="number" min="1" max="3650" bind:value={days} disabled={busy} /></label>
      {/if}
      <label>Nøgletype
        <select bind:value={subj.key_type} disabled={busy}>{#each KEY_TYPES as k (k.id)}<option value={k.id}>{k.label}</option>{/each}</select>
      </label>
      <div><button class="primary" disabled={busy}>{mode === 'selfsigned' ? 'Lav og installér' : 'Opret CSR'}</button></div>
    </form>
  {:else if mode === 'csr' && st?.pending_csr}
    {@const p = st.pending_csr}
    <div class="notice">
      <strong>Ventende CSR</strong> (oprettet {fmtDate(p.created)}) — <span class="mono small">{p.subject}</span><br />
      <span class="small">Gælder for: <span class="mono">{p.sans.join(', ')}</span></span>
    </div>
    <pre class="mono small">{p.pem}</pre>
    <div class="row">
      <button onclick={() => download(p.pem, `${(p.sans[0] || 'scada').replace(/[^a-z0-9.-]/gi, '_')}.csr`)}>Hent CSR</button>
      <button class="danger" onclick={cancelCsr} disabled={busy}>Annullér CSR</button>
    </div>
    <label class="stack">Det signerede certifikat (PEM — gerne med mellemcertifikater)
      <textarea rows="6" class="mono small" bind:value={signed} placeholder="-----BEGIN CERTIFICATE-----" disabled={busy}></textarea>
    </label>
    <div class="row">
      <input type="file" accept=".pem,.crt,.cer" onchange={(e) => readFile(e, (v) => (signed = v))} disabled={busy} />
      <button class="primary" onclick={installSigned} disabled={busy || !signed.trim()}>Installér</button>
    </div>
  {:else if mode === 'import'}
    <div class="row">
      <label class="check"><input type="radio" bind:group={fmt} value="pkcs12" /> PKCS#12 (.p12 / .pfx)</label>
      <label class="check"><input type="radio" bind:group={fmt} value="pem" /> PEM (certifikat + nøgle)</label>
    </div>
    <form class="grid" onsubmit={(e) => { e.preventDefault(); doImport(); }}>
      {#if fmt === 'pkcs12'}
        <label>Fil <input type="file" accept=".p12,.pfx" onchange={(e) => (p12File = (e.currentTarget as HTMLInputElement).files?.[0] ?? null)} disabled={busy} /></label>
      {:else}
        <label>Certifikat (+ kæde)
          <textarea rows="5" class="mono small" bind:value={certPem} placeholder="-----BEGIN CERTIFICATE-----" disabled={busy}></textarea>
          <input type="file" accept=".pem,.crt,.cer" onchange={(e) => readFile(e, (v) => (certPem = v))} disabled={busy} />
        </label>
        <label>Privat nøgle
          <textarea rows="5" class="mono small" bind:value={keyPem} placeholder="-----BEGIN PRIVATE KEY-----" disabled={busy}></textarea>
          <input type="file" accept=".pem,.key" onchange={(e) => readFile(e, (v) => (keyPem = v))} disabled={busy} />
        </label>
      {/if}
      <label>Adgangskode {fmt === 'pem' ? '(kun hvis nøglen er krypteret)' : ''}
        <input type="password" autocomplete="off" bind:value={password} disabled={busy} />
      </label>
      <div><button class="primary" disabled={busy}>Importér og installér</button></div>
    </form>
  {/if}

  <h3>Let's Encrypt</h3>
  <p class="small muted">
    Gratis certifikat, som alle browsere stoler på, og som fornyes automatisk (certbot, ca. hver 60. dag). Kræver et <strong>offentligt
    DNS-navn</strong> (fx scada.laces.dk). <strong>HTTP-01</strong>: navnet skal pege på anlæggets offentlige IP, og port 80 skal nå frem til
    Pi'en udefra. <strong>DNS-01 (deSEC)</strong>: virker uden åbne porte, men kræver en deSEC-konto og en CNAME-post
    <span class="mono">_acme-challenge.&lt;navn&gt;</span> → <span class="mono">&lt;navn i deSEC&gt;.&lt;zone&gt;</span>.
  </p>
  {#if leError}<div class="error">{leError}</div>{/if}
  {#if le?.info}
    {@const i = le.info}
    <ul class="small">
      <li>certbot: {i.certbot ? 'installeret' : 'ikke installeret'}{i.certbot ? ` · automatisk fornyelse: ${i.timer ? 'slået til' : 'SLÅET FRA'}` : ''}</li>
      <li>Let's Encrypt-certifikat på Pi'en: {i.lineage ? 'ja' : 'nej'}{i.last ? ` — seneste udstedelse ${fmtDate(i.last.ts)} til ${i.last.host} (${i.last.method === 'http' ? 'HTTP-01' : 'DNS-01'})` : ''}</li>
      <li>deSEC: {i.token ? 'token gemt' : 'intet token'}{i.zone ? ` · ${i.sub}.${i.zone}` : ''}</li>
    </ul>
    {#if !i.certbot}
      <button onclick={leInstall} disabled={leBusy(le)}>Installér certbot</button>
    {:else}
      <div class="row">
        <label class="check"><input type="radio" bind:group={leMethod} value="http" /> HTTP-01 (port 80)</label>
        <label class="check"><input type="radio" bind:group={leMethod} value="dns" /> DNS-01 (deSEC)</label>
      </div>
      {#if leMethod === 'dns'}
        <form class="grid" onsubmit={(e) => { e.preventDefault(); leDns(); }}>
          <label>deSEC-zone <input bind:value={leZone} placeholder="mitnavn.dedyn.io" required disabled={leBusy(le)} /></label>
          <label>Navn i zonen <input bind:value={leSub} placeholder="scada-acme" disabled={leBusy(le)} /></label>
          <label>deSEC-token {i.token ? '(gemt — udfyld kun for at skifte)' : ''}
            <input type="password" autocomplete="off" bind:value={leToken} disabled={leBusy(le)} />
          </label>
          <div><button disabled={leBusy(le)}>Gem deSEC-opsætning</button></div>
        </form>
      {/if}
      {@const blocked = leBusy(le) || !leHostOk(leHost) || !leEmail || (leMethod === 'dns' && !(i.token && i.zone))}
      <form class="grid" onsubmit={(e) => e.preventDefault()}>
        <label>Værtsnavn (offentligt DNS-navn) <input bind:value={leHost} placeholder="scada.laces.dk" disabled={leBusy(le)} />
          {#if leHost && !leHostOk(leHost)}<span class="small warn">Skal være et DNS-navn som scada.laces.dk — ikke en IP-adresse.</span>{/if}
        </label>
        <label>E-mail (Let's Encrypt advarer her, hvis fornyelsen svigter) <input type="email" bind:value={leEmail} disabled={leBusy(le)} /></label>
        <div class="row">
          <button type="button" onclick={() => leIssue(true)} disabled={blocked}>Test (staging)</button>
          <button type="button" class="primary" onclick={() => leIssue(false)} disabled={blocked}>Udsted og installér</button>
        </div>
        {#if leMethod === 'dns' && !(i.token && i.zone)}<span class="small muted">Gem først deSEC-zone og token.</span>{/if}
      </form>
    {/if}
  {:else if le}
    <p class="muted small">Henter overblik fra serveren … (kræver at hypervisionplc-scada-le.path er installeret)</p>
  {/if}
  {#if le?.status}
    {@const ls = le.status}
    <p class="small" class:bad={ls.state === 'error'}>
      {LE_ACTION[ls.action] ?? ls.action}: {ls.state === 'running' ? 'i gang …' : ls.state === 'ok' ? 'lykkedes' : 'mislykkedes'}
      {ls.message ? ` — ${ls.message}` : ''} <span class="muted">({fmtDate(ls.ts)})</span>
      {#if le.log.length}<button class="link" onclick={() => (showLog = !showLog)}>{showLog ? 'Skjul log' : 'Vis log'}</button>{/if}
    </p>
    {#if showLog && le.log.length}<pre class="mono small log">{le.log.join('\n')}</pre>{/if}
  {/if}
</section>

<style>
  .kv th { text-align: left; padding-right: 1rem; font-weight: 600; white-space: nowrap; vertical-align: top; }
  .row { display: flex; gap: 0.75rem; flex-wrap: wrap; align-items: center; margin: 0.5rem 0; }
  .bad { color: var(--danger, #c0392b); }
  .warn { color: var(--warn, #b7791f); }
  pre { white-space: pre-wrap; word-break: break-all; }
  pre.log { max-height: 16rem; overflow: auto; }
  button.link { background: none; border: none; padding: 0 0 0 0.5rem; text-decoration: underline; cursor: pointer; color: inherit; }
  form.grid { display: grid; gap: 0.6rem; max-width: 36rem; }
  form.grid label:not(.check), label.stack { display: flex; flex-direction: column; gap: 0.2rem; }
</style>
