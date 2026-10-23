<script lang="ts">
  import { onMount } from 'svelte';
  import { BUNDLE, isStale } from './lib/staleCheck';
  import { ApiError, get, onUnauthorized, post, roleAtLeast, type AlarmSummary, type Me } from './lib/api';
  import { NAV_ICON, groupOf, navFor, navHref, pageFor } from './lib/nav';
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
  import SystemConfig from './pages/SystemConfig.svelte';
  import Manual from './pages/Manual.svelte';
  import Alarms from './pages/Alarms.svelte';
  import Energy from './pages/Energy.svelte';
  import Schedules from './pages/Schedules.svelte';
  import Trends from './pages/Trends.svelte';
  import SymbolTest from './pages/SymbolTest.svelte';
  import { LiveClient } from './lib/live';
  import Login from './pages/Login.svelte';
  import ChangePassword from './pages/ChangePassword.svelte';
  import AskDialog from './lib/AskDialog.svelte';


  let route = $state(location.hash.slice(1) || 'overview');
  let info = $state<{ version: string; build: string; source_url: string } | null>(null);
  const stale = $derived(isStale(BUNDLE, info));   // serveren er opdateret, men fanen kører den gamle side
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
    const checkVersion = () => get<{ version: string; build: string; source_url: string }>('/api/health')
      .then((h) => (info = h))
      // fx under genstart efter en opdatering: næste tjek prøver igen, og banneret afhænger kun af et gyldigt svar
      .catch((e) => console.error('Kunne ikke hente version:', e));
    checkVersion();
    // En fane kan stå åben over en opdatering: tjek serverens version jævnligt og når fanen får fokus igen
    const timer = setInterval(checkVersion, 60_000);
    const onVisible = () => { if (document.visibilityState === 'visible') checkVersion(); };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      window.removeEventListener('hashchange', onHash);
      document.removeEventListener('visibilitychange', onVisible);
      clearInterval(timer);
    };
  });

  const groups = $derived(navFor(me?.role));
  const current = $derived(pageFor(route, me?.role));
  const page = $derived(current.id);
  // Fire menupunkter i topbjælken (Drift, Opsætning, System, Bruger). En rullemenu åbner af sig selv når musen
  // føres hen over punktet og lukker lidt efter at den forlader det; klik/tryk og tastatur virker også (touch har ingen hover).
  // Menuen foldes ud OVER indholdet (skubber ikke tegningen ned) og lukkes ved valg, Escape eller klik udenfor.
  let openMenu = $state<string | null>(null);
  let closeTimer: ReturnType<typeof setTimeout> | null = null;
  const HOVER_CLOSE_MS = 220;   // tid til at føre musen skråt fra punktet ned i menuen uden at den lukker
  $effect(() => { void route; openMenu = null; });
  function showMenu(id: string): void {
    if (closeTimer) clearTimeout(closeTimer);
    closeTimer = null;
    openMenu = id;
  }
  function hideMenuSoon(): void {
    if (closeTimer) clearTimeout(closeTimer);
    closeTimer = setTimeout(() => (openMenu = null), HOVER_CLOSE_MS);
  }
  const onHover = (id: string) => (e: PointerEvent) => { if (e.pointerType === 'mouse') showMenu(id); };
  const onLeave = (e: PointerEvent) => { if (e.pointerType === 'mouse') hideMenuSoon(); };
  function onKey(e: KeyboardEvent): void {
    if (e.key === 'Escape' && openMenu) openMenu = null;
  }
  function onWindowClick(e: MouseEvent): void {
    if (openMenu && !(e.target as Element | null)?.closest?.('.menubar')) openMenu = null;
  }
  const ROLE_TXT: Record<string, string> = { viewer: 'viewer', operator: 'operatør', panel: 'driftpanel', engineer: 'tekniker', admin: 'admin' };
  const canEdit = $derived(roleAtLeast(me?.role, 'engineer'));
  // Driftpanel (fx en skærm i produktionen): kun drifttegningen. Først når adgangskoden er skiftet — før det vises
  // det almindelige skift-adgangskode-billede.
  const isPanel = $derived(me?.role === 'panel' && !me.must_change_password && !changingPassword);
  // Driftpanelet må åbne Alarmer (kvittering) og Trends fra genvejene i tegningen; rettighederne håndhæves i backend
  const panelPage = $derived(isPanel && (page === 'alarms' || page === 'trends') ? page : null);
</script>

