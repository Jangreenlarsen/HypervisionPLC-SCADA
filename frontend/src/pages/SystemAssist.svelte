<script lang="ts">
  // System › Hjælper (LLM) (v3.37.0, PLAN.md fase 0): hardwareprofil, LLM-pakke (én samlet, lokal fil), slå tjenesten
  // til/fra og afprøv svartiden. Selve installationen udføres af en root-hjælper (deploy/apply-llm.sh).
  import { onDestroy, onMount } from 'svelte';
  import { ask } from '../lib/ask';
  import { ApiError, del, errorText, get, post, put } from '../lib/api';
  import { formatBytes, uploadWithProgress } from '../lib/upload';

  interface Profile { id: string; label: string; llm: boolean }
  interface Hw {
    profile: string; confirmed: boolean; set_by: string | null; llm_allowed: boolean; llm_mem_mb: number; llm_threads: number;
    warnings: string[]; profiles: Profile[];
    detected: { arch: string; cpus: number; ram_mb: number; avx2: boolean; pi_model: string; suggested: string };
  }
  interface Model { id: string; name: string; quant: string; license: string; size: number }
  interface Status {
    helper_installed: boolean; hw: Hw; available: boolean; busy: boolean; waiting: number;
    installed: { state: string; message: string; action: string; by: string; ts: number; model: Model | null; llama_build: string } | null;
    staged: { sha256: string; size: number; by: string; manifest: { llama_build: string; arch: string; model: Model } } | null;
    pending: { action: string; by: string } | null;
    service: { ok: boolean; status: string; model: string | null };
    stats: { requests: number; errors: number; last_ms: number | null; last_tokens_per_s: number | null; last_error: string | null };
  }
  interface TestResult { answer: string | null; ms: number; tokens_in: number; tokens_out: number; tokens_per_s: number; model: string }

  let st = $state<Status | null>(null);
  let error = $state('');
  let info = $state('');
  let busy = $state('');
  let progress = $state<number | null>(null);
  let profile = $state('');
  let test = $state<TestResult | null>(null);
  let timer: ReturnType<typeof setTimeout> | undefined;

  const STATE: Record<string, string> = {
    running: 'Kører', stopped: 'Slået fra', installing: 'Installerer …', error: 'Fejl', removed: 'Fjernet',
  };

  async function refresh(): Promise<void> {
    try {
      st = await get<Status>('/api/assist/status');
      if (!profile) profile = st.hw.profile;
      error = error.startsWith('Kunne ikke hente') ? '' : error;
    } catch (e) {
      error = `Kunne ikke hente hjælperens status: ${(e as Error).message}`;
    }
    clearTimeout(timer);
    // Følg med, mens en handling er i gang (installation af flere GB tager minutter)
    timer = setTimeout(refresh, st?.pending || st?.installed?.state === 'installing' ? 2000 : 10000);
  }
  onMount(refresh);
  onDestroy(() => clearTimeout(timer));

  async function run(what: string, fn: () => Promise<void>): Promise<void> {
    busy = what;
    error = info = '';
    try {
      await fn();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = '';
      await refresh();
    }
  }

  const saveProfile = () => run('profile', async () => {
    await put('/api/assist/profile', { profile });
    info = 'Hardwareprofilen er gemt';
  });

  async function upload(file: File | undefined): Promise<void> {
    if (!file) return;
    await run('upload', async () => {
      progress = 0;
      try {
        const r = await uploadWithProgress('/api/assist/package', file, (p) => (progress = p));
        if (!r.ok) throw new ApiError(r.status, errorText(r.status, r.body, 'Upload fejlede'), r.body);
        info = 'LLM-pakken er modtaget og kontrolleret — tryk Installér';
      } finally {
        progress = null;
      }
    });
  }

  const action = (a: 'install' | 'start' | 'stop' | 'remove') => run(a, async () => {
    if (a === 'remove' && !(await ask('Fjern LLM-hjælperen og modellen fra maskinen? Den kan installeres igen med LLM-pakken.', { ok: 'Fjern', danger: true }))) return;
    await post('/api/assist/service', { action: a });
    info = { install: 'Installationen er bestilt — den kontrollerer og pakker flere GB ud og tager nogle minutter',
             start: 'Hjælperen startes …', stop: 'Hjælperen slås fra …', remove: 'Hjælperen fjernes …' }[a];
  });

  const runTest = () => run('test', async () => {
    test = null;
    test = await post<TestResult>('/api/assist/test', {});
  });

  const when = (ts: number) => new Date(ts * 1000).toLocaleString('da-DK');
</script>

