<script lang="ts">
  import { onMount } from 'svelte';
  import { ApiError, get, onUnauthorized, post, roleAtLeast, type Me, type Role } from './lib/api';
  import Overview from './pages/Overview.svelte';
  import Drawings from './pages/Drawings.svelte';
  import Tags from './pages/Tags.svelte';
  import Plcs from './pages/Plcs.svelte';
  import Users from './pages/Users.svelte';
  import Editor from './pages/Editor.svelte';
  import Audit from './pages/Audit.svelte';
  import Login from './pages/Login.svelte';
  import ChangePassword from './pages/ChangePassword.svelte';

  const pages: { id: string; label: string; role: Role }[] = [
    { id: 'overview', label: 'Overview', role: 'viewer' },
    { id: 'drawings', label: 'Tegninger', role: 'viewer' },
    { id: 'editor', label: 'Bindinger', role: 'engineer' },
    { id: 'tags', label: 'Tags', role: 'viewer' },
    { id: 'plcs', label: "PLC'er", role: 'engineer' },
    { id: 'audit', label: 'Log', role: 'engineer' },
    { id: 'users', label: 'Brugere', role: 'admin' },
  ];

  let route = $state(location.hash.slice(1) || 'overview');
  let info = $state<{ version: string; build: string; source_url: string } | null>(null);
  let me = $state<Me | null>(null);
  let checked = $state(false);
  let changingPassword = $state(false);
  let error = $state('');

  async function loadMe(): Promise<void> {
    try {
      me = await get<Me>('/api/auth/me');
      error = '';
    } catch (e) {
      me = null;
      if (!(e instanceof ApiError && e.status === 401)) error = (e as Error).message;
    } finally {
      checked = true;
    }
  }

  async function logout(): Promise<void> {
    try {
      await post('/api/auth/logout', {});
    } catch (e) {
      console.error('Logout fejlede:', e); // sessionen ryddes alligevel lokalt nedenfor
    }
    me = null;
  }

  onMount(() => {
    const onHash = () => (route = location.hash.slice(1) || 'overview');
    window.addEventListener('hashchange', onHash);
    onUnauthorized(() => (me = null));
    loadMe();
    get<{ version: string; build: string; source_url: string }>('/api/health')
      .then((h) => (info = h))
      .catch((e) => console.error('Kunne ikke hente version:', e));
    return () => window.removeEventListener('hashchange', onHash);
  });

  const visible = $derived(pages.filter((p) => roleAtLeast(me?.role, p.role)));
  const page = $derived(visible.some((p) => p.id === route.split('/')[0]) ? route.split('/')[0] : 'overview');
  const canEdit = $derived(roleAtLeast(me?.role, 'engineer'));
</script>

<header>
  <span class="brand">HypervisionPLC SCADA</span>
  {#if me && !me.must_change_password}
    <nav>
      {#each visible as p}
        <a href={'#' + p.id} class:active={page === p.id}>{p.label}</a>
      {/each}
    </nav>
    <div class="user">
      <span title="Rolle: {me.role}">{me.username} <span class="role">{me.role}</span></span>
      <button class="link" onclick={() => (changingPassword = true)}>Adgangskode</button>
      <button class="link" onclick={logout}>Log ud</button>
    </div>
  {/if}
</header>

<main>
  {#if error}<div class="error">{error}</div>{/if}
  {#if !checked}
    <p class="muted">Indlæser …</p>
  {:else if !me}
    <Login onlogin={(m) => (me = m)} />
  {:else if me.must_change_password || changingPassword}
    <ChangePassword
      forced={me.must_change_password}
      ondone={() => { changingPassword = false; loadMe(); }}
      oncancel={() => (changingPassword = false)}
    />
  {:else if page === 'editor'}
    <Editor {route} />
  {:else if page === 'drawings'}
    <Drawings {canEdit} />
  {:else if page === 'tags'}
    <Tags {canEdit} />
  {:else if page === 'plcs'}
    <Plcs isAdmin={me.role === 'admin'} />
  {:else if page === 'audit'}
    <Audit />
  {:else if page === 'users'}
    <Users {me} />
  {:else}
    <Overview {route} {canEdit} canOperate={roleAtLeast(me.role, 'operator')} />
  {/if}
</main>

<footer>
  {#if info}
    <span>v{info.version} build {info.build}</span>
  {/if}
  <span>Fri software under AGPL-3.0 —
    <a href={info?.source_url ?? 'https://github.com/Jangreenlarsen/HypervisionPLC-SCADA'} target="_blank" rel="noopener">kildekode</a>
  </span>
</footer>

<style>
  header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: .5rem 1.5rem;
    padding: .5rem 1rem;
    background: #3a3a3a;
    color: #fff;
    min-height: 2.75rem;
  }
  .brand { font-weight: 600; }
  nav { display: flex; gap: .25rem; flex-wrap: wrap; }
  nav a {
    color: #ddd;
    text-decoration: none;
    padding: .3rem .7rem;
    border-radius: 4px;
  }
  nav a.active, nav a:hover { background: #575757; color: #fff; }
  .user { margin-left: auto; display: flex; gap: .75rem; align-items: center; flex-wrap: wrap; font-size: .9rem; }
  .role { color: #bbb; font-size: .8rem; }
  .link { background: none; border: none; color: #ddd; padding: 0; text-decoration: underline; }
  .link:hover { color: #fff; }
  main { padding: 1rem; max-width: 1600px; margin: 0 auto; }
  footer {
    display: flex;
    flex-wrap: wrap;
    gap: .25rem 1rem;
    justify-content: space-between;
    padding: .5rem 1rem 1rem;
    font-size: .8rem;
    color: var(--muted);
    max-width: 1600px;
    margin: 0 auto;
  }
  @media (max-width: 600px) {
    main { padding: .75rem 16px; }
    header { padding: .5rem 16px; }
    .user { margin-left: 0; }
  }
</style>
