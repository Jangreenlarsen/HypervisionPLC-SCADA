<script lang="ts">
  // Fast plads til meddelelser (v1.10.0): en lille pille med den alvorligste besked (+ antal), som åbner en liste med alle. Fylder altid
  // den samme plads i værktøjslinjen og lægger sig OVER tegningen, når listen åbnes — så tegningen aldrig flytter sig.
  import { headline, oneLine, sortMessages, type Msg } from './messages';

  let { messages }: { messages: Msg[] } = $props();
  let open = $state(false);
  let root: HTMLElement | null = $state(null);

  const head = $derived(headline(messages));
  const sorted = $derived(sortMessages(messages));
  $effect(() => { if (!messages.length) open = false; });

  const ICON: Record<Msg['kind'], string> = { error: '⚠', warn: '⚠', ok: '✓', info: 'ℹ' };
  function outside(e: PointerEvent): void { if (open && root && !root.contains(e.target as Node)) open = false; }
  function key(e: KeyboardEvent): void { if (open && e.key === 'Escape') open = false; }
</script>

<svelte:window onpointerdown={outside} onkeydown={key} />

<div class="slot" bind:this={root}>
  {#if head}
    <button class="pill {head.first.kind}" aria-expanded={open} aria-haspopup="true" onclick={() => (open = !open)}
      title={open ? 'Luk' : 'Vis alle beskeder'}>
      <span aria-hidden="true">{ICON[head.first.kind]}</span>
      <span class="txt">{oneLine(head.first.text)}</span>
      {#if head.more}<span class="more">+{head.more}</span>{/if}
    </button>
    {#if open}
      <div class="pop" role="dialog" aria-label="Beskeder">
        {#each sorted as msg (msg.id)}
          <div class="msg {msg.kind}" role={msg.kind === 'error' ? 'alert' : 'status'}>
            <span class="body">{msg.text}
              {#if msg.link}<a href={msg.link.href}>{msg.link.label}</a>{/if}</span>
            {#if msg.action}<button class="small" onclick={msg.action.run} title={msg.action.title ?? ''}>{msg.action.label}</button>{/if}
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>

<style>
  .slot { position: relative; flex: 1 1 12rem; min-width: 0; display: flex; justify-content: flex-end; align-items: center; min-height: 2rem; }
  .pill { max-width: 100%; display: inline-flex; align-items: center; gap: .4rem; padding: .2rem .65rem; border-radius: 999px; border: 1px solid;
    font-size: .85rem; cursor: pointer; background: var(--panel); min-width: 0; }
  .pill .txt { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
  .pill .more { font-weight: 700; flex: 0 0 auto; }
  .pill.error, .msg.error { background: #fdecea; border-color: var(--alarm); color: var(--alarm); }
  .pill.warn, .msg.warn { background: #fff8e1; border-color: #e0b84a; color: #6b5200; }
  .pill.ok, .msg.ok { background: #e8f5e9; border-color: #a5d6a7; color: #1b5e20; }
  .pill.info, .msg.info { background: var(--panel-2); border-color: var(--line); color: var(--muted); }
  .pop { position: absolute; right: 0; top: calc(100% + .3rem); width: min(560px, 92vw); max-height: 60vh; overflow: auto; z-index: 40;
    background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: 0 8px 24px rgba(0, 0, 0, .25);
    padding: .4rem; display: flex; flex-direction: column; gap: .35rem; }
  .msg { display: flex; align-items: flex-start; justify-content: space-between; gap: .6rem; padding: .4rem .55rem; border: 1px solid; border-left-width: 5px;
    border-radius: var(--radius); font-size: .88rem; }
  .msg .body { overflow-wrap: anywhere; }
  .msg button { flex: 0 0 auto; }
</style>
