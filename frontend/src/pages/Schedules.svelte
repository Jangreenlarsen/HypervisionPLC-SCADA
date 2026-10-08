<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { api, get } from '../lib/api';
  import { DAYS, fmtValue, PRESETS, toForm, toPayload, type ScheduleForm } from '../lib/scheduleUi';
  import TagSelect, { type TagOption } from '../lib/TagSelect.svelte';
  import WeekView from '../lib/WeekView.svelte';

  interface Timeline {
    now_value: number | null;
    next_changes: { at: number; value: number | null }[];
    week: { day: string; date: string; segments: { from: number; to: number; value: number | null }[] }[];
  }
  interface Schedule extends Timeline {
    id: number; name: string; tag: string; enabled: boolean; default_value: number | null;
    entries: { days: number[]; start: string; end: string; value: number }[];
    exceptions: { date_from: string; date_to: string; value: number | null; note?: string }[];
    status: { target: number | null; applied: boolean; error: string; last_write: number | null };
  }
  type Tag = TagOption & { min: number | null; max: number | null; description: string };

  let schedules = $state<Schedule[]>([]);
  let tags = $state<Tag[]>([]);
  let error = $state('');
  let editing = $state<{ id: number | null; form: ScheduleForm } | null>(null);
  let formError = $state('');
  let preview = $state<Timeline | null>(null);
  let previewError = $state('');
  let saving = $state(false);
  let timer: ReturnType<typeof setInterval> | null = null;
  let previewTimer: ReturnType<typeof setTimeout> | null = null;

  const tagOf = (name: string) => tags.find((t) => t.name === name);
  const isBool = (name: string) => /:coil:/.test(tagOf(name)?.source ?? '');
  const unitOf = (name: string) => tagOf(name)?.unit ?? '';
  const fmtTime = (ts: number) => new Date(ts * 1000).toLocaleString('da-DK', { weekday: 'short', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });

  async function refresh(): Promise<void> {
    try {
      schedules = await get<Schedule[]>('/api/schedules');
      error = '';
    } catch (e) {
      error = (e as Error).message;
    }
  }

  function newSchedule(): void {
    const tag = tags.find((t) => t.writable)?.name ?? '';
    editing = { id: null, form: { name: '', tag, enabled: true, default_value: '',
      entries: [{ days: [1, 2, 3, 4, 5], start: '06:00', end: '22:00', value: '' }], exceptions: [] } };
    formError = '';
    preview = null;
  }

  function edit(s: Schedule): void {
    editing = { id: s.id, form: toForm(s, isBool(s.tag)) };
    formError = '';
    schedulePreview();
  }

  /** Forhåndsvisning fra serveren (samme beregning som afviklingen), lidt forsinket mens der tastes. */
  function schedulePreview(): void {
    if (previewTimer) clearTimeout(previewTimer);
    previewTimer = setTimeout(async () => {
      if (!editing) return;
      try {
        preview = await api<Timeline>('POST', '/api/schedules/preview', toPayload(editing.form, isBool(editing.form.tag)));
        previewError = '';
      } catch (e) {
        previewError = (e as Error).message;
      }
    }, 300);
  }

  async function save(): Promise<void> {
    if (!editing) return;
    formError = '';
    saving = true;
    try {
      const body = toPayload(editing.form, isBool(editing.form.tag));
      if (editing.id === null) await api('POST', '/api/schedules', body);
      else await api('PUT', `/api/schedules/${editing.id}`, body);
      editing = null;
      await refresh();
    } catch (e) {
      formError = (e as Error).message;
    } finally {
      saving = false;
    }
  }

  async function toggleEnabled(s: Schedule): Promise<void> {
    try {
      await api('PUT', `/api/schedules/${s.id}`, { ...toPayload(toForm(s, isBool(s.tag)), isBool(s.tag)), enabled: !s.enabled });
      await refresh();
    } catch (e) {
      error = (e as Error).message;
    }
  }

  async function remove(s: Schedule): Promise<void> {
    if (!confirm(`Slet ugeprogrammet "${s.name}"? Tagget bevarer sin nuværende værdi.`)) return;
    try {
      await api('DELETE', `/api/schedules/${s.id}`);
      await refresh();
    } catch (e) {
      error = (e as Error).message;
    }
  }

  function toggleDay(e: ScheduleForm['entries'][number], d: number): void {
    e.days = e.days.includes(d) ? e.days.filter((x) => x !== d) : [...e.days, d].sort();
    schedulePreview();
  }

  onMount(async () => {
    try {
      tags = await get<Tag[]>('/api/tags');
    } catch (e) {
      error = (e as Error).message;
    }
    await refresh();
    timer = setInterval(refresh, 15000); // status og "nu" følger afviklingen
  });
  onDestroy(() => {
    if (timer) clearInterval(timer);
    if (previewTimer) clearTimeout(previewTimer);
  });
