<script lang="ts">
  // Hjælper-panelet (v4.1.0, PLAN.md fase 1): spørg hjælperen fra enhver side. Konteksten følger siden (tegning, alarm).
  // Svaret strømmes; kilderne vises som links. Samtalen gemmes kun i fanens sessionStorage — ikke på serveren.
  // Hjælperen kan kun læse og foreslå: den ændrer aldrig noget i anlægget.
  import { tick } from 'svelte';
  import { answerHtml, ask, contextFromRoute, historyFor, loadTurns, saveTurns, timingText, type Turn } from './assist';
  import { assist } from './assistStore.svelte';

  let { route, page }: { route: string; page: string } = $props();

  let turns = $state<Turn[]>(loadTurns());
  let question = $state('');
  let busy = $state(false);
  let phase = $state('');           // "I kø …", "Læser data …", "Skriver …"
  let started = $state(0);
  let elapsed = $state(0);
  let controller: AbortController | null = null;
  let list = $state<HTMLElement>();
  let input = $state<HTMLTextAreaElement>();

  const SUGGEST: Record<string, string[]> = {
    alarms: ['Hvilke alarmer er vigtigst lige nu?', 'Hvordan kvitterer jeg en alarm?'],
    overview: ['Hvad viser denne tegning?', 'Er der noget unormalt lige nu?'],
    trends: ['Hvordan vælger jeg en periode?', 'Hvordan eksporterer jeg data?'],
    draw: ['Hvordan laver jeg et rør mellem to symboler?', 'Hvordan sætter jeg et symbol op?'],
  };
  const suggestions = $derived(SUGGEST[page] ?? ['Hvordan kommer jeg i gang?', 'Hvad betyder SYS-alarmer?']);

  $effect(() => { saveTurns(turns); });
  $effect(() => {
    if (!busy) return;
    const t = setInterval(() => (elapsed = Math.round((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(t);
  });
  // En anden side beder om et svar (fx *Forklar* ved en alarm)
  $effect(() => {
    const req = assist.request;
    if (req && !busy) {
      assist.request = null;
      send(req.question, { alarm: req.alarm, tags: req.tags, label: req.label });
    }
  });
  $effect(() => { if (assist.open) tick().then(() => input?.focus()); });

  async function scrollDown(): Promise<void> {
    await tick();
    list?.scrollTo({ top: list.scrollHeight });
  }

  async function send(text: string, extra: { alarm?: string; tags?: string[]; label?: string } = {}): Promise<void> {
    const q = text.trim();
    if (!q || busy) return;
    const history = historyFor(turns);
    turns.push({ role: 'user', content: q, label: extra.label });
    turns.push({ role: 'assistant', content: '' });
    const answer = turns[turns.length - 1];
    question = '';
    busy = true;
    phase = 'Læser data og manual …';
    started = Date.now();
    elapsed = 0;
    controller = new AbortController();
    scrollDown();
    try {
      await ask({ question: q, context: { ...contextFromRoute(route, page), alarm: extra.alarm ?? null, tags: extra.tags ?? [] }, history },
        (ev) => {
          if (ev.type === 'sources') answer.sources = ev.sources;
          else if (ev.type === 'queued') phase = `I kø — ${ev.waiting} spørgsmål foran …`;
          else if (ev.type === 'delta') { phase = 'Skriver …'; answer.content += ev.text; scrollDown(); }
          else if (ev.type === 'done') answer.ms = ev.ms;
          else if (ev.type === 'error') { answer.error = true; answer.content = answer.content ? `${answer.content}\n\n${ev.message}` : ev.message; }
        }, controller.signal);
      if (!answer.content.trim()) { answer.error = true; answer.content = 'Hjælperen gav intet svar — prøv at spørge anderledes.'; }
    } catch (e) {
      answer.error = true;
      answer.content = (e as Error).name === 'AbortError' ? (answer.content ? `${answer.content} …\n\n(stoppet)` : 'Stoppet.') : (e as Error).message;
    } finally {
      busy = false;
      phase = '';
      controller = null;
      turns = [...turns];
      scrollDown();
    }
  }

  function onKey(e: KeyboardEvent): void {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(question); }
    if (e.key === 'Escape') assist.open = false;
  }

  function clear(): void {
    if (busy) controller?.abort();
    turns = [];
  }
</script>

{#if assist.open}
  <aside class="assist" aria-label="Hjælper">
    <div class="head">
      <strong>Hjælper</strong>
      <span class="muted small">lokal LLM · kun læsning og forslag</span>
      <span class="spacer"></span>
      {#if turns.length}<button class="small" onclick={clear} title="Ryd samtalen">Ryd</button>{/if}
      <button class="small" onclick={() => (assist.open = false)} aria-label="Luk hjælperen" title="Luk (Esc)">✕</button>
    </div>
    <div class="list" bind:this={list}>
      {#if !turns.length}
        <p class="muted small">Spørg om anlægget eller om hvordan SCADA'en bruges. Hjælperen ser det samme som dig (alarmer, tags og
          tegninger du har adgang til) og manualen. Den ændrer aldrig noget — den fortæller, hvor du selv kan gøre det. Et svar tager
          typisk 1–2 minutter.</p>
        <div class="sugg">
          {#each suggestions as s (s)}<button class="small" onclick={() => send(s)}>{s}</button>{/each}
        </div>
      {/if}
      {#each turns as t, i (i)}
        {#if t.role === 'user'}
          <div class="q">{#if t.label}<span class="lbl">{t.label}</span>{/if}{t.content}</div>
        {:else}
          <div class="a" class:err={t.error}>
            {#if t.content}
              {#if t.error}<p>{t.content}</p>{:else}{@html answerHtml(t.content)}{/if}
            {:else if busy && i === turns.length - 1}
              <p class="muted"><span class="dots" aria-hidden="true"></span> {phase} {elapsed} s</p>
            {/if}
            {#if t.sources?.length && !t.error}
              <p class="src small">Kilder: {#each t.sources as s, k (s.href + k)}{#if k}{', '}{/if}<a href={s.href}>{s.label.replace(/^Manual › /, '')}</a>{/each}</p>
            {/if}
            {#if t.ms}<p class="muted small">{timingText({ ms: t.ms, tokens_per_s: 0 })}</p>{/if}
          </div>
        {/if}
      {/each}
    </div>
    <div class="foot">
      <textarea bind:this={input} bind:value={question} rows="2" maxlength="500" placeholder="Skriv et spørgsmål …" onkeydown={onKey}
                disabled={!assist.canAsk} aria-label="Spørgsmål til hjælperen"></textarea>
      {#if busy}
        <button onclick={() => controller?.abort()}>Stop</button>
      {:else}
        <button class="primary" onclick={() => send(question)} disabled={!question.trim() || !assist.canAsk}>Spørg</button>
      {/if}
    </div>
    {#if !assist.canAsk}<p class="small muted pad">Hjælperen kræver rollen operatør.</p>{/if}
  </aside>
{/if}

<style>
  .assist {
    position: fixed; top: 2.5rem; right: 0; bottom: 0; z-index: 35;
    width: min(26rem, 100vw); display: flex; flex-direction: column;
    background: var(--panel); border-left: 1px solid var(--line); box-shadow: -4px 0 12px rgba(0, 0, 0, .15);
  }
  .head { display: flex; align-items: center; gap: .5rem; padding: .45rem .6rem; border-bottom: 1px solid var(--line); }
  .spacer { flex: 1; }
  .list { flex: 1; overflow-y: auto; padding: .6rem; display: flex; flex-direction: column; gap: .5rem; }
  .q { align-self: flex-end; max-width: 85%; background: var(--accent); color: #fff; padding: .4rem .6rem; border-radius: 8px 8px 2px 8px; white-space: pre-wrap; }
  .lbl { display: block; font-size: .75rem; opacity: .85; }
  .a { align-self: flex-start; max-width: 95%; background: #fff; border: 1px solid var(--line); padding: .4rem .6rem; border-radius: 8px 8px 8px 2px; }
  .a :global(p) { margin: .25rem 0; }
  .a :global(ul), .a :global(ol) { margin: .25rem 0; padding-left: 1.2rem; }
  .a.err { border-color: var(--alarm); color: var(--alarm); }
  .src a { color: var(--accent); }
  .sugg { display: flex; flex-wrap: wrap; gap: .35rem; }
  .foot { display: flex; gap: .4rem; padding: .5rem .6rem; border-top: 1px solid var(--line); align-items: flex-end; }
  .foot textarea { flex: 1; resize: none; font: inherit; }
  .pad { padding: 0 .6rem .4rem; margin: 0; }
  .dots::before { content: '●'; animation: pulse 1.2s infinite; }
  @keyframes pulse { 0%, 100% { opacity: .2; } 50% { opacity: 1; } }
</style>
