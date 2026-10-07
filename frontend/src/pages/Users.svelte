<script lang="ts">
  import { onMount } from 'svelte';
  import { del, get, patch, post, ROLES, type Me, type Role } from '../lib/api';

  let { me }: { me: Me } = $props();

  interface User { username: string; role: Role; disabled: boolean; must_change_password: boolean; created_at: number }

  const ROLE_TEXT: Record<Role, string> = {
    viewer: 'Viewer — ser Overview og tags',
    operator: 'Operatør — + betjening (skriv til PLC, kommer senere)',
    engineer: 'Tekniker — + tegninger, tags og bindinger',
    admin: 'Admin — + PLC-forbindelser og brugere',
  };

  let users = $state<User[]>([]);
  let error = $state('');
  let info = $state('');
  let form = $state({ username: '', role: 'viewer' as Role, password: '' });

  async function refresh(): Promise<void> {
    try {
      users = await get<User[]>('/api/users');
    } catch (e) {
      error = (e as Error).message;
    }
  }

  async function run(fn: () => Promise<unknown>, done: string): Promise<void> {
    error = info = '';
    try {
      await fn();
      info = done;
      await refresh();
    } catch (e) {
      error = (e as Error).message;
      await refresh(); // vis den reelle tilstand igen (fx rolle-feltet efter en afvist ændring)
    }
  }

  const create = () =>
    run(async () => {
      await post('/api/users', form);
      form = { username: '', role: 'viewer', password: '' };
    }, 'Brugeren er oprettet og skal skifte adgangskode ved første login.');

  const setRole = (u: User, role: Role) => run(() => patch(`/api/users/${encodeURIComponent(u.username)}`, { role }), `${u.username} er nu ${role}.`);
  const toggle = (u: User) =>
    run(() => patch(`/api/users/${encodeURIComponent(u.username)}`, { disabled: !u.disabled }),
      `${u.username} er ${u.disabled ? 'aktiveret' : 'deaktiveret'}.`);

  function reset(u: User): void {
    const pw = prompt(`Ny midlertidig adgangskode til ${u.username} (mindst 10 tegn):`);
    if (pw) run(() => patch(`/api/users/${encodeURIComponent(u.username)}`, { password: pw }), `${u.username} skal skifte adgangskode ved næste login.`);
  }

  function remove(u: User): void {
    if (confirm(`Slet brugeren ${u.username}?`)) run(() => del(`/api/users/${encodeURIComponent(u.username)}`), `${u.username} er slettet.`);
  }

  onMount(refresh);
</script>

{#if error}<div class="error">{error}</div>{/if}
{#if info}<div class="notice">{info}</div>{/if}

<section class="panel">
  <h2>Brugere</h2>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Bruger</th><th>Rolle</th><th>Status</th><th></th></tr></thead>
      <tbody>
        {#each users as u (u.username)}
          <tr>
            <td>{u.username}{u.username === me.username ? ' (dig)' : ''}</td>
            <td>
              <select value={u.role} onchange={(e) => setRole(u, (e.currentTarget as HTMLSelectElement).value as Role)}>
                {#each ROLES as r}<option value={r}>{r}</option>{/each}
              </select>
            </td>
            <td>
              <span class="badge {u.disabled ? 'error' : 'ok'}">{u.disabled ? 'deaktiveret' : 'aktiv'}</span>
              {#if u.must_change_password}<span class="badge">skal skifte adgangskode</span>{/if}
            </td>
            <td>
              <div class="row">
                <button onclick={() => toggle(u)}>{u.disabled ? 'Aktivér' : 'Deaktivér'}</button>
                <button onclick={() => reset(u)}>Ny adgangskode</button>
                <button class="danger" onclick={() => remove(u)}>Slet</button>
              </div>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  <p class="muted small">Systemet tillader ikke at den sidste aktive administrator slettes, nedgraderes eller deaktiveres.</p>
</section>

<section class="panel">
  <h2>Ny bruger</h2>
  <div class="grid-form">
    <label>Brugernavn<input bind:value={form.username} autocomplete="off" autocapitalize="off" /></label>
    <label>Rolle
      <select bind:value={form.role}>{#each ROLES as r}<option value={r}>{r}</option>{/each}</select>
    </label>
    <label>Midlertidig adgangskode<input type="password" bind:value={form.password} autocomplete="new-password" /></label>
    <div><button class="primary" onclick={create} disabled={!form.username || !form.password}>Opret</button></div>
  </div>
  <ul class="muted small">
    {#each ROLES as r}<li>{ROLE_TEXT[r]}</li>{/each}
  </ul>
</section>