</script>

<div class="row toolbar">
  <button class="primary" onclick={newSchedule} disabled={!!editing}>+ Nyt ugeprogram</button>
  <span class="muted small">Ugeprogrammer skriver til PLC'en ved hvert skift — kun hvis værdien ikke allerede er sat, så en manuel ændring holder til næste skift.</span>
</div>
{#if error}<div class="error">{error}</div>{/if}

{#if editing}
  {@const f = editing.form}
  {@const bool = isBool(f.tag)}
  <section class="panel">
    <h2>{editing.id === null ? 'Nyt ugeprogram' : `Redigér "${f.name}"`}</h2>
    <div class="grid-form">
      <label>Navn<input bind:value={f.name} maxlength="60" placeholder="fx Komfort stue" /></label>
      <label>Tag (skal være skrivbart)
        <TagSelect value={f.tag} {tags} writableOnly onchange={(v) => { f.tag = v; schedulePreview(); }} />
      </label>
      <label>Uden for perioderne
        {#if bool}
          <select bind:value={f.default_value} onchange={schedulePreview}>
            <option value="">— rør ikke tagget —</option><option value="1">Til</option><option value="0">Fra</option>
          </select>
        {:else}
          <input bind:value={f.default_value} oninput={schedulePreview} inputmode="decimal" placeholder="tom = rør ikke tagget" />
        {/if}
      </label>
      <label class="check"><input type="checkbox" bind:checked={f.enabled} /> Aktivt</label>
    </div>
    {#if f.tag && !bool && (tagOf(f.tag)?.min !== null || tagOf(f.tag)?.max !== null)}
      <p class="muted small">Tagget tillader {tagOf(f.tag)?.min ?? '−∞'} til {tagOf(f.tag)?.max ?? '∞'} {unitOf(f.tag)}.</p>
    {/if}

    <h3>Perioder</h3>
    <p class="muted small">Tider er dansk tid. "22:00–06:00" går over midnat. Overlapper perioder, gælder den nederste. Brug 24:00 som slut for "til midnat".</p>
    {#each f.entries as e, i}
      <div class="entry">
        <div class="days">
          {#each DAYS as name, d}
            <button class="day" class:on={e.days.includes(d + 1)} onclick={() => toggleDay(e, d + 1)}>{name}</button>
          {/each}
          {#each PRESETS as p}<button class="small link-btn" onclick={() => { e.days = [...p.days]; schedulePreview(); }}>{p.label}</button>{/each}
        </div>
        <label>Fra<input class="time" bind:value={e.start} oninput={schedulePreview} placeholder="TT:MM" maxlength="5" /></label>
        <label>Til<input class="time" bind:value={e.end} oninput={schedulePreview} placeholder="TT:MM" maxlength="5" /></label>
        <label>Værdi
          {#if bool}
            <select bind:value={e.value} onchange={schedulePreview}><option value="1">Til</option><option value="0">Fra</option></select>
          {:else}
            <span class="row"><input class="num" bind:value={e.value} oninput={schedulePreview} inputmode="decimal" /> {unitOf(f.tag)}</span>
          {/if}
        </label>
        <button class="danger small" onclick={() => { f.entries = f.entries.filter((_, j) => j !== i); schedulePreview(); }} title="Fjern perioden">×</button>
      </div>
    {/each}
    <button onclick={() => { f.entries = [...f.entries, { days: [1, 2, 3, 4, 5], start: '06:00', end: '22:00', value: bool ? '1' : '' }]; schedulePreview(); }}>+ Periode</button>

    <h3>Undtagelser (fx ferie, helligdage)</h3>
    <p class="muted small">Gælder hele dage og erstatter ugeplanen. Tom værdi = værdien "uden for perioderne".</p>
    {#each f.exceptions as x, i}
      <div class="entry">
        <label>Fra dato<input type="date" bind:value={x.date_from} onchange={schedulePreview} /></label>
        <label>Til dato<input type="date" bind:value={x.date_to} onchange={schedulePreview} /></label>
        <label>Værdi
          {#if bool}
            <select bind:value={x.value} onchange={schedulePreview}><option value="">standard</option><option value="1">Til</option><option value="0">Fra</option></select>
          {:else}
            <input class="num" bind:value={x.value} oninput={schedulePreview} inputmode="decimal" placeholder="standard" />
          {/if}
        </label>
        <label>Note<input bind:value={x.note} maxlength="60" placeholder="fx Sommerferie" /></label>
        <button class="danger small" onclick={() => { f.exceptions = f.exceptions.filter((_, j) => j !== i); schedulePreview(); }} title="Fjern undtagelsen">×</button>
      </div>
    {/each}
    <button onclick={() => { const d = new Date().toISOString().slice(0, 10); f.exceptions = [...f.exceptions, { date_from: d, date_to: d, value: '', note: '' }]; schedulePreview(); }}>+ Undtagelse</button>

    <h3>Forhåndsvisning (denne uge)</h3>
    {#if previewError}<p class="small error">{previewError}</p>{/if}
    {#if preview}
      <WeekView week={preview.week} isBool={bool} unit={unitOf(f.tag)} />
      <p class="small muted">Nu: <strong>{fmtValue(preview.now_value, bool, unitOf(f.tag))}</strong>
        {#if preview.next_changes.length} · næste skift {fmtTime(preview.next_changes[0].at)} → {fmtValue(preview.next_changes[0].value, bool, unitOf(f.tag))}{/if}</p>
    {:else if !previewError}
      <button class="small" onclick={schedulePreview}>Vis forhåndsvisning</button>
    {/if}

    {#if formError}<div class="error">{formError}</div>{/if}
    <div class="row" style="margin-top: .8rem">
      <button class="primary" onclick={save} disabled={saving}>{saving ? 'Gemmer …' : 'Gem'}</button>
      <button onclick={() => (editing = null)} disabled={saving}>Annullér</button>
    </div>
  </section>
{/if}

{#if !schedules.length && !editing}
  <div class="panel muted">Ingen ugeprogrammer endnu. Et ugeprogram sætter fx et setpunkt til 21 °C på hverdage 06–22 og 17 °C resten af tiden.</div>
{/if}

<div class="list">
  {#each schedules as s (s.id)}
    {@const bool = isBool(s.tag)}
    <section class="panel" class:off={!s.enabled}>
      <div class="row head">
        <h3>{s.name}</h3>
        <span class="muted small">→ {tagOf(s.tag)?.description || s.tag}</span>
        {#if !s.enabled}<span class="badge">slået fra</span>
        {:else if s.status.error}<span class="badge error" title={s.status.error}>fejl</span>
        {:else if s.status.applied}<span class="badge connected">aktiv</span>{/if}
        <span class="spacer"></span>
        <label class="check small"><input type="checkbox" checked={s.enabled} onchange={() => toggleEnabled(s)} /> Aktivt</label>
        <button class="small" onclick={() => edit(s)} disabled={!!editing}>Redigér</button>
        <button class="small danger" onclick={() => remove(s)}>Slet</button>
      </div>
      {#if s.status.error}<p class="small error">Kunne ikke skrive: {s.status.error} — prøver igen om lidt.</p>{/if}
      <p class="small">Nu: <strong>{fmtValue(s.now_value, bool, unitOf(s.tag))}</strong>
        {#if s.next_changes.length} · næste skift {fmtTime(s.next_changes[0].at)} → <strong>{fmtValue(s.next_changes[0].value, bool, unitOf(s.tag))}</strong>{/if}
        {#if s.exceptions.length} · {s.exceptions.length} undtagelse{s.exceptions.length > 1 ? 'r' : ''}{/if}</p>
      <WeekView week={s.week} isBool={bool} unit={unitOf(s.tag)} compact />
    </section>
  {/each}
</div>

<style>
  .toolbar { margin-bottom: .75rem; }
  h3 { margin: 1rem 0 .3rem; }
  .head { align-items: center; gap: .6rem; flex-wrap: wrap; }
  .head h3 { margin: 0; }
  .spacer { flex: 1; }
  .entry { display: flex; flex-wrap: wrap; align-items: end; gap: .6rem; padding: .5rem 0; border-bottom: 1px dashed var(--line); }
  .entry label { display: flex; flex-direction: column; font-size: .85rem; }
  .days { display: flex; flex-wrap: wrap; gap: .2rem; align-items: center; }
  .day { min-width: 2.2rem; padding: .25rem .3rem; }
  .day.on { background: #2a78d6; color: #fff; border-color: #2a78d6; }
  .link-btn { background: none; border: none; text-decoration: underline; color: var(--accent); padding: 0 .2rem; }
  .time { width: 4.5rem; }
  .num { width: 6rem; }
  .list { display: grid; gap: .75rem; }
  .off { opacity: .7; }
  .badge.error { background: #c62828; color: #fff; border-color: #c62828; }
</style>
