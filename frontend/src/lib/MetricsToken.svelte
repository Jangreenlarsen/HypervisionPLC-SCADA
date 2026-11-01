<script lang="ts">
  import { onMount } from 'svelte';
  import { ApiError, del, get, put } from './api';
  import { ask } from './ask';
  import { generateToken, scrapeConfig } from './metricsToken';

  // Kun admin: sæt/fjern scrape-tokenet til /metrics (Prometheus). Andre roller får 403, og boksen vises slet ikke.
  let info = $state<{ enabled: boolean; min_length: number; auth_failures: number } | null>(null);
  let visible = $state(true);
  let busy = $state(false);
  let error = $state('');
  let fresh = $state('');   // det netop oprettede token — vises kun her, serveren kan ikke give det igen

  async function load(): Promise<void> {
    try {
      info = await get('/api/system/metrics');
    } catch (e) {
      if (e instanceof ApiError && (e.status === 403 || e.status === 401)) visible = false;
      else error = (e as Error).message;
    }
  }
  onMount(load);

  async function create(): Promise<void> {
    if (info?.enabled && !(await ask('Der findes allerede et token. Et nyt token afløser det — Prometheus skal have det nye, ellers afvises den.', { ok: 'Opret nyt token', danger: true }))) return;
    busy = true; error = '';
    try {
      const token = generateToken();
      await put('/api/system/metrics', { token });
      fresh = token;
      await load();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  async function disable(): Promise<void> {
    if (!(await ask('Slå /metrics fra? Prometheus kan så ikke længere hente tal.', { ok: 'Slå fra', danger: true }))) return;
    busy = true; error = '';
    try {
      await del('/api/system/metrics');
      fresh = '';
      await load();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  const config = $derived(fresh ? scrapeConfig(location.host, fresh) : '');
</script>

{#if visible}
  <h3>Prometheus (<span class="mono">/metrics</span>)</h3>
  <div class="card">
    {#if error}<div class="error">{error}</div>{/if}
    {#if info}
      <p class="small">
        {#if info.enabled}<span class="badge ok">slået til</span>{:else}<span class="badge off">slået fra</span>{/if}
        Tal om serveren og PLC'erne (kun systemtal — ingen tag-værdier, navne eller hemmeligheder) til Prometheus/Grafana.
        Hentes med <span class="mono">Authorization: Bearer &lt;token&gt;</span>; en almindelig login-session giver ikke adgang.
        {#if info.auth_failures}<span class="muted">· {info.auth_failures} afviste forsøg siden start</span>{/if}
      </p>
      <div class="row">
        <button onclick={create} disabled={busy}>{info.enabled ? 'Opret nyt token' : 'Slå til (opret token)'}</button>
        {#if info.enabled}<button onclick={disable} disabled={busy}>Slå fra</button>{/if}
      </div>
    {/if}
    {#if fresh}
      <div class="fresh">
        <p class="small"><strong>Kopiér tokenet nu — det kan ikke vises igen.</strong> Serveren gemmer kun en kontrolsum.</p>
        <input class="mono" readonly value={fresh} aria-label="Nyt scrape-token" onclick={(e) => e.currentTarget.select()} />
        <p class="small muted">Eksempel til <span class="mono">prometheus.yml</span>:</p>
        <pre class="mono small">{config}</pre>
        <button onclick={() => (fresh = '')}>Jeg har kopieret det</button>
      </div>
    {/if}
  </div>
{/if}

<style>
  h3 { margin: 1.1rem 0 0.4rem; font-size: 1rem; }
  .card { border: 1px solid var(--line); background: var(--panel-2); border-radius: var(--radius); padding: 0.6rem 0.8rem; }
  .fresh { margin-top: 0.7rem; border-top: 1px solid var(--line); padding-top: 0.6rem; }
  .fresh input { width: 100%; box-sizing: border-box; }
  pre { background: var(--panel); border: 1px solid var(--line); padding: 0.5rem; overflow-x: auto; margin: 0.3rem 0 0.6rem; }
</style>