<h1>Hjælper (LLM)</h1>
<p class="muted">En lokal sprogmodel (kun CPU) som hjælper i SCADA'en. Den kører som sin egen tjeneste med lav prioritet og
  et loft over hukommelsen, kan slås fra, og skriver aldrig til en PLC. Alt er lokalt — intet sendes ud af maskinen.</p>
{#if error}<p class="error" role="alert">{error}</p>{/if}
{#if info}<p class="notice">{info}</p>{/if}

{#if st}
  {@const hw = st.hw}
  <section class="panel">
    <h2>Hardware</h2>
    <p class="small">Maskinen: <strong>{hw.detected.arch}</strong>, {hw.detected.cpus} CPU-kerner, {hw.detected.ram_mb ? `${Math.round(hw.detected.ram_mb / 102.4) / 10} GB` : 'ukendt'} RAM{hw.detected.pi_model ? `, ${hw.detected.pi_model}` : ''}{hw.detected.arch === 'x86_64' ? `, AVX2: ${hw.detected.avx2 ? 'ja' : 'nej'}` : ''}.
      Forslag: <strong>{hw.profiles.find((p) => p.id === hw.detected.suggested)?.label}</strong>.</p>
    <div class="row">
      <label>Hardwareprofil
        <select bind:value={profile} disabled={!!busy}>
          {#each hw.profiles as p (p.id)}<option value={p.id}>{p.label}{p.llm ? '' : ' — uden hjælper'}</option>{/each}
        </select>
      </label>
      <button onclick={saveProfile} disabled={!!busy || (profile === hw.profile && hw.confirmed)}>Gem profil</button>
    </div>
    <p class="small muted">{hw.confirmed ? `Valgt${hw.set_by ? ` af ${hw.set_by}` : ''}.` : 'Ikke bekræftet endnu — forslaget bruges.'}
      {hw.llm_allowed ? `Hjælperen får ${hw.llm_threads} tråde og højst ${hw.llm_mem_mb} MB RAM.` : 'Profilen tillader ikke hjælperen (for få ressourcer).'}</p>
    {#each hw.warnings as w (w)}<p class="small warn">⚠ {w}</p>{/each}
  </section>

  <section class="panel">
    <h2>LLM-tjeneste</h2>
    {#if !st.helper_installed}
      <p class="small warn">Hjælperens styring er ikke installeret på maskinen — opdatér SCADA'en (System › Opdatering).</p>
    {:else}
      {@const inst = st.installed}
      <p>
        Status: <strong>{st.pending ? `${st.pending.action} i gang …` : inst ? STATE[inst.state] ?? inst.state : 'Ikke installeret'}</strong>
        {#if inst?.model} · {inst.model.name} {inst.model.quant} ({formatBytes(inst.model.size)}, licens {inst.model.license}) · llama.cpp {inst.llama_build}{/if}
        {#if st.service.ok} · <span class="ok">svarer</span>{:else if inst?.state === 'running'} · {st.service.status === 'loading' ? 'indlæser modellen …' : 'svarer ikke endnu'}{/if}
      </p>
      {#if inst?.message}<p class="small muted">{inst.message} ({inst.by}, {when(inst.ts)})</p>{/if}
      <div class="row">
        {#if inst?.model}
          {#if inst.state === 'running'}
            <button onclick={() => action('stop')} disabled={!!busy || !!st.pending}>Slå fra</button>
          {:else}
            <button class="primary" onclick={() => action('start')} disabled={!!busy || !!st.pending || !hw.llm_allowed}>Slå til</button>
          {/if}
          <button class="danger" onclick={() => action('remove')} disabled={!!busy || !!st.pending}>Fjern</button>
        {/if}
      </div>
      <p class="small muted">Slået fra bruger hjælperen ingen CPU eller RAM. På maskiner med få ressourcer (fx Raspberry Pi 4) kan den ikke slås til.</p>

      <h3>LLM-pakke</h3>
      <p class="small muted">Én fil (<code>scada-llm-&lt;arkitektur&gt;-&lt;model&gt;-&lt;build&gt;.tar</code>, 3–6 GB) med llama.cpp og modellen —
        bygges med <code>deploy/make-llm-package.sh</code>. Den kontrolleres her og igen før installationen (SHA256).</p>
      {#if st.staged}
        {@const m = st.staged.manifest}
        <p class="notice small">Klar til installation: <strong>{m.model.name} {m.model.quant}</strong> ({m.arch}, llama.cpp {m.llama_build}, {formatBytes(st.staged.size)}, licens {m.model.license})
          <br /><span class="muted">SHA256 {st.staged.sha256.slice(0, 16)}… · uploadet af {st.staged.by}</span></p>
        <div class="row">
          <button class="primary" onclick={() => action('install')} disabled={!!busy || !!st.pending || !hw.llm_allowed}>Installér og slå til</button>
          <button onclick={() => run('discard', async () => { await del('/api/assist/package'); })} disabled={!!busy}>Kassér</button>
        </div>
      {:else}
        <label class="file">Vælg LLM-pakke …
          <input type="file" accept=".tar" disabled={!!busy || !hw.llm_allowed}
                 onchange={(e) => upload((e.currentTarget as HTMLInputElement).files?.[0])} />
        </label>
      {/if}
      {#if progress !== null}<p class="small">Uploader … {Math.round(progress * 100)} % <progress max="1" value={progress}></progress></p>{/if}
    {/if}
  </section>

  {#if st.installed?.state === 'running'}
    <section class="panel">
      <h2>Afprøv</h2>
      <p class="small muted">Et kort spørgsmål med fast svarformat — viser svartid og hastighed på denne maskine.</p>
      <button onclick={runTest} disabled={!!busy || !st.service.ok}>{busy === 'test' ? 'Venter på svar …' : 'Afprøv hjælperen'}</button>
      {#if test}
        <p><em>"{test.answer}"</em></p>
        <p class="small muted">{(test.ms / 1000).toFixed(1)} s · {test.tokens_in} → {test.tokens_out} tokens · {test.tokens_per_s} tokens/s · {test.model}</p>
      {/if}
      <p class="small muted">Siden start: {st.stats.requests} kald, {st.stats.errors} fejl{st.stats.last_ms !== null ? `, seneste ${(st.stats.last_ms / 1000).toFixed(1)} s` : ''}{st.stats.last_error ? ` — seneste fejl: ${st.stats.last_error}` : ''}.</p>
    </section>
  {/if}
{:else if !error}
  <p class="muted">Henter …</p>
{/if}

<style>
  section { margin-bottom: 1rem; }
  h2 { margin-top: 0; }
  .row { gap: .6rem; align-items: flex-end; flex-wrap: wrap; }
  .warn { color: #8a5a00; }
  .ok { color: #2e7d32; }
  .file input { display: block; margin-top: .3rem; }
  progress { width: 14rem; vertical-align: middle; }
</style>
