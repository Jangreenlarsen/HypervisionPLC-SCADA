<script lang="ts">
  import { onMount } from 'svelte';
  import { ApiError, get, onUnauthorized, post, roleAtLeast, type AlarmSummary, type Me, type Role } from './lib/api';
  import Overview from './pages/Overview.svelte';
  import Drawings from './pages/Drawings.svelte';
  import Tags from './pages/Tags.svelte';
  import Plcs from './pages/Plcs.svelte';
  import Users from './pages/Users.svelte';
  import Editor from './pages/Editor.svelte';
  import DrawEditor from './pages/DrawEditor.svelte';
  import Audit from './pages/Audit.svelte';
  import Backup from './pages/Backup.svelte';
  import Alarms from './pages/Alarms.svelte';
  import Energy from './pages/Energy.svelte';
  import Schedules from './pages/Schedules.svelte';
  import Trends from './pages/Trends.svelte';
  import { LiveClient } from './lib/live';
  import Login from './pages/Login.svelte';
  import ChangePassword from './pages/ChangePassword.svelte';

  const pages: { id: string; label: string; role: Role }[] = [
    { id: 'overview', label: 'Overview', role: 'viewer' },
    { id: 'alarms', label: 'Alarmer', role: 'viewer' },
    { id: 'trends', label: 'Trends', role: 'viewer' },
    { id: 'energy', label: 'Energi', role: 'viewer' },
    { id: 'drawings', label: 'Tegninger', role: 'viewer' },
    { id: 'draw', label: 'Tegn', role: 'engineer' },
    { id: 'editor', label: 'Bindinger', role: 'engineer' },
    { id: 'schedules', label: 'Ugeprogrammer', role: 'engineer' },
    { id: 'tags', label: 'Tags', role: 'viewer' },
    { id: 'plcs', label: "PLC'er", role: 'engineer' },
    { id: 'audit', label: 'Log', role: 'engineer' },
    { id: 'users', label: 'Brugere', role: 'admin' },
    { id: 'backup', label: 'Backup', role: 'admin' },
  ];

  let route = $state(location.hash.slice(1) || 'overview');
  let info = $state<{ version: string; build: string; source_url: string } | null>(null);
  let me = $state<Me | null>(null);
  let checked = $state(false);
  let changingPassword = $state(false);
  let alarmSummary = $state<AlarmSummary>({ active: 0, unacked: 0, high: 0 });
  let alarmLive: LiveClient | null = null;

  // Én let WebSocket til alarmklokken i toppen (abonnerer ikke på tags).
  $effect(() => {
    if (me && !me.must_change_password && !alarmLive) {
      alarmLive = new LiveClient(() => {});
      alarmLive.onAlarms = (s) => (alarmSummary = s);
      alarmLive.subscribe([]);
    } else if (!me && alarmLive) {
      alarmLive.close();
      alarmLive = null;
      alarmSummary = { active: 0, unacked: 0, high: 0 };
    }
  });
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
  // Driftpanel (fx en skærm i produktionen): kun drifttegningen. Først når adgangskoden er skiftet — før det vises
  // det almindelige skift-adgangskode-billede.
  const isPanel = $derived(me?.role === 'panel' && !me.must_change_password && !changingPassword);
</script>

{#if isPanel && me}
  <!-- Driftpanel: kun drifttegningen — ingen topmenu, alarmklokke eller sidefod (kildekode-linket står i kolonnen) -->
  <main class="panel-mode">
    {#if error}<div class="error">{error}</div>{/if}
    <Overview {route} canOperate={true} panel sourceUrl={info?.source_url ?? ''} onlogout={logout} />
  </main>
{:else}
<header>
  <span class="brand">HypervisionPLC SCADA</span>
  {#if me && !me.must_change_password}
    <nav>
      {#each visible as p}
        <a href={'#' + p.id} class:active={page === p.id}>{p.label}</a>
      {/each}
    </nav>
    <a href="#alarms" class="bell {alarmSummary.unacked ? 'unacked' : ''} {alarmSummary.high ? 'high' : alarmSummary.active ? 'medium' : ''}"
       title="{alarmSummary.active} aktive alarmer, {alarmSummary.unacked} ukvitterede">
      Alarmer <span class="count">{alarmSummary.active}</span>{#if alarmSummary.unacked}<span class="unack">&nbsp;· {alarmSummary.unacked} ny</span>{/if}
    </a>
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
  {:else if page === 'schedules'}
    <Schedules />
  {:else if page === 'energy'}
    <Energy {canEdit} />
  {:else if page === 'trends'}
    <Trends {canEdit} />
  {:else if page === 'alarms'}
    <Alarms canAck={roleAtLeast(me.role, 'operator')} />
  {:else if page === 'draw'}
    <DrawEditor {route} />
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
  {:else if page === 'backup'}
    <Backup />
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
{/if}

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
  .bell {
    margin-left: auto;
    color: #ddd;
    text-decoration: none;
    padding: .2rem .6rem;
    border-radius: 4px;
    border: 1px solid #666;
    font-size: .9rem;
  }
  .bell.medium { background: #b26a00; color: #fff; border-color: #b26a00; }
  .bell.high { background: #c62828; color: #fff; border-color: #c62828; }
  .bell.unacked { animation: bell 1s steps(2, start) infinite; }
  @keyframes bell { to { opacity: .55; } }
  @media (prefers-reduced-motion: reduce) { .bell.unacked { animation: none; } }
  .user { margin-left: .5rem; display: flex; gap: .75rem; align-items: center; flex-wrap: wrap; font-size: .9rem; }
  .role { color: #bbb; font-size: .8rem; }
  .link { background: none; border: none; color: #ddd; padding: 0; text-decoration: underline; }
  .link:hover { color: #fff; }
  /* Ingen breddegrænse: SCADA bruges også på store kontrolrumsskærme */
  main { padding: 1rem; }
  main.panel-mode { padding: .5rem; }
  footer {
    display: flex;
    flex-wrap: wrap;
    gap: .25rem 1rem;
    justify-content: space-between;
    padding: .5rem 1rem 1rem;
    font-size: .8rem;
    color: var(--muted);
  }
  @media (max-width: 600px) {
    main { padding: .75rem 16px; }
    header { padding: .5rem 16px; }
    .user { margin-left: 0; }
  }
</style>
