<script lang="ts">
  import { onMount } from 'svelte';
  import { ApiError, get, onUnauthorized, post, roleAtLeast, type AlarmSummary, type Me } from './lib/api';
  import { NAV_ICON, groupOf, navFor, pageFor } from './lib/nav';
  import Overview from './pages/Overview.svelte';
  import Drawings from './pages/Drawings.svelte';
  import Tags from './pages/Tags.svelte';
  import Plcs from './pages/Plcs.svelte';
  import Users from './pages/Users.svelte';
  import Editor from './pages/Editor.svelte';
  import DrawEditor from './pages/DrawEditor.svelte';
  import Audit from './pages/Audit.svelte';
  import Backup from './pages/Backup.svelte';
  import Update from './pages/Update.svelte';
  import Alarms from './pages/Alarms.svelte';
  import Energy from './pages/Energy.svelte';
  import Schedules from './pages/Schedules.svelte';
  import Trends from './pages/Trends.svelte';
  import { LiveClient } from './lib/live';
  import Login from './pages/Login.svelte';
  import ChangePassword from './pages/ChangePassword.svelte';


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

  const groups = $derived(navFor(me?.role));
  const current = $derived(pageFor(route, me?.role));
  const page = $derived(current.id);
  // Menuen foldes ud OVER indholdet (skubber ikke tegningen ned) og lukkes ved valg, Escape eller klik udenfor
  let menuOpen = $state(false);
  $effect(() => { void route; menuOpen = false; });
  function onKey(e: KeyboardEvent): void {
    if (e.key === 'Escape' && menuOpen) menuOpen = false;
  }
  const ROLE_TXT: Record<string, string> = { viewer: 'viewer', operator: 'operatør', panel: 'driftpanel', engineer: 'tekniker', admin: 'admin' };
  const canEdit = $derived(roleAtLeast(me?.role, 'engineer'));
  // Driftpanel (fx en skærm i produktionen): kun drifttegningen. Først når adgangskoden er skiftet — før det vises
  // det almindelige skift-adgangskode-billede.
  const isPanel = $derived(me?.role === 'panel' && !me.must_change_password && !changingPassword);
</script>

