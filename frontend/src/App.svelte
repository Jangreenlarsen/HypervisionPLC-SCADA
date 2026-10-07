<script lang="ts">
  import { onMount } from 'svelte';
  import { get } from './lib/api';
  import Overview from './pages/Overview.svelte';
  import Drawings from './pages/Drawings.svelte';
  import Tags from './pages/Tags.svelte';
  import Plcs from './pages/Plcs.svelte';

  const pages = [
    { id: 'overview', label: 'Overview' },
    { id: 'drawings', label: 'Tegninger' },
    { id: 'tags', label: 'Tags' },
    { id: 'plcs', label: "PLC'er" },
  ];

  let route = $state(location.hash.slice(1) || 'overview');
  let info = $state<{ version: string; build: string; source_url: string } | null>(null);

  onMount(() => {
    const onHash = () => (route = location.hash.slice(1) || 'overview');
    window.addEventListener('hashchange', onHash);
    get<{ version: string; build: string; source_url: string }>('/api/health')
      .then((h) => (info = h))
      .catch((e) => console.error('Kunne ikke hente version:', e));
    return () => window.removeEventListener('hashchange', onHash);
  });

  const page = $derived(route.split('/')[0]);
</script>

<header>
  <span class="brand">HypervisionPLC SCADA</span>
  <nav>
    {#each pages as p}
      <a href={'#' + p.id} class:active={page === p.id}>{p.label}</a>
    {/each}
  </nav>
</header>

<main>
  {#if page === 'drawings'}
    <Drawings />
  {:else if page === 'tags'}
    <Tags />
  {:else if page === 'plcs'}
    <Plcs />
  {:else}
    <Overview {route} />
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
  }
</style>
