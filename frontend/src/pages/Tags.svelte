<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { del, get, post, type LiveValue } from '../lib/api';
  import { formatValue } from '../lib/animate';
  import { LiveClient } from '../lib/live';

  let { canEdit = false }: { canEdit?: boolean } = $props();

  interface Tag {
    name: string; source: string; plc: string; description: string; unit: string;
    scale: number; offset: number; decimals: number | null; writable: boolean;
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
    if (!confirm(`Slet tagget ${t.name}?`)) return;
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
    Kilde: <code>plc1:hr:100</code>, <code>plc1:hr:20:real</code> (uint/int/dint/dword/real), <code>plc1:ir:7</code>,
    <code>plc1:coil:5</code>, <code>plc1:di:3</code>, <code>plc1:logic:1:Variabel</code>, <code>plc1:global:Variabel</code>.
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

<section class="panel">
  <h2>Tags ({tags.length})</h2>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Navn</th><th>Kilde</th><th>Værdi</th><th>Kvalitet</th><th>Beskrivelse</th><th></th></tr></thead>
      <tbody>
        {#each tags as t}
          {@const v = values[t.name]}
          <tr>
            <td class="mono">{t.name}</td>
            <td class="mono">{t.source}</td>
            <td>{formatValue(v?.value, { unit: t.unit, decimals: t.decimals, description: '', plc: t.plc })}</td>
            <td><span class="badge {v?.quality ?? 'unknown'}" title={v?.error ?? ''}>{v?.quality ?? 'unknown'}</span></td>
            <td class="small">{t.description}{v?.error ? ` — ${v.error}` : ''}</td>
            <td>{#if canEdit}<button class="danger" onclick={() => remove(t)}>Slet</button>{/if}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</section>