<svelte:window onkeydown={onKey} />
{#snippet icon(name: string)}<svg class="ico" viewBox="0 0 24 24" aria-hidden="true">{@html NAV_ICON[name]}</svg>{/snippet}

{#if isPanel && me}
  <!-- Driftpanel: kun drifttegningen — ingen topmenu, alarmklokke eller sidefod (kildekode-linket står i kolonnen) -->
  <main class="panel-mode">
    {#if error}<div class="error">{error}</div>{/if}
    <Overview {route} canOperate={true} panel sourceUrl={info?.source_url ?? ''} onlogout={logout} />
  </main>
{:else}
<header>
  {#if me && !me.must_change_password}
    <button class="menu-btn" aria-expanded={menuOpen} aria-controls="hovedmenu" onclick={() => (menuOpen = !menuOpen)}>
      {@render icon(menuOpen ? 'close' : 'menu')}<span>Menu</span>
    </button>
    <span class="crumb"><span class="grp">{groupOf(page)?.label}</span> <span class="sep">›</span> <strong>{current.label}</strong></span>
    <span class="spacer"></span>
    <a href="#alarms" class="bell {alarmSummary.unacked ? 'unacked' : ''} {alarmSummary.high ? 'high' : alarmSummary.active ? 'medium' : ''}"
       title="{alarmSummary.active} aktive alarmer, {alarmSummary.unacked} ukvitterede">
      {@render icon('alarms')}<span class="count">{alarmSummary.active}</span>{#if alarmSummary.unacked}<span class="unack">· {alarmSummary.unacked} ny</span>{/if}
    </a>
    <!-- AGPL-3.0 §13: link til kildekoden altid synligt -->
    <a class="src" href={info?.source_url ?? 'https://github.com/Jangreenlarsen/HypervisionPLC-SCADA'} target="_blank" rel="noopener"
       title="Fri software under AGPL-3.0{info ? ` · v${info.version} build ${info.build}` : ''}">AGPL · kildekode</a>
    <span class="who" title="Rolle: {ROLE_TXT[me.role] ?? me.role}">{@render icon('user')}<span class="name">{me.username}</span></span>
  {:else}
    <span class="brand">HypervisionPLC SCADA</span>
    <span class="spacer"></span>
    <a class="src" href={info?.source_url ?? 'https://github.com/Jangreenlarsen/HypervisionPLC-SCADA'} target="_blank" rel="noopener">AGPL · kildekode</a>
  {/if}
</header>

{#if menuOpen && me}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="menu-scrim" onclick={() => (menuOpen = false)}></div>
  <nav id="hovedmenu" class="menu-panel" aria-label="Hovedmenu">
    {#each groups as g}
      <section>
        <h2>{g.label}</h2>
        {#each g.pages as p}
          <a href={'#' + p.id} class:active={page === p.id} aria-current={page === p.id ? 'page' : undefined}
             onclick={() => (menuOpen = false)}>{@render icon(p.icon)}<span>{p.label}</span></a>
        {/each}
      </section>
    {/each}
    <section class="me">
      <h2>{me.username} <span class="role">· {ROLE_TXT[me.role] ?? me.role}</span></h2>
      <button onclick={() => { menuOpen = false; changingPassword = true; }}>{@render icon('key')}<span>Skift adgangskode</span></button>
      <button onclick={() => { menuOpen = false; logout(); }}>{@render icon('logout')}<span>Log ud</span></button>
      <p class="about">HypervisionPLC SCADA{#if info}<br />v{info.version} build {info.build}{/if}</p>
    </section>
  </nav>
{/if}

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
  {:else if page === 'update'}
    <Update />
  {:else if page === 'users'}
    <Users {me} />
  {:else}
    <Overview {route} {canEdit} canOperate={roleAtLeast(me.role, 'operator')} />
  {/if}
</main>

{/if}

<style>
  /* Smal topbjælke (40 px); menuen foldes ud over indholdet i et panel, så tegningen beholder pladsen */
  header {
    position: sticky; top: 0; z-index: 40;
    display: flex; align-items: center; gap: .6rem;
    height: 2.5rem; padding: 0 .6rem;
    background: #3a3a3a; color: #fff;
  }
  .brand { font-weight: 600; padding-left: .4rem; }
  .spacer { flex: 1; }
  .ico { width: 18px; height: 18px; flex: none; stroke: currentColor; fill: none; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
  .menu-btn {
    display: inline-flex; align-items: center; gap: .4rem; height: 2rem; padding: 0 .7rem;
    background: transparent; color: #fff; border: 1px solid #666; border-radius: 4px;
  }
  .menu-btn:hover, .menu-btn[aria-expanded="true"] { background: #575757; border-color: #888; }
  .crumb { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; font-size: .95rem; }
  .crumb .grp, .crumb .sep { color: #bbb; }
  .bell {
    display: inline-flex; align-items: center; gap: .35rem; white-space: nowrap;
    color: #ddd; text-decoration: none; padding: .15rem .55rem; border-radius: 4px; border: 1px solid #666; font-size: .9rem;
  }
  .bell .count { font-weight: 700; font-variant-numeric: tabular-nums; }
  .bell.medium { background: #b26a00; color: #fff; border-color: #b26a00; }
  .bell.high { background: #c62828; color: #fff; border-color: #c62828; }
  .bell.unacked { animation: bell 1s steps(2, start) infinite; }
  @keyframes bell { to { opacity: .55; } }
  @media (prefers-reduced-motion: reduce) { .bell.unacked { animation: none; } }
  .src { color: #bbb; font-size: .75rem; white-space: nowrap; }
  .who { display: inline-flex; align-items: center; gap: .3rem; color: #ddd; font-size: .9rem; white-space: nowrap; }

  .menu-scrim { position: fixed; inset: 2.5rem 0 0 0; background: rgba(0, 0, 0, .25); z-index: 30; }
  .menu-panel {
    position: fixed; top: 2.5rem; left: 0; z-index: 35;
    width: min(100vw, 56rem); max-height: calc(100vh - 2.5rem); overflow-y: auto;
    display: grid; grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr)); gap: .25rem 1rem;
    padding: .75rem 1rem 1rem; background: var(--panel); color: var(--text);
    border: 1px solid var(--line); border-top: 0; border-radius: 0 0 var(--radius) 0; box-shadow: 0 10px 28px rgba(0, 0, 0, .25);
  }
  .menu-panel section { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
  .menu-panel h2 { font-size: .72rem; font-weight: 600; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin: .35rem .5rem .3rem; }
  .menu-panel a, .menu-panel button {
    display: flex; align-items: center; gap: .6rem; width: 100%; text-align: left;
    padding: .45rem .5rem; border-radius: var(--radius); color: var(--text); text-decoration: none;
    background: none; border: 0; font: inherit; cursor: pointer;
  }
  .menu-panel a:hover, .menu-panel button:hover { background: var(--panel-2); }
  .menu-panel a.active { background: var(--accent); color: #fff; }
  .menu-panel .me { border-left: 1px solid var(--line); padding-left: .75rem; }
  .menu-panel .role { text-transform: none; letter-spacing: 0; font-weight: 400; }
  .menu-panel .about { font-size: .75rem; color: var(--muted); margin: .5rem .5rem 0; }

  /* Ingen breddegrænse: SCADA bruges også på store kontrolrumsskærme */
  main { padding: .75rem 1rem 1rem; }
  main.panel-mode { padding: .5rem; }
  @media (max-width: 640px) {
    main { padding: .75rem 16px; }
    header { padding: 0 .5rem; gap: .45rem; }
    .crumb .grp, .crumb .sep, .who .name, .menu-btn span { display: none; }
    .src { font-size: .7rem; }
    .menu-panel .me { border-left: 0; padding-left: 0; border-top: 1px solid var(--line); padding-top: .5rem; }
  }
</style>
