<script lang="ts">
  // Dialog til at udsætte en aktiv alarm (v6.19.0, B5): begrundelse (påkrævet) og varighed. Backendens fejl vises i dialogen.
  import { onDestroy } from 'svelte';
  import { post, type Alarm } from './api';
  import { DEFAULT_SHELVE_MINUTES, REASON_MAX, SHELVE_OPTIONS, normalizeReason, reasonError, reasonLength } from './shelf';

  let { alarm, onclose, ondone }: { alarm: Alarm; onclose: () => void; ondone: () => void } = $props();

  let reason = $state('');
  let minutes = $state(DEFAULT_SHELVE_MINUTES);
  let error = $state('');
  let busy = $state(false);
  let reasonEl = $state<HTMLTextAreaElement | null>(null);
  let panelEl = $state<HTMLDivElement | null>(null);

  // Fokus føres tilbage til knappen, der åbnede dialogen (Udsæt), når den lukkes — hvis knappen stadig findes
  const opener = typeof document !== 'undefined' ? (document.activeElement as HTMLElement | null) : null;
  onDestroy(() => { if (opener?.isConnected) opener.focus(); });

  const invalid = $derived(reasonError(reason));
  const count = $derived(reasonLength(reason));
  $effect(() => { queueMicrotask(() => reasonEl?.focus()); });

  async function submit(): Promise<void> {
    if (invalid || busy) return;
    busy = true;
    error = '';
    try {
      await post('/api/alarms/shelve', { key: alarm.key, minutes, reason: normalizeReason(reason) });
      ondone();
    } catch (e) {
      error = (e as Error).message;   // den specifikke backend-fejl (fx 404/409/400)
    } finally {
      busy = false;
    }
  }

  // Escape lukker kun dialogen (lyttes på dialogen, ikke window); Tab bliver i dialogen (simpel fokusfælde)
  function onKey(e: KeyboardEvent): void {
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      if (!busy) onclose();
      return;
    }
    if (e.key !== 'Tab' || !panelEl) return;
    const items = [...panelEl.querySelectorAll<HTMLElement>('textarea, select, button:not([disabled])')];
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    const cur = document.activeElement;
    if (e.shiftKey && (cur === first || cur === panelEl)) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && (cur === last || cur === panelEl)) { e.preventDefault(); first.focus(); }
    else if (!panelEl.contains(cur)) { e.preventDefault(); first.focus(); }
  }

  // Et klik ved siden af dialogen må ikke kassere en indtastet begrundelse: kun en tom dialog lukkes af baggrunden
  function onBackdrop(): void {
    if (!busy && !reason.trim()) onclose();
    else reasonEl?.focus();   // fokus tilbage i dialogen, så Escape og Tab stadig virker
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={onBackdrop}>
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="panel dlg" role="dialog" aria-modal="true" aria-label="Udsæt alarm" tabindex="-1" bind:this={panelEl}
       onkeydown={onKey} onclick={(e) => e.stopPropagation()}>
    <h3>Udsæt alarm</h3>
    <p class="text">{alarm.message}</p>
    <p class="small muted">Alarmen skjules fra Aktive, indtil tiden er gået eller den genindsættes under fanen Udsatte. Udsættelsen logges med din begrundelse.</p>
    <label class="field">Begrundelse
      <textarea bind:this={reasonEl} bind:value={reason} rows="3" maxlength={REASON_MAX * 4} placeholder="Hvorfor udsættes alarmen?"
                aria-label="Begrundelse" aria-invalid={reason.length > 0 && !!invalid}></textarea>
    </label>
    <div class="small count" class:bad={reason.length > 0 && !!invalid}>{count} / {REASON_MAX} tegn (mindst 3)</div>
    <label class="field">Varighed
      <select bind:value={minutes} aria-label="Varighed">
        {#each SHELVE_OPTIONS as o (o.minutes)}<option value={o.minutes}>{o.label}</option>{/each}
      </select>
    </label>
    <div class="msg small" class:error={!!error} role="alert">{error}</div>
    <footer class="row">
      <span class="spacer"></span>
      <button onclick={onclose}>Annullér</button>
      <button class="primary" disabled={!!invalid || busy} onclick={submit}>Udsæt</button>
    </footer>
  </div>
</div>

<style>
  .backdrop { position: fixed; inset: 0; background: rgba(0, 0, 0, .35); display: flex; align-items: flex-start; justify-content: center; padding: 12vh 16px 0; z-index: 60; }
  .dlg { width: 100%; max-width: 520px; box-shadow: 0 8px 30px rgba(0, 0, 0, .3); }
  h3 { margin: 0 0 .4rem; }
  .text { margin: 0 0 .4rem; overflow-wrap: anywhere; }
  .field { display: block; margin-top: .5rem; }
  textarea, select { display: block; width: 100%; margin-top: .2rem; box-sizing: border-box; }
  textarea { resize: vertical; }
  .count { min-height: 1.3em; text-align: right; font-variant-numeric: tabular-nums; }
  .count.bad { color: var(--alarm); }
  .msg { min-height: 1.4em; margin-top: .4rem; }
  .msg.error { background: none; border: 0; padding: 0; color: var(--alarm); }
  footer { gap: .5rem; padding-top: .5rem; margin-top: .4rem; border-top: 1px solid var(--line); }
  .spacer { flex: 1; }
</style>
