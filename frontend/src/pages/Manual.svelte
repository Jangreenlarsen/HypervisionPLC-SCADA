<script lang="ts">
  import { onDestroy, tick } from 'svelte';
  import { buildChapters, groupChapters, highlight, renderMarkdown, searchChapters } from '../lib/manual';
  import { NAV_ICON } from '../lib/nav';

  // Kapitlerne er markdown-filer; eager = de ligger i selve programmet (ingen ekstra kald, virker også uden for nettet).
  // Undermappen manual/llm (hjælperens tillæg) kommer ikke med: mønsteret tager kun filerne i selve mappen.
  const files = import.meta.glob('../manual/*.md', { query: '?raw', import: 'default', eager: true }) as Record<string, string>;
  const chapters = buildChapters(files);
  const groups = groupChapters(chapters);

  let { route }: { route: string } = $props();   // "manual", "manual/<kapitel>" eller "manual/<kapitel>/<afsnit>"
  let query = $state('');
  let body: HTMLElement | undefined = $state();
  let zoomed = $state<{ src: string; alt: string } | null>(null);   // et skærmbillede vist stort
  let reading = $state('');          // ankeret for det afsnit, der læses lige nu (markeres i indekset)
  let showTop = $state(false);       // "Til toppen" vises, når man har rullet et stykke ned
  let tocOpen = $state(false);       // smal skærm: indekset er foldet sammen
  function onBodyClick(e: MouseEvent): void {
    const t = e.target as HTMLElement;
    if (t instanceof HTMLImageElement) zoomed = { src: t.src, alt: t.alt };
  }

  const parts = $derived(route.split('/'));
  const chapter = $derived(chapters.find((c) => c.slug === parts[1]) ?? chapters[0]);
  const index = $derived(chapters.indexOf(chapter));
  const html = $derived(renderMarkdown(chapter.md));
  const hits = $derived(searchChapters(chapters, query));
  const total = $derived(hits.reduce((n, h) => n + h.count, 0));

  const href = (slug: string, anchor = '') => `#manual/${slug}${anchor ? `/${anchor}` : ''}`;
  const icon = (name: string) => NAV_ICON[name] ?? NAV_ICON.manual;

  /** Efter hver visning: fremhæv søgeordet og rul til det afsnit adressen peger på (ellers til toppen). */
  $effect(() => {
    void html;
    const q = query;
    const anchor = parts[2];
    tick().then(() => {
      if (!body) return;
      if (q.trim().length >= 2) highlight(body, q);
      const target = anchor ? body.querySelector(`#${CSS.escape(anchor)}`) : null;
      if (target) target.scrollIntoView({ block: 'start' });
      else if (!q.trim()) window.scrollTo({ top: 0 });
      spy();
    });
  });

  /** Det afsnit, man læser: den sidste ##-overskrift, der er rullet op under topbjælken. */
  function spy(): void {
    showTop = window.scrollY > 600;
    if (!body) return;
    let current = '';
    for (const h of body.querySelectorAll('h2[id]')) {
      if (h.getBoundingClientRect().top - 90 <= 0) current = h.id;
      else break;
    }
    reading = current;
  }
  let raf = 0;
  const onScroll = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(spy); };
  onDestroy(() => cancelAnimationFrame(raf));
</script>

<svelte:window onkeydown={(e) => { if (e.key === 'Escape') zoomed = null; }} onscroll={onScroll} />

