<script lang="ts">
  // Parameter-editor til én testanimation (Symboltest): felterne følger typen og tagget, og ændringerne virker med det samme.
  import ColorField from './ColorField.svelte';
  import { addThreshold, paramFields, removeThreshold, setItem, setParam, setThreshold, type Field, type SimAnim, type SimTag } from './symbolSim';
  import { FLICKER_PALETTE } from './symbolConfig';

  let { anim, tag, tags, onparams, onpos }: {
    anim: SimAnim; tag: SimTag; tags: SimTag[];
    onparams: (params: Record<string, any>) => void;
    onpos: (posTag: string | undefined) => void;
  } = $props();

  const fields = $derived(paramFields(anim.anim, tag));
  const p = $derived(anim.params);
  const posTags = $derived(tags.filter((t) => t.kind === 'pos'));
  const posTag = $derived(tags.find((t) => t.id === anim.posTag));
  const set = (f: Field, v: unknown) => onparams(setParam(p, f, v));
  const palette = $derived((Array.isArray(p.palette) && p.palette.length ? p.palette : FLICKER_PALETTE) as string[]);
  const label = (_n: number, j: number) => (tag.labels[j] ? `${j}: ${tag.labels[j]}` : String(j));
</script>

<div class="params">
  {#each fields as f (f.key)}
    <div class="field">
      <span class="lbl">{f.label}</span>
      {#if f.type === 'number'}
        <input type="number" step={f.step ?? 'any'} value={p[f.key] ?? ''} placeholder={f.optional ? 'standard' : ''} onchange={(e) => set(f, e.currentTarget.value)} />
      {:else if f.type === 'color'}
        <ColorField value={p[f.key] ?? ''} label={f.label} onchange={(c) => set(f, c)} />
      {:else if f.type === 'bool'}
        <input type="checkbox" checked={f.defaultOn ? p[f.key] !== false : Boolean(p[f.key])} onchange={(e) => set(f, e.currentTarget.checked)} />
      {:else if f.type === 'text'}
        <input type="text" value={p[f.key] ?? ''} onchange={(e) => set(f, e.currentTarget.value)} />
      {:else if f.type === 'select'}
        <select value={String(p[f.key] ?? '')} onchange={(e) => set(f, e.currentTarget.value)}>
          {#each f.options as o}<option value={o.v}>{o.label}</option>{/each}
        </select>
      {:else if f.type === 'tag'}
        <select value={String(p[f.key] ?? '')} onchange={(e) => onparams(setParam(p, { ...f, type: 'text', optional: true }, e.currentTarget.value))}>
          <option value="">Ingen</option>
          {#each tags.filter((t) => t.id !== tag.id) as t}<option value={t.name}>{t.name}</option>{/each}
        </select>
      {:else if f.type === 'colors'}
        <div class="list">
          {#each Array.from({ length: f.n }, (_, j) => j) as j}
            <div class="item"><small>{label(f.n, j)}</small><ColorField value={p[f.key]?.[j] ?? ''} label="{f.label} {j}" onchange={(c) => onparams(setItem(p, f.key, j, c, f.n))} /></div>
          {/each}
        </div>
      {:else if f.type === 'numbers'}
        <div class="list">
          {#each Array.from({ length: f.n }, (_, j) => j) as j}
            <label class="item"><small>{label(f.n, j)}</small>
              <input type="number" step={f.step ?? 'any'} value={p[f.key]?.[j] ?? 0} onchange={(e) => onparams(setItem(p, f.key, j, Number(e.currentTarget.value) || 0, f.n))} />
            </label>
          {/each}
        </div>
      {:else if f.type === 'bools'}
        <div class="list">
          {#each Array.from({ length: f.n }, (_, j) => j) as j}
            <label class="item"><small>{label(f.n, j)}</small>
              <input type="checkbox" checked={Boolean(p[f.key]?.[j])} onchange={(e) => onparams(setItem(p, f.key, j, e.currentTarget.checked, f.n))} />
            </label>
          {/each}
        </div>
      {:else if f.type === 'texts'}
        <div class="list">
          {#each Array.from({ length: f.n }, (_, j) => j) as j}
            <label class="item"><small>{label(f.n, j)}</small>
              <input type="text" value={p[f.key]?.[j] ?? ''} onchange={(e) => onparams(setItem(p, f.key, j, e.currentTarget.value, f.n))} />
            </label>
          {/each}
        </div>
      {:else if f.type === 'palette'}
        <div class="list">
          {#each [0, 1, 2] as j}
            <div class="item"><ColorField value={palette[j] ?? ''} label="{f.label} {j + 1}"
              onchange={(c) => onparams({ ...p, palette: [0, 1, 2].map((k) => (k === j ? c : palette[k] ?? FLICKER_PALETTE[k])) })} /></div>
          {/each}
        </div>
      {:else if f.type === 'thresholds'}
        <div class="list">
          {#each p.thresholds ?? [] as t, i}
            <div class="item row">
              <span>fra</span>
              <input type="number" step="any" value={t.value} onchange={(e) => onparams(setThreshold(p, i, { value: Number(e.currentTarget.value) || 0 }))} />
              <ColorField value={t.color} label="Grænse {i + 1}" onchange={(c) => onparams(setThreshold(p, i, { color: c }))} />
              <button type="button" class="small" onclick={() => onparams(removeThreshold(p, i))} aria-label="Fjern grænse {i + 1}">✕</button>
            </div>
          {/each}
          <button type="button" class="small" onclick={() => onparams(addThreshold(p))}>+ Grænse</button>
        </div>
      {/if}
    </div>
  {/each}

  {#if posTags.length}
    <div class="field">
      <span class="lbl">Gælder kun i positioner</span>
      <input type="checkbox" checked={Array.isArray(p.only)} aria-label="Gælder kun i bestemte positioner"
             onchange={(e) => {
               if (!e.currentTarget.checked) { const { only: _o, ...rest } = p; onparams(rest); onpos(undefined); return; }
               const t = posTags[0];
               onpos(t.id);
               onparams({ ...p, only: Array.from({ length: t.count }, () => true) });
             }} />
      {#if Array.isArray(p.only)}
        <select value={anim.posTag ?? ''} onchange={(e) => {
          const t = posTags.find((x) => x.id === e.currentTarget.value);
          onpos(t?.id);
          if (t) onparams({ ...p, only: Array.from({ length: t.count }, (_, j) => p.only[j] ?? true) });
        }}>{#each posTags as t}<option value={t.id}>{t.name}</option>{/each}</select>
        {#if posTag}
          <div class="list">
            {#each Array.from({ length: posTag.count }, (_, j) => j) as j}
              <label class="item"><small>{posTag.labels[j] ? `${j}: ${posTag.labels[j]}` : j}</small>
                <input type="checkbox" checked={Boolean(p.only[j])} onchange={(e) => onparams(setItem(p, 'only', j, e.currentTarget.checked, posTag.count))} />
              </label>
            {/each}
          </div>
        {/if}
      {/if}
    </div>
  {/if}
</div>

<style>
  .params { display: flex; flex-direction: column; gap: 6px; padding: 6px 0 2px; }
  .field { display: grid; grid-template-columns: 11em 1fr; gap: 6px; align-items: start; }
  .lbl { font-size: .85em; color: var(--muted, #666); padding-top: 3px; }
  .list { display: flex; flex-wrap: wrap; gap: 6px 10px; }
  .item { display: inline-flex; flex-direction: column; gap: 2px; }
  .item.row { flex-direction: row; align-items: center; gap: 4px; }
  input[type='number'] { width: 6em; }
  input[type='text'] { width: 9em; }
  @media (max-width: 800px) { .field { grid-template-columns: 1fr; } }
</style>
