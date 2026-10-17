<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { ask as askUser } from '../lib/ask';
  import { del, get, patch, post, type LiveValue } from '../lib/api';
  import { formatValue } from '../lib/animate';
  import { SOURCE_LABEL, sourceKind } from '../lib/tagSource';
  import { LiveClient } from '../lib/live';

  let { canEdit = false }: { canEdit?: boolean } = $props();

  interface Tag {
    name: string; source: string; plc: string; description: string; unit: string;
    scale: number; offset: number; decimals: number | null; writable: boolean;
    min: number | null; max: number | null; confirm_write: boolean;
    alarm_hh: number | null; alarm_h: number | null; alarm_l: number | null; alarm_ll: number | null;
    alarm_deadband: number; alarm_delay_s: number; alarm_on: 'true' | 'false' | null;
    trend: boolean; trend_interval_s: number; energy: 'counter' | 'power' | null; energy_factor: number;
  }
  interface EditForm {
    name: string; source: string; description: string; unit: string; scale: string; offset: string;
    decimals: string; writable: boolean; min: string; max: string; confirm_write: boolean;
    alarm_hh: string; alarm_h: string; alarm_l: string; alarm_ll: string; alarm_deadband: string;
    alarm_delay_s: string; alarm_on: '' | 'true' | 'false'; trend: boolean; trend_interval_s: string;
    energy: '' | 'counter' | 'power'; energy_factor: string;
  }
  interface Suggestion { name: string; source: string; datatype: string; description: string; exists: boolean; pick?: boolean }

  let tags = $state<Tag[]>([]);
  let plcKeys = $state<string[]>([]);
  let values = $state<Record<string, LiveValue>>({});
  let error = $state('');
  let form = $state({ name: '', source: '', unit: '', scale: '1', offset: '0', decimals: '', description: '' });
  let discoverPlc = $state('');
  let suggestions = $state<Suggestion[]>([]);
  let importResult = $state('');
  let edit = $state<EditForm | null>(null);
  let editError = $state('');

  const s = (v: number | null) => (v === null || v === undefined ? '' : String(v));

  function startEdit(t: Tag): void {
    editError = '';
    edit = {
      name: t.name, source: t.source, description: t.description, unit: t.unit, scale: String(t.scale),
      offset: String(t.offset), decimals: s(t.decimals), writable: t.writable, min: s(t.min), max: s(t.max),
      confirm_write: t.confirm_write,
      alarm_hh: s(t.alarm_hh), alarm_h: s(t.alarm_h), alarm_l: s(t.alarm_l), alarm_ll: s(t.alarm_ll),
      alarm_deadband: String(t.alarm_deadband ?? 0), alarm_delay_s: String(t.alarm_delay_s ?? 0), alarm_on: t.alarm_on ?? '',
      trend: t.trend, trend_interval_s: String(t.trend_interval_s ?? 10),
      energy: t.energy ?? '', energy_factor: String(t.energy_factor ?? 1),
    };
  }

  async function saveEdit(): Promise<void> {
    if (!edit) return;
    editError = '';
    try {
      // Tomme felter for min/max/decimaler betyder "ingen" — 0 er en gyldig værdi.
      const opt = (text: string, field: string) => (text.trim() === '' ? null : num(text, field));
      await patch(`/api/tags/${encodeURIComponent(edit.name)}`, {
        source: edit.source.trim(), description: edit.description.trim(), unit: edit.unit.trim(),
        scale: num(edit.scale, 'Skala'), offset: num(edit.offset, 'Offset'),
        ...(edit.decimals.trim() === '' ? {} : { decimals: num(edit.decimals, 'Decimaler') }),
        writable: edit.writable, min: opt(edit.min, 'Min'), max: opt(edit.max, 'Max'), confirm_write: edit.confirm_write,
        alarm_hh: opt(edit.alarm_hh, 'HH'), alarm_h: opt(edit.alarm_h, 'H'), alarm_l: opt(edit.alarm_l, 'L'),
        alarm_ll: opt(edit.alarm_ll, 'LL'), alarm_deadband: num(edit.alarm_deadband || '0', 'Dødbånd'),
        alarm_delay_s: num(edit.alarm_delay_s || '0', 'Forsinkelse'), alarm_on: edit.alarm_on || null,
        trend: edit.trend, trend_interval_s: num(edit.trend_interval_s || '10', 'Interval'),
        energy: edit.energy || null, energy_factor: num(edit.energy_factor || '1', 'Omregning til kWh'),
      });
      edit = null;
      await refresh();
    } catch (e) {
      editError = (e as Error).message;
    }
  }

  const live = new LiveClient((changes) => (values = { ...values, ...changes }));

  async function refresh(): Promise<void> {
    try {
      tags = await get<Tag[]>('/api/tags');
      if (canEdit) {
        plcKeys = (await get<{ key: string }[]>('/api/plcs')).map((p) => p.key);
        discoverPlc ||= plcKeys[0] ?? '';
      }
      live.subscribe(tags.map((t) => t.name));
    } catch (e) {
      error = (e as Error).message;
    }
  }

  function num(text: string, field: string): number | undefined {
    if (text.trim() === '') return undefined;
    const n = Number(text.replace(',', '.'));
    if (!Number.isFinite(n)) throw new Error(`${field} skal være et tal`);
    return n;
  }

  async function create(): Promise<void> {
    error = '';
    try {
      const body: Record<string, unknown> = { name: form.name.trim(), source: form.source.trim() };
      if (form.unit.trim()) body.unit = form.unit.trim();
      if (form.description.trim()) body.description = form.description.trim();
      body.scale = num(form.scale, 'Skala');
      body.offset = num(form.offset, 'Offset');
      const dec = num(form.decimals, 'Decimaler');
      if (dec !== undefined) body.decimals = dec;
      await post('/api/tags', body);
      form = { name: '', source: '', unit: '', scale: '1', offset: '0', decimals: '', description: '' };
      await refresh();
    } catch (e) {
      error = (e as Error).message;
    }
  }

  async function remove(t: Tag): Promise<void> {
    if (!await askUser(`Slet tagget ${t.name}?`)) return;
    try {
      await del(`/api/tags/${encodeURIComponent(t.name)}`);
      await refresh();
    } catch (e) {
      error = (e as Error).message;
    }
  }

  async function discover(): Promise<void> {
    error = importResult = '';
    try {
      const res = await get<{ suggestions: Suggestion[] }>(`/api/plcs/${encodeURIComponent(discoverPlc)}/discover`);
      suggestions = res.suggestions.map((s) => ({ ...s, pick: false }));
      if (!suggestions.length) importResult = 'PLC\'en har ingen kompilerede ST-variabler at foreslå.';
    } catch (e) {
      error = (e as Error).message;
    }
  }

  async function importPicked(): Promise<void> {
    const picked = suggestions.filter((s) => s.pick && !s.exists);
    try {
      const res = await post<{ created: string[]; skipped: { name: string; reason: string }[] }>('/api/tags/import', {
        tags: picked.map((s) => ({ name: s.name, source: s.source, description: s.description })),
      });
      importResult = `Oprettet: ${res.created.length}` +
        (res.skipped.length ? ` · Sprunget over: ${res.skipped.map((s) => `${s.name} (${s.reason})`).join(', ')}` : '');
      suggestions = [];
      await refresh();
    } catch (e) {
      error = (e as Error).message;
    }
  }

  onMount(refresh);
  onDestroy(() => live.close());
