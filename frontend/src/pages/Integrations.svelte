<script lang="ts">
  import { onMount } from 'svelte';
  import { del, get, patch, post } from '../lib/api';
  import { ask } from '../lib/ask';
  import {
    createBody, emptyForm, examples, formFrom, generateKey, keyStatus, patchBody, scopeText,
    type ApiKey, type KeyForm,
  } from '../lib/integration';

  let keys = $state<ApiKey[] | null>(null);
  let form = $state<KeyForm>(emptyForm());
  let editing = $state<string | null>(null);      // id på den nøgle, der redigeres (null = opret ny)
  let fresh = $state<{ key: string; name: string } | null>(null);   // den netop oprettede nøgle — vises kun her
  let busy = $state(false);
  let error = $state('');

  const base = location.origin;
  const sample = $derived(fresh ? examples(base, fresh.key) : null);

  async function load(): Promise<void> {
    try {
      keys = await get<ApiKey[]>('/api/system/integration/keys');
      error = '';
    } catch (e) {
      error = (e as Error).message;
    }
  }
  onMount(load);

  function reset(): void {
    form = emptyForm();
    editing = null;
  }

  async function save(): Promise<void> {
    busy = true; error = '';
    try {
      if (editing) {
        const original = keys?.find((k) => k.id === editing);
        const changes = original ? patchBody(form, original) : {};
        if (Object.keys(changes).length) await patch(`/api/system/integration/keys/${editing}`, changes);
        reset();
      } else {
        const key = generateKey();                  // genereres her; serveren gemmer kun en kontrolsum og kan ikke give den tilbage
        await post('/api/system/integration/keys', createBody(form, key));
        fresh = { key, name: form.name.trim() };
        reset();
      }
      await load();
    } catch (e) {
      error = (e as Error).message;               // backendens præcise fejl (fx "Ukendte tags: …")
    } finally {
      busy = false;
    }
  }

  function edit(k: ApiKey): void {
    form = formFrom(k);
    editing = k.id;
    fresh = null;
    error = '';
  }

  async function toggle(k: ApiKey): Promise<void> {
    busy = true; error = '';
    try {
      await patch(`/api/system/integration/keys/${k.id}`, { disabled: !k.disabled });
      await load();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  async function revoke(k: ApiKey): Promise<void> {
    if (!(await ask(`Tilbagekald nøglen "${k.name}"? Systemer, der bruger den, mister adgangen med det samme, og det kan ikke fortrydes.`, { ok: 'Tilbagekald', danger: true }))) return;
    busy = true; error = '';
    try {
      await del(`/api/system/integration/keys/${k.id}`);
      if (editing === k.id) reset();
      await load();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  const when = (ts: number | null) => (ts === null ? '—' : new Date(ts * 1000).toLocaleString('da-DK'));
</script>

<section class="panel">
  <h2>Integrationer</h2>
  <p class="muted small">
    API-nøgler til Node-RED, Home Assistant og andre systemer, der skal <strong>læse</strong> værdier, historik og alarmer. En nøgle kan kun bruge
    integrations-API'et (<span class="mono">/api/v1/integration/…</span>), aldrig resten af SCADA, og er afgrænset til de tags, du vælger. Nøglen vises
    <strong>kun én gang</strong>, og serveren gemmer kun en kontrolsum. Beskrivelse af grænsefladen (OpenAPI):
    <a href="/api/v1/integration/openapi.json" target="_blank" rel="noopener">openapi.json</a>. Styring (skrivning) er ikke slået til.
  </p>
  {#if error}<div class="error">{error}</div>{/if}

  {#if fresh && sample}
    <div class="notice warn">
      <strong>Kopiér nøglen til "{fresh.name}" nu — den kan ikke vises igen.</strong>
      <input class="mono" readonly value={fresh.key} aria-label="Ny API-nøgle" onclick={(e) => e.currentTarget.select()} />
      <p class="small muted">Eksempler (adressen er den, du bruger nu — brug den adresse, som det andet system kan nå):</p>
      <p class="small"><strong>curl</strong></p><pre class="mono small">{sample.curl}</pre>
      <p class="small"><strong>Node-RED</strong></p><pre class="mono small">{sample.nodered}</pre>
      <p class="small"><strong>Home Assistant</strong></p><pre class="mono small">{sample.homeassistant}</pre>
      <button onclick={() => (fresh = null)}>Jeg har kopieret den</button>
    </div>
  {/if}

  <h3>{editing ? 'Redigér nøgle' : 'Ny nøgle'}</h3>
  <form class="grid" onsubmit={(e) => { e.preventDefault(); save(); }}>
    <label>Navn (hvem bruger den?) <input bind:value={form.name} placeholder="Node-RED" disabled={busy} /></label>
    <fieldset class="scope">
      <legend>Hvad må nøglen se?</legend>
      <label class="check"><input type="radio" bind:group={form.scopeMode} value="selected" disabled={busy} /> Valgte tags / præfikser</label>
      <label class="check"><input type="radio" bind:group={form.scopeMode} value="all" disabled={busy} /> Alle tags</label>
    </fieldset>
    {#if form.scopeMode === 'selected'}
      <label>Tags (ét pr. linje eller adskilt af komma)
        <textarea rows="3" bind:value={form.tags} placeholder="kedel_temp" disabled={busy}></textarea>
      </label>
      <label>Præfikser (alle tags, der starter med …)
        <textarea rows="2" bind:value={form.prefixes} placeholder="kedel_" disabled={busy}></textarea>
      </label>
    {/if}
    <label>Kun fra disse IP-adresser/netværk (valgfrit)
      <textarea rows="2" bind:value={form.ips} placeholder="10.1.1.0/24" disabled={busy}></textarea>
    </label>
    <label>Udløber (valgfrit) <input type="date" bind:value={form.expires} disabled={busy} /></label>
    <div class="row">
      <button class="primary" type="submit" disabled={busy}>{editing ? 'Gem ændringer' : 'Opret nøgle'}</button>
      {#if editing}<button type="button" onclick={reset} disabled={busy}>Annullér</button>{/if}
    </div>
    {#if editing}<p class="muted small">Selve nøglen kan ikke ændres. Mistet nøgle: tilbagekald den og opret en ny.</p>{/if}
  </form>

  <h3>Nøgler</h3>
  {#if keys}
    <div class="table-wrap">
      <table>
        <thead><tr><th>Navn</th><th>Afgrænsning</th><th>Status</th><th>Sidst brugt</th><th>Kald</th><th></th></tr></thead>
        <tbody>
          {#each keys as k (k.id)}
            <tr>
              <td>{k.name}<div class="muted small mono">{k.prefix}…</div></td>
              <td class="small">{scopeText(k.scope)}{#if k.ip_allow.length}<div class="muted">kun fra {k.ip_allow.join(', ')}</div>{/if}
                {#if k.expires_at !== null}<div class="muted">udløber {when(k.expires_at)}</div>{/if}</td>
              <td><span class="badge {keyStatus(k) === 'aktiv' ? 'ok' : 'off'}">{keyStatus(k)}</span></td>
              <td class="small">{when(k.last_used_at)}{#if k.last_ip}<div class="muted">{k.last_ip}</div>{/if}</td>
              <td class="small">{k.stats.requests}{#if k.stats.rate_limited} <span class="muted">· {k.stats.rate_limited} afvist</span>{/if}{#if k.stats.errors} <span class="muted">· {k.stats.errors} fejl</span>{/if}</td>
              <td class="nowrap">
                <button onclick={() => edit(k)} disabled={busy}>Redigér</button>
                <button onclick={() => toggle(k)} disabled={busy}>{k.disabled ? 'Aktivér' : 'Deaktivér'}</button>
                <button onclick={() => revoke(k)} disabled={busy}>Tilbagekald</button>
              </td>
            </tr>
          {:else}
            <tr><td colspan="6" class="muted">Ingen nøgler endnu.</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else if !error}
    <p class="muted">Henter …</p>
  {/if}
</section>

<style>
  .grid { display: grid; gap: 0.5rem; max-width: 34rem; }
  .grid label { display: grid; gap: 0.2rem; }
  .grid label.check { display: flex; gap: 0.4rem; align-items: center; }
  fieldset.scope { border: 1px solid var(--line); border-radius: var(--radius); padding: 0.4rem 0.6rem; }
  h3 { margin: 1rem 0 0.2rem; font-size: 1rem; }
  textarea { font: inherit; }
  .notice input { width: 100%; box-sizing: border-box; margin: 0.4rem 0; }
  pre { background: var(--panel); border: 1px solid var(--line); padding: 0.5rem; overflow-x: auto; margin: 0.2rem 0 0.6rem; white-space: pre-wrap; }
  .nowrap { white-space: nowrap; }
</style>
