<script lang="ts">
  import { SOURCE_LABEL, sourceKind } from './tagSource';
  // Fælles tag-dropdown (binding-editor og tegne-editor): grupperet pr. PLC med kilde og enhed.
  export interface TagOption { name: string; source: string; unit: string; writable: boolean; plc: string }

  let {
    value = $bindable(''),
    tags,
    writableOnly = false,
    placeholder = '— vælg tag —',
    onchange,
  }: {
    value?: string;
    tags: TagOption[];
    writableOnly?: boolean;
    placeholder?: string;
    onchange?: (value: string) => void;
  } = $props();

  const groups = $derived.by(() => {
    const map = new Map<string, TagOption[]>();
    for (const t of tags) map.set(t.plc, [...(map.get(t.plc) ?? []), t]);
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b));
  });
  const known = $derived(new Set(tags.map((t) => t.name)));
  const detail = (t: TagOption) =>
    `${t.name} · ${t.source}${sourceKind(t.source) !== 'intern' ? ` (${SOURCE_LABEL[sourceKind(t.source)]})` : ''}${t.unit ? ` [${t.unit}]` : ''}`;
  // Det valgte tag vises med sit fulde navn i det lukkede felt (kilde og enhed står i tooltip) — ellers skærer et smalt felt
  // navnet over, fordi teksten "navn · kilde (type) [enhed]" er lang (v1.6.1)
  const current = $derived(tags.find((t) => t.name === value));
</script>

<select bind:value onchange={() => onchange?.(value)} title={current ? detail(current) : value || placeholder}>
  <option value="">{placeholder}</option>
  {#if value && !known.has(value)}<option value={value}>{value} (findes ikke)</option>{/if}
  {#each groups as [plc, rows]}
    <optgroup label={plc}>
      {#each rows as t}
        <option value={t.name} class:tag-writable={t.writable} disabled={writableOnly && !t.writable && t.name !== value}>
          {t.name === value ? t.name : detail(t)}{writableOnly && !t.writable ? ' (ikke skrivbar)' : ''}
        </option>
      {/each}
    </optgroup>
  {/each}
</select>