<svelte:window onkeydown={onKey} onclick={onWindowClick} />
{#snippet staleBanner()}
  <div class="stale" role="alert">
    <span><strong>SCADA er opdateret</strong> til v{info?.version} build {info?.build}, men denne side kører stadig v{BUNDLE.version} build {BUNDLE.build}. Genindlæs for at få de nye funktioner — gem dit arbejde først (fx i Tegn).</span>
    <button class="primary" onclick={() => location.reload()}>Genindlæs</button>
  </div>
{/snippet}
{#snippet icon(name: string)}<svg class="ico" viewBox="0 0 24 24" aria-hidden="true">{@html NAV_ICON[name]}</svg>{/snippet}

{#if isPanel && me}
  <!-- Driftpanel: kun drifttegningen — ingen topmenu, alarmklokke eller sidefod (kildekode-linket står i kolonnen) -->
  <main class="panel-mode">
    {#if stale}{@render staleBanner()}{/if}
    {#if error}<div class="error">{error}</div>{/if}
    {#if panelPage === 'alarms'}
      <Alarms canAck={true} />
    {:else if panelPage === 'trends'}
      <Trends canEdit={false} {route} />
    {:else}
      <Overview {route} canOperate={true} panel sourceUrl={info?.source_url ?? ''} onlogout={logout} />
    {/if}
  </main>
{:else}
<header>
  {#if me && !me.must_change_password}
    <nav class="menubar" aria-label="Hovedmenu">
      {#each groups as g}
        <div class="menu" class:open={openMenu === g.id} role="presentation" onpointerenter={onHover(g.id)} onpointerleave={onLeave}>
          <button class="top" class:here={groupOf(page)?.id === g.id} aria-haspopup="true" aria-expanded={openMenu === g.id}
                  onclick={() => (openMenu === g.id ? (openMenu = null) : showMenu(g.id))}>{g.label}<span class="caret" aria-hidden="true"></span></button>
          {#if openMenu === g.id}
            <div class="drop" role="menu">
              {#each g.pages as p}
                <a href={navHref(p.id, location.hash.slice(1))} role="menuitem" class:active={page === p.id} aria-current={page === p.id ? 'page' : undefined}
                   onclick={() => (openMenu = null)}>{@render icon(p.icon)}<span>{p.label}</span></a>
              {/each}
            </div>
          {/if}
        </div>
      {/each}
    </nav>
    <span class="crumb"><span class="grp">{groupOf(page)?.label}</span> <span class="sep">›</span> <strong>{current.label}</strong></span>
    <span class="spacer"></span>
    <a href="#alarms" class="bell {alarmSummary.unacked ? 'unacked' : ''} {alarmSummary.high ? 'high' : alarmSummary.active ? 'medium' : ''}"
       title="{alarmSummary.active} aktive alarmer, {alarmSummary.unacked} ukvitterede">
      {@render icon('alarms')}<span class="count">{alarmSummary.active}</span>{#if alarmSummary.unacked}<span class="unack">· {alarmSummary.unacked} ny</span>{/if}
    </a>
    <!-- AGPL-3.0 §13: link til kildekoden altid synligt -->
    <a class="src" href={info?.source_url ?? 'https://github.com/Jangreenlarsen/HypervisionPLC-SCADA'} target="_blank" rel="noopener"
       title="Fri software under AGPL-3.0{info ? ` · v${info.version} build ${info.build}` : ''}">AGPL<span class="srcfull"> · kildekode</span></a>
    <nav class="menubar" aria-label="Brugermenu">
      <div class="menu user" class:open={openMenu === 'user'} role="presentation" onpointerenter={onHover('user')} onpointerleave={onLeave}>
        <button class="top" aria-haspopup="true" aria-expanded={openMenu === 'user'} title="Rolle: {ROLE_TXT[me.role] ?? me.role}"
                onclick={() => (openMenu === 'user' ? (openMenu = null) : showMenu('user'))}>
          {@render icon('user')}<span class="name">Bruger</span><span class="caret" aria-hidden="true"></span>
        </button>
        {#if openMenu === 'user'}
          <div class="drop right" role="menu">
            <p class="who-line"><strong>{me.username}</strong> <span class="role">· {ROLE_TXT[me.role] ?? me.role}</span></p>
            <a href="#manual" role="menuitem" class:active={page === 'manual'} onclick={() => (openMenu = null)}>{@render icon('manual')}<span>Manual</span></a>
            <button role="menuitem" onclick={() => { openMenu = null; changingPassword = true; }}>{@render icon('key')}<span>Skift adgangskode</span></button>
            <button role="menuitem" onclick={() => { openMenu = null; logout(); }}>{@render icon('logout')}<span>Log ud</span></button>
            <p class="about">HypervisionPLC SCADA{#if info}<br />v{info.version} build {info.build}{/if}</p>
          </div>
        {/if}
      </div>
    </nav>
  {:else}
    <span class="brand">HypervisionPLC SCADA</span>
    <span class="spacer"></span>
    <a class="src" href={info?.source_url ?? 'https://github.com/Jangreenlarsen/HypervisionPLC-SCADA'} target="_blank" rel="noopener">AGPL · kildekode</a>
  {/if}
</header>

<main>
  {#if stale}{@render staleBanner()}{/if}
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
    <Trends {canEdit} {route} />
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
  {:else if page === 'symboltest'}
    <SymbolTest />
  {:else if page === 'plcs'}
    <Plcs isAdmin={me.role === 'admin'} />
  {:else if page === 'audit'}
    <Audit />
  {:else if page === 'backup'}
    <Backup />
  {:else if page === 'update'}
    <Update />
  {:else if page === 'config'}
    <SystemConfig />
  {:else if page === 'manual'}
    <Manual {route} />
  {:else if page === 'users'}
    <Users {me} />
  {:else}
    <Overview {route} {canEdit} canOperate={roleAtLeast(me.role, 'operator')} />
  {/if}
</main>

{/if}

<!-- spørgsmål til brugeren (i stedet for browserens confirm/prompt, som Firefox kan blokere) -->
<AskDialog />

<style>
  .stale { display: flex; align-items: center; gap: .8rem; flex-wrap: wrap; margin-bottom: .6rem; padding: .5rem .8rem; color: #5a3a00; background: #fff4e0; border: 1px solid #f0c27a; border-radius: var(--radius); }
  .stale span { flex: 1; min-width: 14rem; }
  /* Smal topbjælke (40 px) med fire menupunkter; rullemenuerne foldes ud over indholdet, så tegningen beholder pladsen */
  header {
    position: sticky; top: 0; z-index: 40;
    display: flex; align-items: center; gap: .6rem;
    height: 2.5rem; padding: 0 .6rem;
    background: #3a3a3a; color: #fff;
  }
  .brand { font-weight: 600; padding-left: .4rem; }
  .spacer { flex: 1; }
  .ico { width: 18px; height: 18px; flex: none; stroke: currentColor; fill: none; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
  .menubar { display: flex; align-items: center; gap: .15rem; height: 100%; }
  .menu { position: relative; height: 100%; display: flex; align-items: center; }
  .menu.user { margin-left: .2rem; padding-left: .45rem; border-left: 1px solid #555; }
  .top {
    display: inline-flex; align-items: center; gap: .35rem; height: 2rem; padding: 0 .75rem;
    background: transparent; color: #eee; border: 1px solid transparent; border-radius: 4px; font: inherit; font-size: .95rem; cursor: pointer;
  }
  .top:hover, .menu.open .top { background: #575757; border-color: #777; color: #fff; }
  .top.here { box-shadow: inset 0 -2px 0 var(--accent); }
  .caret { width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid currentColor; opacity: .7; }
  .drop {
    position: absolute; top: 100%; left: 0; min-width: 13rem; padding: .35rem;
    background: var(--panel); color: var(--text); border: 1px solid var(--line); border-top: 0;
    border-radius: 0 0 var(--radius) var(--radius); box-shadow: 0 10px 28px rgba(0, 0, 0, .28);
    display: flex; flex-direction: column; gap: 1px;
  }
  .drop.right { left: auto; right: 0; min-width: 15rem; }
  .drop a, .drop button {
    display: flex; align-items: center; gap: .6rem; width: 100%; text-align: left;
    padding: .45rem .5rem; border-radius: var(--radius); color: var(--text); text-decoration: none;
    background: none; border: 0; font: inherit; cursor: pointer;
  }
  .drop a:hover, .drop button:hover { background: var(--panel-2); }
  .drop a.active { background: var(--accent); color: #fff; }
  .drop .who-line { margin: .25rem .5rem .3rem; }
  .drop .role { color: var(--muted); }
  .drop .about { font-size: .75rem; color: var(--muted); margin: .4rem .5rem .2rem; border-top: 1px solid var(--line); padding-top: .4rem; }
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
  .src { color: #bbb; font-size: .75rem; white-space: nowrap; }

  /* Ingen breddegrænse: SCADA bruges også på store kontrolrumsskærme */
  main { padding: .75rem 1rem 1rem; }
  main.panel-mode { padding: .5rem; }
  @media (max-width: 640px) {
    main { padding: .75rem 16px; }
    header { padding: 0 .5rem; gap: .45rem; }
    .crumb, .menu.user .name, .srcfull, .caret { display: none; }   /* alle fire menupunkter, klokken og AGPL-linket skal være på én linje */
    .top { padding: 0 .4rem; font-size: .88rem; }
    .menubar { gap: 0; }
    .menu.user { margin-left: 0; padding-left: .25rem; }
    .src { font-size: .7rem; }
  }
</style>
