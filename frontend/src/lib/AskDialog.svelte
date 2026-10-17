<script lang="ts">
  // Viser det første spørgsmål i askQueue (lib/ask.ts) — erstatter browserens confirm()/prompt(), som Firefox kan blokere.
  import { askQueue } from './ask';

  const req = $derived($askQueue[0] ?? null);
  let value = $state('');
  let okBtn = $state<HTMLButtonElement | null>(null);
  let inputEl = $state<HTMLInputElement | null>(null);

  $effect(() => {
    if (!req) return;
    value = req.input?.value ?? '';
    // fokus på feltet eller OK, så Enter svarer og Escape annullerer med det samme
    queueMicrotask(() => (req.input ? inputEl?.focus() : okBtn?.focus()));
  });
  const answer = (ok: boolean) => req?.resolve(ok ? (req.input ? value : '') : null);
  function onKey(e: KeyboardEvent): void {
    if (!req) return;
    if (e.key === 'Escape') { e.preventDefault(); answer(false); }
    else if (e.key === 'Enter' && req.input) { e.preventDefault(); answer(true); }
  }
</script>

<svelte:window onkeydown={onKey} />

{#if req}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="backdrop" onclick={() => answer(false)}>
    <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
    <div class="panel dlg" role="alertdialog" aria-modal="true" aria-label="Spørgsmål" tabindex="-1" onclick={(e) => e.stopPropagation()}>
      <p class="text">{req.text}</p>
      {#if req.input}<input bind:this={inputEl} bind:value placeholder={req.input.placeholder} autocomplete="off" />{/if}
      <footer class="row">
        <span class="spacer"></span>
        <button onclick={() => answer(false)}>{req.cancel}</button>
        <button bind:this={okBtn} class={req.danger ? 'danger' : 'primary'} onclick={() => answer(true)}>{req.ok}</button>
      </footer>
    </div>
  </div>
{/if}

<style>
  .backdrop { position: fixed; inset: 0; background: rgba(0, 0, 0, .35); display: flex; align-items: flex-start; justify-content: center; padding: 18vh 16px 0; z-index: 60; }
  .dlg { width: 100%; max-width: 520px; box-shadow: 0 8px 30px rgba(0, 0, 0, .3); }
  .text { margin: 0 0 .6rem; white-space: pre-line; overflow-wrap: anywhere; }
  input { width: 100%; margin-bottom: .4rem; }
  footer { gap: .5rem; padding-top: .5rem; border-top: 1px solid var(--line); }
  .spacer { flex: 1; }
</style>
