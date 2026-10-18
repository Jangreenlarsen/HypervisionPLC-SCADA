<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { ask as askUser } from '../lib/ask';
  import { del, get, patch, post } from '../lib/api';

  let { isAdmin = false }: { isAdmin?: boolean } = $props();

  interface Status {
    state: string; message: string; last_ok: number | null; cycles?: number; errors?: number;
    requests_per_cycle?: number; plan?: { kind: string; start: number; count: number }[];
    sse?: { state: string; message?: string; events?: number; covered?: number; external?: boolean; ext_events?: number };
  }
  interface Plc {
    key: string; name: string; base_url: string; username: string; enabled: boolean;
    sse_enabled: boolean; verify_tls: boolean; has_password: boolean; tag_count: number; status: Status;
  }

  let plcs = $state<Plc[]>([]);
  let error = $state('');
  let form = $state({ key: '', name: '', base_url: 'http://', username: '', password: '', sse_enabled: true });
  let pw = $state<Record<string, string>>({});
  let timer: ReturnType<typeof setInterval>;

  async function refresh(): Promise<void> {
    try {
      plcs = await get<Plc[]>('/api/plcs');
    } catch (e) {
      error = (e as Error).message;
    }
  }

  async function create(): Promise<void> {
    error = '';
    try {
      await post('/api/plcs', { ...form, name: form.name || form.key, password: form.password || undefined });
      form = { key: '', name: '', base_url: 'http://', username: '', password: '', sse_enabled: true };
      await refresh();
    } catch (e) {
      error = (e as Error).message;
    }
  }

  async function update(p: Plc, body: Record<string, unknown>): Promise<void> {
    error = '';
    try {
      await patch(`/api/plcs/${encodeURIComponent(p.key)}`, body);
      pw[p.key] = '';
      await refresh();
    } catch (e) {
      error = (e as Error).message;
    }
  }

  async function remove(p: Plc): Promise<void> {
    if (!await askUser(`Fjern PLC'en ${p.name}?`)) return;
    try {
      await del(`/api/plcs/${encodeURIComponent(p.key)}`);
      await refresh();
    } catch (e) {
      error = (e as Error).message;
    }
  }

  const ago = (ts: number | null) => (ts ? `${Math.max(0, Math.round(Date.now() / 1000 - ts))} s siden` : 'aldrig');

  onMount(() => {
    refresh();
    timer = setInterval(refresh, 3000);
  });
  onDestroy(() => clearInterval(timer));
</script>

{#if error}<div class="error">{error}</div>{/if}

{#each plcs as p (p.key)}
  <section class="panel">
    <div class="row" style="justify-content: space-between">
      <h2>{p.name} <span class="muted small mono">{p.key}</span></h2>
      <span class="badge {p.status.state}">{p.status.state}</span>
    </div>
    {#if p.status.message}<div class={p.status.state === 'error' ? 'error' : 'notice'}>{p.status.message}</div>{/if}
    <div class="table-wrap">
      <table>
        <tbody>
          <tr><th>Adresse</th><td class="mono">{p.base_url}</td></tr>
          <tr><th>Bruger</th><td>{p.username} {p.has_password ? '' : '— ingen adgangskode sat'}</td></tr>
          <tr><th>Tags</th><td>{p.tag_count}</td></tr>
          <tr><th>Seneste OK</th><td>{ago(p.status.last_ok)} · {p.status.cycles ?? 0} cyklusser · {p.status.errors ?? 0} fejl</td></tr>
          <tr><th>Kald pr. cyklus</th><td>{p.status.requests_per_cycle ?? 0}
            {#if p.status.plan?.length}<span class="muted small">({p.status.plan.map((r) => `${r.kind} ${r.start}+${r.count}`).join(', ')})</span>{/if}</td></tr>
          <tr><th>SSE</th><td>
            <span class="badge {p.status.sse?.state}">{p.status.sse?.state ?? '-'}</span>
            <span class="small muted">{p.status.sse?.message ?? ''}{p.status.sse?.covered !== undefined ? ` · dækker ${p.status.sse.covered} adresser` : ''}{p.status.sse?.events ? ` · ${p.status.sse.events} hændelser` : ''}{p.status.sse?.external ? ` · eksterne registre via SSE (${p.status.sse.ext_events ?? 0})` : ''}</span>
          </td></tr>
        </tbody>
      </table>
    </div>
    {#if isAdmin}
    <div class="row" style="margin-top: .6rem">
      <button onclick={() => update(p, { enabled: !p.enabled })}>{p.enabled ? 'Deaktivér' : 'Aktivér'}</button>
      <button onclick={() => update(p, { sse_enabled: !p.sse_enabled })}>{p.sse_enabled ? 'Slå SSE fra' : 'Slå SSE til'}</button>
      <input type="password" placeholder="Ny adgangskode" bind:value={pw[p.key]} autocomplete="new-password" />
      <button disabled={!pw[p.key]} onclick={() => update(p, { password: pw[p.key] })}>Gem adgangskode</button>
      <button class="danger" onclick={() => remove(p)}>Fjern</button>
    </div>
    {/if}
  </section>
{/each}

{#if isAdmin}
<section class="panel">
  <h2>Tilføj PLC</h2>
  <p class="muted small">Brug en dedikeret bruger på PLC'en med rollen <code>api</code>. Adgangskoden gemmes kun på SCADA-serveren og vises aldrig igen.</p>
  <div class="grid-form">
    <label>Nøgle<input bind:value={form.key} placeholder="plc1" /></label>
    <label>Navn<input bind:value={form.name} /></label>
    <label>Adresse<input bind:value={form.base_url} placeholder="http://10.1.1.30" /></label>
    <label>Bruger<input bind:value={form.username} autocomplete="off" /></label>
    <label>Adgangskode<input type="password" bind:value={form.password} autocomplete="new-password" /></label>
    <label class="row" style="flex-direction: row"><input type="checkbox" bind:checked={form.sse_enabled} /> Brug SSE</label>
    <div><button class="primary" onclick={create} disabled={!form.key || !form.username}>Tilføj</button></div>
  </div>
</section>
{/if}