</script>

{#if error}<div class="error">{error}</div>{/if}

{#if canEdit}
<section class="panel">
  <h2>Nyt tag</h2>
  <p class="muted small">
    <strong>Intern</strong> (PLC'ens egne registre): <code>plc1:hr:100</code>, <code>plc1:hr:20:real</code> (uint/int/dint/dword/real),
    <code>plc1:ir:7</code>, <code>plc1:coil:5</code>, <code>plc1:di:3</code>, <code>plc1:logic:1:Variabel</code>, <code>plc1:global:Variabel</code>.<br />
    <strong>Extern</strong> (slave på PLC'ens RS485-bus): <code>plc1:rtu:&lt;slave&gt;:&lt;hr|ir|coil|di&gt;:&lt;adresse&gt;[:datatype]</code>, fx <code>plc1:rtu:90:hr:0</code>.<br />
    <strong>Expansion board</strong>: <code>plc1:mbx:&lt;board&gt;:&lt;kanal A-H&gt;:&lt;slave&gt;:&lt;type&gt;:&lt;adresse&gt;</code>, fx <code>plc1:mbx:1:D:1:coil:0</code>.
    Eksterne værdier hentes hvert 2. sekund (kræver PLC-firmware 7.9.68.123+); hold antallet nede, PLC'ens cache er lille.<br />
    Teknisk værdi = rå × skala + offset.
  </p>
  <div class="grid-form">
    <label>Navn<input bind:value={form.name} placeholder="Pumpe1_Drift" /></label>
    <label>Kilde<input bind:value={form.source} placeholder="plc1:coil:0" /></label>
    <label>Enhed<input bind:value={form.unit} maxlength="16" /></label>
    <label>Skala<input bind:value={form.scale} inputmode="decimal" /></label>
    <label>Offset<input bind:value={form.offset} inputmode="decimal" /></label>
    <label>Decimaler<input bind:value={form.decimals} inputmode="numeric" placeholder="auto" /></label>
    <label>Beskrivelse<input bind:value={form.description} maxlength="200" /></label>
    <div><button class="primary" onclick={create} disabled={!form.name || !form.source}>Opret</button></div>
  </div>
</section>

<section class="panel">
  <h2>Foreslå tags fra PLC</h2>
  <div class="row">
    <select bind:value={discoverPlc}>{#each plcKeys as k}<option value={k}>{k}</option>{/each}</select>
    <button onclick={discover} disabled={!discoverPlc}>Hent ST-variabler</button>
    {#if suggestions.length}<button class="primary" onclick={importPicked}>Importér valgte</button>{/if}
  </div>
  {#if importResult}<div class="notice">{importResult}</div>{/if}
  {#if suggestions.length}
    <div class="table-wrap">
      <table>
        <thead><tr><th></th><th>Tag-navn</th><th>Kilde</th><th>Type</th><th>Beskrivelse</th></tr></thead>
        <tbody>
          {#each suggestions as s}
            <tr>
              <td><input type="checkbox" bind:checked={s.pick} disabled={s.exists} /></td>
              <td class="mono">{s.name}{s.exists ? ' (findes)' : ''}</td>
              <td class="mono">{s.source}</td>
              <td>{s.datatype}</td>
              <td>{s.description}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</section>
{/if}

{#if edit}
  <!-- Står fast øverst mens man scroller i listen; egen scroll så listen stadig kan ses nedenunder -->
  <section class="panel edit-panel" aria-label="Redigér tag">
    <h2>Redigér {edit.name}</h2>
    <div class="grid-form">
      <label>Kilde<input bind:value={edit.source} /></label>
      <label>Beskrivelse<input bind:value={edit.description} maxlength="200" /></label>
      <label>Enhed<input bind:value={edit.unit} maxlength="16" /></label>
      <label>Skala<input bind:value={edit.scale} inputmode="decimal" /></label>
      <label>Offset<input bind:value={edit.offset} inputmode="decimal" /></label>
      <label>Decimaler<input bind:value={edit.decimals} inputmode="numeric" placeholder="auto" /></label>
    </div>
    <h3 style="margin-top: .8rem">Betjening</h3>
    <div class="grid-form">
      <label class="row" style="flex-direction: row"><input type="checkbox" bind:checked={edit.writable} /> Skrivbar fra Overview (kun hr/coil)</label>
      <label>Min (teknisk enhed)<input bind:value={edit.min} inputmode="decimal" placeholder="ingen" /></label>
      <label>Max (teknisk enhed)<input bind:value={edit.max} inputmode="decimal" placeholder="ingen" /></label>
      <label class="row" style="flex-direction: row"><input type="checkbox" bind:checked={edit.confirm_write} /> Kræv bekræftelse ved skrivning</label>
    </div>
    <h3 style="margin-top: .8rem">Historik (trends)</h3>
    <div class="grid-form">
      <label class="row" style="flex-direction: row"><input type="checkbox" bind:checked={edit.trend} /> Gem historik</label>
      <label>Højst én værdi pr. (s)<input bind:value={edit.trend_interval_s} inputmode="decimal" /></label>
    </div>
    <p class="muted small">Værdien gemmes når den ændrer sig (til/fra-skift altid med det samme), plus hvert 5. minut. Kortere interval = mere præcis graf, men mere data.</p>
    <div class="grid-form">
      <label>Energi (til energirapporten)
        <select bind:value={edit.energy}>
          <option value="">Nej</option>
          <option value="counter">Tæller (fx kWh-måler)</option>
          <option value="power">Effekt (fx W eller kW)</option>
        </select>
      </label>
      {#if edit.energy}
        <label>Omregning til kWh
          <input bind:value={edit.energy_factor} inputmode="decimal" title="Gang tagets værdi med dette for at få kWh (tæller) eller kW (effekt)" />
        </label>
      {/if}
    </div>
    {#if edit.energy}
      <p class="muted small">
        {edit.energy === 'counter' ? 'Tæller i kWh → 1; i Wh → 0,001. Falder tælleren (nulstilling), regnes den nye værdi som stigning fra 0.'
          : 'Effekt i kW → 1; i W → 0,001. Effekten integreres over tiden; huller (ingen forbindelse) tæller som 0.'}
        Kræver at historik er slået til. Energi-tags gemmes længere end anden historik.
      </p>
    {/if}
    <h3 style="margin-top: .8rem">Alarmer</h3>
    <p class="muted small">Tal-tags: grænser i teknisk enhed (tomt = ingen). Til/fra-tags: alarm når værdien er sand eller falsk.</p>
    <div class="grid-form">
      <label>HH (høj-høj)<input bind:value={edit.alarm_hh} inputmode="decimal" placeholder="ingen" /></label>
      <label>H (høj)<input bind:value={edit.alarm_h} inputmode="decimal" placeholder="ingen" /></label>
      <label>L (lav)<input bind:value={edit.alarm_l} inputmode="decimal" placeholder="ingen" /></label>
      <label>LL (lav-lav)<input bind:value={edit.alarm_ll} inputmode="decimal" placeholder="ingen" /></label>
      <label>Dødbånd<input bind:value={edit.alarm_deadband} inputmode="decimal" /></label>
      <label>Forsinkelse (s)<input bind:value={edit.alarm_delay_s} inputmode="decimal" /></label>
      <label>Til/fra-alarm
        <select bind:value={edit.alarm_on}>
          <option value="">Ingen</option><option value="true">Når sand</option><option value="false">Når falsk</option>
        </select>
      </label>
    </div>
    <div class="row edit-actions">
      <button class="primary" onclick={saveEdit}>Gem</button>
      <button onclick={() => (edit = null)}>Annullér</button>
      {#if editError}<span class="error edit-error">{editError}</span>{/if}
    </div>
  </section>
{/if}

<section class="panel">
  <h2>Tags ({tags.length})</h2>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Navn</th><th>Kilde</th><th>Værdi</th><th>Kvalitet</th><th>Beskrivelse</th><th></th></tr></thead>
      <tbody>
        {#each tags as t}
          {@const v = values[t.name]}
          <tr class:editing={edit?.name === t.name}>
            <td class="mono">{t.name}{#if t.writable} <span class="badge" title="Kan skrives fra Overview">skrivbar</span>{/if}</td>
            <td class="mono">{t.source}{#if sourceKind(t.source) !== 'intern'} <span class="badge" title="Hentes via PLC'ens /api/ext">{SOURCE_LABEL[sourceKind(t.source)]}</span>{/if}</td>
            <td>{formatValue(v?.value, { unit: t.unit, decimals: t.decimals, description: '', plc: t.plc })}</td>
            <td><span class="badge {v?.quality ?? 'unknown'}" title={v?.error ?? ''}>{v?.quality ?? 'unknown'}</span></td>
            <td class="small">{t.description}{v?.error ? ` — ${v.error}` : ''}</td>
            <td>{#if canEdit}<div class="row"><button onclick={() => startEdit(t)}>Redigér</button><button class="danger" onclick={() => remove(t)}>Slet</button></div>{/if}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</section>

<style>
  .edit-panel {
    position: sticky;
    top: .5rem;
    z-index: 5;
    max-height: 60vh;
    overflow-y: auto;
    box-shadow: 0 6px 18px rgba(0, 0, 0, .18);
    padding-bottom: 0;
  }
  /* Gem/Annullér altid synlige i bunden af panelet, også når formularen scrolles */
  .edit-actions {
    position: sticky;
    bottom: 0;
    background-color: var(--panel, #eee);
    padding: .6rem 0;
    margin-top: .6rem;
    border-top: 1px solid var(--line);
    align-items: center;
  }
  .edit-error { margin: 0; flex: 1; min-width: 12rem; }
  tr.editing td { background: #e3edf8; }
</style>
