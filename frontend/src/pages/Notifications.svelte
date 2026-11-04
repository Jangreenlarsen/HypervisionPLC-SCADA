<script lang="ts">
  import { onMount } from 'svelte';
  import { get, post, put } from '../lib/api';
  import {
    CHANNEL_TEXT, PRIORITY_TEXT, PROVIDER_TEXT, SECURITY_TEXT, buildBody, formFrom,
    type Form, type NotifyState, type Priority, type Security, type TestResults,
  } from '../lib/notifications';

  let info = $state<NotifyState | null>(null);
  let form = $state<Form | null>(null);
  let busy = $state(false);
  let error = $state('');
  let saved = $state('');
  let testResult = $state<TestResults['results'] | null>(null);

  function apply(s: NotifyState): void {
    info = s;
    form = formFrom(s.config);
  }

  async function load(): Promise<void> {
    try {
      apply(await get<NotifyState>('/api/system/notifications'));
      error = '';
    } catch (e) {
      error = (e as Error).message;
    }
  }
  onMount(load);

  async function save(): Promise<void> {
    if (!form) return;
    busy = true; error = ''; saved = ''; testResult = null;
    try {
      apply(await put<NotifyState>('/api/system/notifications', buildBody(form)));
      saved = 'Gemt';
    } catch (e) {
      error = (e as Error).message;    // backendens præcise fejl (fx "Webhook kan ikke slås til uden en adresse")
    } finally {
      busy = false;
    }
  }

  async function test(): Promise<void> {
    busy = true; error = ''; saved = ''; testResult = null;
    try {
      const r = await post<NotifyState & TestResults>('/api/system/notifications/test', {});
      testResult = r.results;
      info = r;      // kun status og afsendelser — det, der er tastet i formularen uden at være gemt, bevares
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  const when = (ts: number) => new Date(ts * 1000).toLocaleString('da-DK');
  const failing = $derived(info ? Object.entries(info.failing) : []);
  // formularen er ændret siden den gemte opsætning (eller en hemmelighed er tastet) — en prøvebesked bruger den GEMTE opsætning
  const dirty = $derived(!!form && !!info && JSON.stringify(buildBody(form)) !== JSON.stringify(buildBody(formFrom(info.config))));
</script>

<section class="panel">
  <h2>Notifikationer</h2>
  <p class="muted small">
    Få besked, når en alarm rejses eller ophører — som webhook (til Node-RED, Home Assistant, ntfy, Slack/Teams …) og/eller e-mail.
    Adresser, token og adgangskode er skriv-kun: de gemmes kun på serveren og vises aldrig igen. Flere alarmer inden for samletiden sendes som <em>én</em> besked.
  </p>
  {#if error}<div class="error">{error}</div>{/if}
  {#each failing as [channel, message]}
    <div class="error">{CHANNEL_TEXT[channel] ?? channel} kan ikke sendes: {message}</div>
  {/each}

  {#if form && info}
    <form class="grid" onsubmit={(e) => { e.preventDefault(); save(); }}>
      <label class="check"><input type="checkbox" bind:checked={form.enabled} disabled={busy} /> <strong>Send notifikationer</strong></label>
      <label>Hvilke alarmer
        <select bind:value={form.min_priority} disabled={busy}>
          {#each Object.entries(PRIORITY_TEXT) as [value, text]}<option {value}>{text}</option>{/each}
        </select>
      </label>
      <label class="check"><input type="checkbox" bind:checked={form.on_clear} disabled={busy} /> Send også når alarmen ophører</label>
      <label>Samletid (sekunder, 5–300)
        <input type="number" min="5" max="300" bind:value={form.batch_s} disabled={busy} />
      </label>

      <h3>Webhook</h3>
      <label class="check"><input type="checkbox" bind:checked={form.wh_enabled} disabled={busy} /> Slå webhook til</label>
      <label>Adresse {#if info.config.webhook.has_url}<span class="badge ok">sat · {info.config.webhook.host}</span>{:else}<span class="badge off">ikke sat</span>{/if}
        <input type="url" placeholder={info.config.webhook.has_url ? 'Skriv en ny adresse for at ændre den' : 'https://…'} bind:value={form.wh_url} disabled={busy} autocomplete="off" />
      </label>
      {#if info.config.webhook.has_url}<label class="check"><input type="checkbox" bind:checked={form.clear_url} disabled={busy} /> Fjern adressen</label>{/if}
      <label>Bearer-token (valgfrit) {#if info.config.webhook.has_token}<span class="badge ok">sat</span>{/if}
        <input type="password" placeholder={info.config.webhook.has_token ? 'Skriv et nyt token for at ændre det' : ''} bind:value={form.wh_token} disabled={busy} autocomplete="off" />
      </label>
      {#if info.config.webhook.has_token}<label class="check"><input type="checkbox" bind:checked={form.clear_token} disabled={busy} /> Fjern tokenet</label>{/if}

      <h3>E-mail</h3>
      <label class="check"><input type="checkbox" bind:checked={form.em_enabled} disabled={busy} /> Slå e-mail til</label>
      <label>Udbyder
        <select bind:value={form.em_provider} disabled={busy}>
          {#each Object.entries(PROVIDER_TEXT) as [value, text]}<option {value}>{text}</option>{/each}
        </select>
      </label>
      {#if form.em_provider === 'resend'}
        <label>Resend API-nøgle {#if info.config.email.has_resend_key}<span class="badge ok">sat</span>{:else}<span class="badge off">ikke sat</span>{/if}
          <input type="password" placeholder={info.config.email.has_resend_key ? 'Skriv en ny nøgle for at ændre den' : 're_…'} bind:value={form.em_resend_key} disabled={busy} autocomplete="off" />
        </label>
        {#if info.config.email.has_resend_key}<label class="check"><input type="checkbox" bind:checked={form.clear_resend_key} disabled={busy} /> Fjern nøglen</label>{/if}
        <p class="muted small">Resend sender via deres HTTPS-API (<span class="mono">api.resend.com</span>). Afsenderen skal være en adresse på et domæne, du har verificeret hos Resend.</p>
      {:else}
        <label>SMTP-server <input bind:value={form.em_host} placeholder="smtp.laces.dk" disabled={busy} /></label>
        <label>Port <input type="number" min="1" max="65535" bind:value={form.em_port} disabled={busy} /></label>
        <label>Sikkerhed
          <select bind:value={form.em_security} disabled={busy}>
            {#each Object.entries(SECURITY_TEXT) as [value, text]}<option {value}>{text}</option>{/each}
          </select>
        </label>
        <label>Brugernavn (valgfrit) <input bind:value={form.em_username} disabled={busy} autocomplete="off" /></label>
        <label>Adgangskode {#if info.config.email.has_password}<span class="badge ok">sat</span>{/if}
          <input type="password" placeholder={info.config.email.has_password ? 'Skriv en ny adgangskode for at ændre den' : ''} bind:value={form.em_password} disabled={busy} autocomplete="new-password" />
        </label>
        {#if info.config.email.has_password}<label class="check"><input type="checkbox" bind:checked={form.clear_password} disabled={busy} /> Fjern adgangskoden</label>{/if}
      {/if}
      <label>Afsender <input type="email" bind:value={form.em_sender} placeholder="scada@laces.dk" disabled={busy} /></label>
      <label>Modtagere (én pr. linje eller adskilt af komma)
        <textarea rows="3" bind:value={form.em_recipients} placeholder="jan@laces.dk" disabled={busy}></textarea>
      </label>

      <div class="row">
        <button class="primary" type="submit" disabled={busy}>Gem</button>
        <button type="button" onclick={test} disabled={busy || dirty} title={dirty ? 'Gem først — prøvebeskeden bruger den gemte opsætning' : ''}>Send prøvebesked</button>
        {#if dirty}<span class="muted small">Ændringer er ikke gemt</span>{/if}
        {#if saved}<span class="muted small">{saved}</span>{/if}
      </div>
      <p class="muted small">Prøvebeskeden sendes med den <strong>gemte</strong> opsætning til de kanaler, der er slået til — tryk Gem først, hvis du har ændret noget.</p>
    </form>

    {#if testResult}
      <div class="notice">
        {#each Object.entries(testResult) as [channel, r]}
          <div><strong>{CHANNEL_TEXT[channel] ?? channel}:</strong> {r.ok ? 'sendt' : `fejlede — ${r.error}`}</div>
        {/each}
      </div>
    {/if}

    <h3>Status</h3>
    <p class="small muted">
      Sendt siden start: {Object.entries(info.sent).map(([c, n]) => `${CHANNEL_TEXT[c] ?? c} ${n}`).join(' · ')} ·
      mislykkede: {Object.entries(info.failed).map(([c, n]) => `${CHANNEL_TEXT[c] ?? c} ${n}`).join(' · ')} · venter: {info.queued}
      {#if info.dropped}· kasseret (kø fuld): {info.dropped}{/if}
    </p>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Tid</th><th>Kanal</th><th>Resultat</th><th>Alarmer</th><th>Forsøg</th></tr></thead>
        <tbody>
          {#each info.deliveries as d}
            <tr>
              <td class="small">{when(d.ts)}{#if d.test} <span class="badge off">prøve</span>{/if}</td>
              <td>{CHANNEL_TEXT[d.channel] ?? d.channel}</td>
              <td>{#if d.ok}<span class="badge ok">sendt</span>{:else}<span class="badge error">fejlede</span> <span class="small">{d.error}</span>{/if}</td>
              <td>{d.alarms}</td><td>{d.attempts}</td>
            </tr>
          {:else}
            <tr><td colspan="5" class="muted">Intet er sendt endnu.</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else if !error}
    <p class="muted">Henter …</p>
  {/if}
</section>

<style>
  .grid { display: grid; gap: 0.5rem; max-width: 36rem; }
  .grid label { display: grid; gap: 0.2rem; }
  .grid label.check { display: flex; gap: 0.4rem; align-items: center; }
  h3 { margin: 1rem 0 0.2rem; font-size: 1rem; }
  textarea { font: inherit; }
</style>
