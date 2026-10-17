<script lang="ts">
  // Én tags alarm i symbolguiden (trin 6, v0.74.0): opsætning som kort tekst, status lige nu, og "Ret alarm" (PATCH /api/tags).
  import { api } from './api';
  import { alarmPayload, alarmStatus, alarmSummary, formFrom, type AlarmForm, type TagAlarm } from './tagAlarm';

  let { name, row, kind, active, unack, onsaved }: {
    name: string; row: TagAlarm & { unit?: string }; kind: 'bool' | 'num';
    active: unknown; unack: unknown; onsaved: (row: TagAlarm & { unit?: string }) => void;
  } = $props();

  let editing = $state(false);
  let form = $state<AlarmForm>(formFrom({}));
  let error = $state('');
  let saving = $state(false);
  const status = $derived(alarmStatus(active, unack));

  function open(): void {
    form = formFrom(row);
    error = '';
    editing = true;
  }
  async function save(): Promise<void> {
    const r = alarmPayload(form, kind);
    if ('error' in r) { error = r.error; return; }
    saving = true;
    error = '';
    try {
      onsaved(await api<TagAlarm & { unit?: string }>('PATCH', `/api/tags/${encodeURIComponent(name)}`, r.data));
      editing = false;
    } catch (e) {
      error = (e as Error).message;   // serverens tekst, fx "H skal være større end L"
    } finally {
      saving = false;
    }
  }
</script>

<tr>
  <td><strong>{name}</strong></td>
  <td class="small">{alarmSummary(row, row.unit ?? '')}</td>
  <td class="small"><span class="st {status.level}">{status.text}</span></td>
  <td><button class="small" onclick={() => (editing ? (editing = false) : open())} disabled={saving}>{editing ? 'Luk' : 'Ret alarm'}</button></td>
</tr>
{#if editing}
  <tr class="edit">
    <td colspan="4">
      <div class="row wrap">
        {#if kind === 'bool'}
          <label class="opt small">Alarm
            <select bind:value={form.on}><option value="">ingen</option><option value="true">når Til</option><option value="false">når Fra</option></select>
          </label>
        {:else}
          {#each [['hh', 'HH (høj-høj)'], ['h', 'H (høj)'], ['l', 'L (lav)'], ['ll', 'LL (lav-lav)']] as [k, label]}
            <label class="opt small">{label}<input class="n" bind:value={form[k as 'hh']} inputmode="decimal" placeholder="ingen" /></label>
          {/each}
          <label class="opt small">Dødbånd<input class="n" bind:value={form.deadband} inputmode="decimal" placeholder="0" /></label>
        {/if}
        <label class="opt small">Forsinkelse (s)<input class="n" bind:value={form.delay} inputmode="decimal" placeholder="0" /></label>
        <button class="small primary" onclick={save} disabled={saving}>{saving ? 'Gemmer…' : 'Gem alarm'}</button>
      </div>
      <p class="small muted">Gælder tagget overalt (samme som under <strong>Tags</strong>). {kind === 'bool' ? 'Til/fra-tag: alarm når værdien er Til eller Fra.' : 'Grænser i teknisk enhed; tomt = ingen grænse.'}</p>
      {#if error}<p class="small error">{error}</p>{/if}
    </td>
  </tr>
{/if}

<style>
  .st.unack { color: var(--alarm); font-weight: 600; }
  .st.active { color: #b26a00; font-weight: 600; }
  .st.none { color: #2e7d32; }
  .edit td { background: var(--panel-2); }
  .n { width: 5.5rem; }
  .opt { display: inline-flex; gap: .3rem; align-items: center; }
</style>