{#if zoomed}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="lightbox" onclick={() => (zoomed = null)} role="dialog" aria-label="Skærmbillede: {zoomed.alt}" tabindex="-1">
    <img src={zoomed.src} alt={zoomed.alt} />
    <p>{zoomed.alt} <span class="muted small">— klik eller tryk Escape for at lukke</span></p>
  </div>
{/if}

<div class="manual">
  <aside aria-label="Kapitler" class:open={tocOpen}>
    <label class="search">
      <span class="sr">Søg i manualen</span>
      <input type="search" bind:value={query} placeholder="Søg i manualen, fx logikblok, backup" />
    </label>
    <button class="toc-toggle" onclick={() => (tocOpen = !tocOpen)} aria-expanded={tocOpen}>
      <svg viewBox="0 0 24 24" aria-hidden="true">{@html icon(chapter.icon)}</svg>
      <span class="grow">{chapter.title}</span><span aria-hidden="true">{tocOpen ? '▴' : '▾'} Indhold</span>
    </button>
    {#if query.trim().length >= 2}
      <p class="small muted count">{hits.length ? `${total} træf i ${hits.length} kapitler` : 'Ingen træf — prøv et andet ord, eller spørg Hjælperen'}</p>
      <ul class="hits">
        {#each hits as h}
          <li>
            <a class="hit-ch" href={href(h.chapter.slug)} onclick={() => (tocOpen = false)}>
              <svg viewBox="0 0 24 24" aria-hidden="true">{@html icon(h.chapter.icon)}</svg>
              <strong>{h.chapter.title}</strong> <span class="pill">{h.count}</span>
            </a>
            {#each h.snippets as s}
              <a class="snip" href={href(h.chapter.slug, s.anchor)} onclick={() => (tocOpen = false)}>
                {#if s.heading}<span class="where">{s.heading}</span>{/if}
                <span class="muted">{s.text}</span>
              </a>
            {/each}
          </li>
        {/each}
      </ul>
    {:else}
      <nav>
        {#each groups as g}
          <div class="group">
            <div class="gname">{g.name}</div>
            <ol>
              {#each g.chapters as c}
                <li class:current={c.slug === chapter.slug}>
                  <a class="ch" href={href(c.slug)} aria-current={c.slug === chapter.slug ? 'page' : undefined} onclick={() => (tocOpen = false)}>
                    <svg viewBox="0 0 24 24" aria-hidden="true">{@html icon(c.icon)}</svg>
                    <span class="txt"><span class="t">{c.title}</span>{#if c.blurb}<span class="b">{c.blurb}</span>{/if}</span>
                  </a>
                  {#if c.slug === chapter.slug && c.headings.length}
                    <ul class="secs">
                      {#each c.headings as h}
                        <li><a href={href(c.slug, h.id)} class:reading={reading === h.id} onclick={() => (tocOpen = false)}>{h.text}</a></li>
                      {/each}
                    </ul>
                  {/if}
                </li>
              {/each}
            </ol>
          </div>
        {/each}
      </nav>
    {/if}
  </aside>

  <article class="panel">
    <div class="crumb small muted">Manual › {chapter.group} › <strong>{chapter.title}</strong> <span class="pos">· kapitel {index + 1} af {chapters.length}</span></div>
    <!-- Ny søgning = teksten tegnes forfra, så gamle markeringer (<mark>) forsvinder, også når feltet tømmes -->
    {#key query.trim().length >= 2 ? query : ''}
      <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
      <div class="body" bind:this={body} onclick={onBodyClick}>{@html html}</div>
    {/key}
    <footer class="pager">
      {#if index > 0}<a class="btn" href={href(chapters[index - 1].slug)}>← {chapters[index - 1].title}</a>{:else}<span></span>{/if}
      {#if index < chapters.length - 1}<a class="btn" href={href(chapters[index + 1].slug)}>{chapters[index + 1].title} →</a>{/if}
    </footer>
  </article>
</div>

{#if showTop}
  <button class="totop" onclick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} title="Til toppen af kapitlet">↑ Til toppen</button>
{/if}

<style>
  .manual { display: grid; grid-template-columns: 19rem minmax(0, 1fr); gap: 1rem; align-items: start; }
  aside { position: sticky; top: 3.2rem; max-height: calc(100vh - 3.8rem); overflow-y: auto; padding-right: .2rem; }
  .sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
  .search { display: block; margin-bottom: .7rem; }
  .search input { width: 100%; padding: .45rem .7rem; border-radius: 999px; }
  ol, ul { list-style: none; margin: 0; padding: 0; }
  svg { width: 1.15rem; height: 1.15rem; flex: none; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
  .group { margin-bottom: .55rem; }
  .gname { font-size: .7rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); padding: .35rem .5rem .15rem; }
  a.ch { display: flex; gap: .55rem; align-items: flex-start; padding: .32rem .5rem; border-radius: var(--radius); text-decoration: none; color: var(--text); }
  a.ch svg { margin-top: .1rem; color: var(--muted); }
  a.ch:hover { background: var(--panel-2); }
  .txt { display: flex; flex-direction: column; min-width: 0; }
  .txt .t { line-height: 1.25; }
  .txt .b { font-size: .74rem; color: var(--muted); line-height: 1.25; }
  li.current > a.ch { background: var(--accent); color: #fff; }
  li.current > a.ch svg, li.current > a.ch .b { color: rgba(255, 255, 255, .85); }
  .secs { margin: .2rem 0 .35rem 1.15rem; border-left: 2px solid var(--line); }
  .secs a { display: block; font-size: .82rem; padding: .16rem .55rem; color: var(--muted); text-decoration: none; border-left: 2px solid transparent; margin-left: -2px; }
  .secs a:hover { color: var(--text); background: var(--panel-2); }
  .secs a.reading { color: var(--accent); border-left-color: var(--accent); font-weight: 600; }
  .count { margin: 0 0 .5rem; }
  .hits li { margin-bottom: .7rem; }
  .hit-ch { display: flex; gap: .45rem; align-items: center; text-decoration: none; color: var(--text); padding: .2rem .3rem; }
  .pill { font-size: .72rem; background: var(--panel-2); border: 1px solid var(--line); border-radius: 999px; padding: 0 .4rem; color: var(--muted); }
  .snip { display: block; margin: .15rem 0 .15rem 1.6rem; padding: .25rem .45rem; border-radius: var(--radius); font-size: .8rem; text-decoration: none; line-height: 1.35; }
  .snip:hover { background: var(--panel-2); }
  .snip .where { display: block; font-weight: 600; color: var(--text); font-size: .76rem; }
  .crumb { margin-bottom: .6rem; }
  .crumb .pos { white-space: nowrap; }
  .toc-toggle { display: none; }
  .totop { position: fixed; right: 1.2rem; bottom: 1.2rem; z-index: 20; border-radius: 999px; box-shadow: 0 2px 8px rgba(0, 0, 0, .2); }
  article { min-width: 0; max-width: 60rem; }

  /* Indholdet kommer fra markdown, så reglerne rammer dets elementer */
  .body :global(h1) { margin-top: 0; }
  .body :global(h2) { margin-top: 1.8rem; padding-bottom: .25rem; border-bottom: 1px solid var(--line); scroll-margin-top: 3.2rem; }
  .body :global(h3) { margin-top: 1.2rem; scroll-margin-top: 3.2rem; }
  .body :global(p), .body :global(li) { line-height: 1.55; }
  .body :global(table) { border-collapse: collapse; margin: .6rem 0 1rem; display: block; overflow-x: auto; max-width: 100%; }
  .body :global(th), .body :global(td) { border: 1px solid var(--line); padding: .35rem .55rem; text-align: left; vertical-align: top; }
  .body :global(th) { background: var(--panel-2); }
  .body :global(code) { background: var(--panel-2); padding: .05rem .3rem; border-radius: 3px; font-size: .9em; }
  .body :global(blockquote) { margin: .8rem 0; padding: .4rem .9rem; background: #fff8e1; border-left: 4px solid #f0b429; border-radius: var(--radius); }
  .body :global(blockquote p) { margin: .3rem 0; }
  .body :global(mark) { background: #ffe58f; padding: 0 .1rem; }
  .body :global(figure) { margin: 1rem 0 1.4rem; }
  .body :global(figure img) {
    display: block; max-width: 100%; height: auto; border: 1px solid var(--line); border-radius: var(--radius);
    box-shadow: 0 2px 8px rgba(0, 0, 0, .12); cursor: zoom-in; background: #fff;
  }
  .body :global(figcaption) { margin-top: .35rem; font-size: .82rem; color: var(--muted); }
  .lightbox {
    position: fixed; inset: 0; z-index: 100; background: rgba(0, 0, 0, .82); display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: .6rem; padding: 1rem; cursor: zoom-out;
  }
  .lightbox img { max-width: 96vw; max-height: 86vh; background: #fff; border-radius: 4px; }
  .lightbox p { color: #fff; margin: 0; text-align: center; }
  .lightbox .muted { color: #bbb; }
  .pager { display: flex; justify-content: space-between; gap: 1rem; margin-top: 1.5rem; padding-top: .8rem; border-top: 1px solid var(--line); }
  @media (max-width: 800px) {
    .manual { grid-template-columns: minmax(0, 1fr); }
    aside { position: static; max-height: none; }
    /* indekset foldes sammen bag en knap med det aktuelle kapitel; søgningen står altid fremme */
    .toc-toggle { display: flex; width: 100%; gap: .5rem; align-items: center; text-align: left; margin-bottom: .5rem; }
    .toc-toggle .grow { flex: 1; }
    aside:not(.open) nav { display: none; }
    .body :global(pre), .body :global(code) { overflow-wrap: anywhere; }
  }
</style>
