<script lang="ts">
  import { tick } from 'svelte';
  import { buildChapters, highlight, renderMarkdown, searchChapters } from '../lib/manual';

  // Kapitlerne er markdown-filer; eager = de ligger i selve programmet (ingen ekstra kald, virker også uden for nettet)
  const files = import.meta.glob('../manual/*.md', { query: '?raw', import: 'default', eager: true }) as Record<string, string>;
  const chapters = buildChapters(files);

  let { route }: { route: string } = $props();   // "manual", "manual/<kapitel>" eller "manual/<kapitel>/<afsnit>"
  let query = $state('');
  let body: HTMLElement | undefined = $state();
  let zoomed = $state<{ src: string; alt: string } | null>(null);   // et skærmbillede vist stort
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
    });
  });
</script>

<svelte:window onkeydown={(e) => { if (e.key === 'Escape') zoomed = null; }} />

{#if zoomed}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="lightbox" onclick={() => (zoomed = null)} role="dialog" aria-label="Skærmbillede: {zoomed.alt}" tabindex="-1">
    <img src={zoomed.src} alt={zoomed.alt} />
    <p>{zoomed.alt} <span class="muted small">— klik eller tryk Escape for at lukke</span></p>
  </div>
{/if}

<div class="manual">
  <aside aria-label="Kapitler">
    <label class="search">Søg i manualen
      <input type="search" bind:value={query} placeholder="fx logikblok, setpunkt, backup" />
    </label>
    <select class="chapter-select" aria-label="Kapitel" value={chapter.slug} onchange={(e) => (location.hash = href(e.currentTarget.value))}>
      {#each chapters as c}<option value={c.slug}>{c.title}</option>{/each}
    </select>
    {#if query.trim().length >= 2}
      <p class="small muted">{hits.length ? `${total} træf i ${hits.length} kapitler` : 'Ingen træf'}</p>
      <ul class="hits">
        {#each hits as h}
          <li>
            <a href={href(h.chapter.slug)}><strong>{h.chapter.title}</strong> <span class="muted small">({h.count})</span></a>
            {#each h.snippets as s}<div class="snip small muted">{s}</div>{/each}
          </li>
        {/each}
      </ul>
    {:else}
      <nav>
        <ol>
          {#each chapters as c}
            <li class:current={c.slug === chapter.slug}>
              <a href={href(c.slug)} aria-current={c.slug === chapter.slug ? 'page' : undefined}>{c.title}</a>
              {#if c.slug === chapter.slug && c.headings.length}
                <ul>{#each c.headings as h}<li><a href={href(c.slug, h.id)}>{h.text}</a></li>{/each}</ul>
              {/if}
            </li>
          {/each}
        </ol>
      </nav>
    {/if}
  </aside>

  <article class="panel">
    <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
    <div class="body" bind:this={body} onclick={onBodyClick}>{@html html}</div>
    <footer class="pager">
      {#if index > 0}<a class="btn" href={href(chapters[index - 1].slug)}>← {chapters[index - 1].title}</a>{:else}<span></span>{/if}
      {#if index < chapters.length - 1}<a class="btn" href={href(chapters[index + 1].slug)}>{chapters[index + 1].title} →</a>{/if}
    </footer>
  </article>
</div>

<style>
  .manual { display: grid; grid-template-columns: 17rem minmax(0, 1fr); gap: 1rem; align-items: start; }
  aside { position: sticky; top: 3.2rem; max-height: calc(100vh - 3.8rem); overflow-y: auto; }
  .search { display: flex; flex-direction: column; gap: .25rem; font-size: .85rem; color: var(--muted); margin-bottom: .6rem; }
  ol, ul { list-style: none; margin: 0; padding: 0; }
  nav li > a { display: block; padding: .3rem .5rem; border-radius: var(--radius); text-decoration: none; color: var(--text); }
  nav li > a:hover { background: var(--panel-2); }
  nav li.current > a { background: var(--accent); color: #fff; }
  nav li.current ul { margin: .15rem 0 .4rem .6rem; border-left: 2px solid var(--line); }
  nav li.current ul a { font-size: .85rem; padding: .15rem .5rem; color: var(--muted); }
  .hits li { margin-bottom: .6rem; }
  .snip { margin-left: .5rem; }
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
  .chapter-select { display: none; width: 100%; margin-bottom: .5rem; }
  @media (max-width: 800px) {
    .manual { grid-template-columns: minmax(0, 1fr); }
    aside { position: static; max-height: none; }
    .chapter-select { display: block; }
    nav { display: none; }                  /* kapitelvælgeren erstatter den lange liste */
    .body :global(pre), .body :global(code) { overflow-wrap: anywhere; }
  }
</style>
