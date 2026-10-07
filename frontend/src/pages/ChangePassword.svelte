<script lang="ts">
  import { post } from '../lib/api';

  let { forced = false, ondone, oncancel }: { forced?: boolean; ondone: () => void; oncancel?: () => void } = $props();
  let oldPw = $state('');
  let newPw = $state('');
  let repeat = $state('');
  let error = $state('');
  let busy = $state(false);

  async function submit(e: SubmitEvent): Promise<void> {
    e.preventDefault();
    error = '';
    if (newPw !== repeat) {
      error = 'De to nye adgangskoder er ikke ens';
      return;
    }
    busy = true;
    try {
      await post('/api/auth/password', { old_password: oldPw, new_password: newPw });
      ondone();
    } catch (err) {
      error = (err as Error).message;
    } finally {
      busy = false;
    }
  }
</script>

<form class="panel pw" onsubmit={submit}>
  <h2>Skift adgangskode</h2>
  {#if forced}<div class="notice">Du skal vælge en ny adgangskode, før du kan fortsætte.</div>{/if}
  {#if error}<div class="error">{error}</div>{/if}
  <label>Nuværende adgangskode<input type="password" bind:value={oldPw} autocomplete="current-password" required /></label>
  <label>Ny adgangskode (mindst 10 tegn)<input type="password" bind:value={newPw} autocomplete="new-password" minlength="10" required /></label>
  <label>Gentag ny adgangskode<input type="password" bind:value={repeat} autocomplete="new-password" required /></label>
  <div class="row">
    <button class="primary" type="submit" disabled={busy}>Gem</button>
    {#if !forced && oncancel}<button type="button" onclick={oncancel}>Annullér</button>{/if}
  </div>
</form>

<style>
  .pw { max-width: 420px; margin: 6vh auto 0; display: flex; flex-direction: column; gap: .75rem; }
  label { display: flex; flex-direction: column; gap: .25rem; font-size: .9rem; color: var(--muted); }
</style>
