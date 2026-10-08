<script lang="ts">
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
</script>

<select bind:value onchange={() => onchange?.(value)}>
  <option value="">{placeholder}</option>
  {#if value && !known.has(value)}<option value={value}>{value} (findes ikke)</option>{/if}
  {#each groups as [plc, rows]}
    <optgroup label={plc}>
      {#each rows as t}
        <option value={t.name} disabled={writableOnly && !t.writable && t.name !== value}>
          {t.name} · {t.source}{t.unit ? ` [${t.unit}]` : ''}{writableOnly && !t.writable ? ' (ikke skrivbar)' : ''}
        </option>
      {/each}
    </optgroup>
  {/each}
</select>
