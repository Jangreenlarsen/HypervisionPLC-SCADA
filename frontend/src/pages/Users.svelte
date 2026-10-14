<script lang="ts">
  import { onMount } from 'svelte';
  import { del, get, patch, post, ROLES, type Me, type Role } from '../lib/api';

  let { me }: { me: Me } = $props();

  interface User { username: string; role: Role; disabled: boolean; must_change_password: boolean; created_at: number; drawings: string[] | null }
  interface ScopeEdit { username: string; all: boolean; selected: string[] }

  const SCOPABLE: Role[] = ['viewer', 'operator', 'panel'];

  const ROLE_TEXT: Record<Role, string> = {
    viewer: 'Viewer — ser Overview og tags (kan begrænses til udvalgte tegninger)',
    operator: 'Operatør — + betjening af klik-handlinger i tegningerne',
    panel: 'Driftpanel — som operatør, men ser kun drifttegningen: ingen menu, kun "Log ud" (fx en skærm i produktionen)',
    engineer: 'Tekniker — + tegninger, tags og bindinger',
    admin: 'Admin — + PLC-forbindelser og brugere',
  };

  let users = $state<User[]>([]);
  let error = $state('');
  let info = $state('');
  let form = $state({ username: '', role: 'viewer' as Role, password: '', all: true, selected: [] as string[] });
  let drawings = $state<{ id: string; name: string }[]>([]);
  let scope = $state<ScopeEdit | null>(null);

  const drawingName = (id: string) => drawings.find((d) => d.id === id)?.name ?? id;
  const scopeText = (u: User) =>
    !SCOPABLE.includes(u.role) ? 'Alle (rollen ser altid alt)'
      : u.drawings === null ? 'Alle tegninger'
      : u.drawings.length === 0 ? 'Ingen tegninger'
      : u.drawings.map(drawingName).join(', ');

  function toggleIn(list: string[], id: string): string[] {
    return list.includes(id) ? list.filter((x) => x !== id) : [...list, id];
  }

  const saveScope = () => {
    if (!scope) return;
    const s = scope;
    run(async () => {
      await patch(`/api/users/${encodeURIComponent(s.username)}`, { drawings: s.all ? null : s.selected });
      scope = null;
    }, `Tegningsadgang for ${s.username} er gemt.`);
  };

  async function refresh(): Promise<void> {
    try {
      users = await get<User[]>('/api/users');
      drawings = await get<{ id: string; name: string }[]>('/api/drawings');
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
      const scoped = SCOPABLE.includes(form.role) && !form.all;
      await post('/api/users', { username: form.username, role: form.role, password: form.password,
        drawings: scoped ? form.selected : null });
      form = { username: '', role: 'viewer', password: '', all: true, selected: [] };
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
      <thead><tr><th>Bruger</th><th>Rolle</th><th>Tegninger</th><th>Status</th><th></th></tr></thead>
      <tbody>
        {#each users as u (u.username)}
          <tr>
            <td>{u.username}{u.username === me.username ? ' (dig)' : ''}</td>
            <td>
              <select value={u.role} onchange={(e) => setRole(u, (e.currentTarget as HTMLSelectElement).value as Role)}>
                {#each ROLES as r}<option value={r}>{r}</option>{/each}
              </select>
            </td>
            <td class="small">
              {scopeText(u)}
              {#if SCOPABLE.includes(u.role)}
                <button class="small" onclick={() => (scope = { username: u.username, all: u.drawings === null, selected: [...(u.drawings ?? [])] })}>Vælg …</button>
              {/if}
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

{#if scope}
  <section class="panel">
    <h2>Tegningsadgang for {scope.username}</h2>
    <p class="muted small">Brugeren ser kun de valgte tegninger på Overview, kun de tags der vises i dem, og kan kun betjene klik-handlinger i dem.</p>
    <label class="row"><input type="radio" checked={scope.all} onchange={() => scope && (scope.all = true)} /> Alle tegninger</label>
    <label class="row"><input type="radio" checked={!scope.all} onchange={() => scope && (scope.all = false)} /> Kun valgte tegninger:</label>
    <div class="choices">
      {#each drawings as d}
        <label class="row"><input type="checkbox" disabled={scope.all} checked={scope.selected.includes(d.id)}
          onchange={() => scope && (scope.selected = toggleIn(scope.selected, d.id))} /> {d.name}</label>
      {/each}
    </div>
    {#if !scope.all && scope.selected.length === 0}<p class="small notice">Ingen tegninger valgt — brugeren vil ikke kunne se noget.</p>{/if}
    <div class="row" style="margin-top: .6rem">
      <button class="primary" onclick={saveScope}>Gem</button>
      <button onclick={() => (scope = null)}>Annullér</button>
    </div>
  </section>
{/if}

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
  {#if SCOPABLE.includes(form.role)}
    <div style="margin-top: .6rem">
      <label class="row"><input type="radio" checked={form.all} onchange={() => (form.all = true)} /> Adgang til alle tegninger</label>
      <label class="row"><input type="radio" checked={!form.all} onchange={() => (form.all = false)} /> Kun valgte tegninger:</label>
      <div class="choices">
        {#each drawings as d}
          <label class="row"><input type="checkbox" disabled={form.all} checked={form.selected.includes(d.id)}
            onchange={() => (form.selected = toggleIn(form.selected, d.id))} /> {d.name}</label>
        {/each}
      </div>
    </div>
  {/if}
  <ul class="muted small">
    {#each ROLES as r}<li>{ROLE_TEXT[r]}</li>{/each}
  </ul>
</section>

<style>
  .choices { display: flex; flex-wrap: wrap; gap: .25rem 1.2rem; padding-left: 1.6rem; }
</style>
