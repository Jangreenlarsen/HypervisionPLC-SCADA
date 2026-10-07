<script lang="ts">
  import { post, type Me } from '../lib/api';

  let { onlogin }: { onlogin: (me: Me) => void } = $props();
  let username = $state('');
  let password = $state('');
  let error = $state('');
  let busy = $state(false);

  async function submit(e: SubmitEvent): Promise<void> {
    e.preventDefault();
    error = '';
    busy = true;
    try {
      onlogin(await post<Me>('/api/auth/login', { username: username.trim(), password }));
    } catch (err) {
      error = (err as Error).message;
      password = '';
    } finally {
      busy = false;
    }
  }
</script>

<form class="panel login" onsubmit={submit}>
  <h2>Log ind</h2>
  {#if error}<div class="error">{error}</div>{/if}
  <label>Brugernavn<input bind:value={username} autocomplete="username" autocapitalize="off" spellcheck="false" required /></label>
  <label>Adgangskode<input type="password" bind:value={password} autocomplete="current-password" required /></label>
  <button class="primary" type="submit" disabled={busy || !username || !password}>Log ind</button>
</form>

<style>
  .login {
    max-width: 360px;
    margin: 10vh auto 0;
    display: flex;
    flex-direction: column;
    gap: .75rem;
  }
  label { display: flex; flex-direction: column; gap: .25rem; font-size: .9rem; color: var(--muted); }
</style>
