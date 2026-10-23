<script lang="ts">
  // Parametrene for én animation (farver, grænser, tekster, drej/flyt, løbelys …) — bruges af Symbol-guiden og af gruppernes
  // animationer (v0.131.0). Ændrer `a.params` direkte (a er en $state-proxy hos den der bruger komponenten).
  import { textFor } from './animate';
  import { expressionError } from './expression';
  import TagSelect from './TagSelect.svelte';
  import type { TagMeta } from './api';
  import { BLINK_TXT, GLIDE_SPEEDS, glideSeconds, isLogicRef, type Anim, type LogicBlock, type PoolBlock, type SrcKind } from './symbolConfig';

  let { a, kind, positions = [], logic = [], pool = [], tags, valueOf, metaOf }: {
    a: Anim; kind: SrcKind;
    positions?: { label: string }[]; logic?: LogicBlock[]; pool?: PoolBlock[];
    tags: { name: string; source: string; unit: string; writable: boolean; plc: string }[];
    valueOf: (tag: string) => unknown; metaOf: (tag: string) => TagMeta | undefined;
  } = $props();

  const p = $derived(a.params);
  const num = (v: string, fallback: number) => (Number.isFinite(Number(v.replace(',', '.'))) && v.trim() !== '' ? Number(v.replace(',', '.')) : fallback);
  const fmt = (v: unknown) => (v === undefined || v === null ? '—' : typeof v === 'boolean' ? (v ? 'Til' : 'Fra') : String(v));
  const blockLabel = (b: LogicBlock) => `${b.id}${b.name ? ` – ${b.name}` : ''}`;
  const poolLabel = (p: PoolBlock) => `${p.symbol} · ${p.id}${p.name ? ` – ${p.name}` : ''}`;
  const poolRef = (p: PoolBlock) => `@${p.element}:${p.id}`;
  const firstBlockRef = (local: LogicBlock[]) => (local[0] ? `@${local[0].id}` : pool[0] ? poolRef(pool[0]) : '');
</script>

{#snippet colorInput(obj: Record<string, any>, key: string | number, label: string)}
  <label class="opt small"><input type="color" bind:value={obj[key]} /> {label}</label>
{/snippet}

{#snippet numInput(obj: Record<string, any>, key: string | number, label: string)}
  <label class="opt small">{label} <input class="n" value={obj[key] ?? ''} onchange={(e) => (obj[key] = num(e.currentTarget.value, obj[key] ?? 0))} /></label>
{/snippet}

  <div class="row wrap params">
    {#if (a.type === 'fill' || a.type === 'stroke')}
      {#if kind === 'pos'}
        {#each positions as pos, j}{@render colorInput(p.colors, j, pos.label)}{/each}
      {:else}
        {@render colorInput(p, 'on', kind === 'bool' ? 'Til' : 'Over 0')}{@render colorInput(p, 'off', kind === 'bool' ? 'Fra' : '0')}
        {#if kind === 'num'}
          {#each p.thresholds ?? [] as th, ti}
            <span class="opt small">≥ <input class="n" value={th.value} onchange={(e) => (th.value = num(e.currentTarget.value, th.value))} />
              <input type="color" bind:value={th.color} /><button class="small" onclick={() => p.thresholds.splice(ti, 1)} aria-label="Fjern grænse">✕</button></span>
          {/each}
          <button class="small" onclick={() => (p.thresholds = [...(p.thresholds ?? []), { value: 0, color: '#b26a00' }])}>+ Grænse</button>
        {/if}
      {/if}
    {:else if a.type === 'blink' || a.type === 'visible' || a.type === 'spin' || a.type === 'flicker'}
      {#if a.type === 'flicker'}
        <span class="small muted">Skifter tilfældigt mellem:</span>
        {#if Array.isArray(p.palette)}{#each [0, 1, 2] as i}{@render colorInput(p.palette, i, `Farve ${i + 1}`)}{/each}{/if}
      {/if}
      {#if kind === 'pos'}
        {#each positions as pos, j}<label class="opt small"><input type="checkbox" bind:checked={p.set[j]} /> {pos.label}</label>{/each}
      {:else if kind === 'num'}
        {@render numInput(p, 'at_least', 'Når ≥')}
      {:else}
        <label class="opt small"><input type="checkbox" bind:checked={p.invert} /> Omvendt (når Fra)</label>
      {/if}
      {#if a.type === 'blink'}
        <select bind:value={p.speed} aria-label="Blinkfrekvens">{#each Object.entries(BLINK_TXT) as [v, t]}<option value={v}>{t}</option>{/each}</select>
      {/if}
    {:else if a.type === 'level' || a.type === 'opacity' || a.type === 'scale'}
      {@render numInput(p, 'min', 'Min')}{@render numInput(p, 'max', 'Max')}
      {#if a.type === 'scale'}
        {@render numInput(p, 'size_min', 'Størrelse ved min (%)')}{@render numInput(p, 'size_max', 'ved max (%)')}
      {/if}
      {#if a.type === 'level'}
        <select bind:value={p.direction} aria-label="Retning"><option value="up">Op</option><option value="down">Ned</option><option value="left">Venstre</option><option value="right">Højre</option></select>
      {/if}
    {:else if a.type === 'text'}
      {#if kind === 'pos'}
        <span class="small muted">Viser positionens navn.</span>
      {:else if kind === 'bool'}
        <label class="opt small">Til <input class="lbl" bind:value={p.true_text} /></label><label class="opt small">Fra <input class="lbl" bind:value={p.false_text} /></label>
      {:else}
        {@render numInput(p, 'decimals', 'Decimaler')}
        <label class="opt small">Før <input class="lbl" bind:value={p.prefix} /></label><label class="opt small">Efter <input class="lbl" bind:value={p.suffix} /></label>
        <!-- som på siden Bindinger (v0.73.0): beregning på værdien før visning, og tagets enhed efter tallet -->
        <label class="opt small">Beregning <input class="lbl" bind:value={p.expression} maxlength="80" placeholder="fx x / 10" /></label>
        <label class="opt small"><input type="checkbox" checked={p.show_unit !== false} onchange={(e) => (p.show_unit = e.currentTarget.checked)} /> Vis enhed</label>
        {#if expressionError(p.expression ?? '')}<span class="small error">Beregning: {expressionError(p.expression ?? '')}</span>{/if}
        {#if valueOf(a.src) !== undefined && valueOf(a.src) !== null}<span class="small muted">Lige nu: {fmt(valueOf(a.src))} → <strong>{textFor(valueOf(a.src), metaOf(a.src), p)}</strong></span>{/if}
      {/if}
    {:else if a.type === 'rotate'}
      {#if kind === 'pos'}
        {#each positions as pos, j}{@render numInput(p.angles, j, `${pos.label} °`)}{/each}
      {:else}
        {@render numInput(p, 'min', 'Min')}{@render numInput(p, 'max', 'Max')}{@render numInput(p, 'angle_min', '° ved min')}{@render numInput(p, 'angle_max', '° ved max')}
      {/if}
      <label class="opt small" title="Hvor hurtigt delen drejer til den nye vinkel (glidende kræver, at delen ikke selv er drejet/flyttet i tegningen)">Hastighed
        <select value={String(glideSeconds(p.glide_s, kind === 'pos'))} onchange={(e) => (p.glide_s = Number(e.currentTarget.value))}>
          {#each GLIDE_SPEEDS as g (g.s)}<option value={String(g.s)}>{g.label}</option>{/each}
        </select></label>
    {:else if a.type === 'move'}
      {#if kind === 'pos'}
        {#each positions as pos, j}<span class="opt small">{pos.label} {@render numInput(p.dxs, j, 'x')}{@render numInput(p.dys, j, 'y')}</span>{/each}
      {:else}
        {@render numInput(p, 'min', 'Min')}{@render numInput(p, 'max', 'Max')}{@render numInput(p, 'dx', 'x ved max')}{@render numInput(p, 'dy', 'y ved max')}
      {/if}
    {:else if a.type === 'flow'}
      {#if kind === 'pos'}
        {#each positions as pos, j}
          <label class="opt small">{pos.label} <select bind:value={p.dirs[j]}><option value={0}>stop</option><option value={1}>frem</option><option value={-1}>tilbage</option></select></label>
        {/each}
      {:else}
        <select bind:value={p.mode} aria-label="Styring"><option value="onoff">Til/fra</option><option value="signed">Fortegn (+/−)</option><option value="code">Kode 0/1/2</option></select>
        <label class="opt small">Retning fra
          {#if logic.length || pool.length}
            <select value={isLogicRef(p.dir_tag ?? '') ? 'logic' : 'tag'} onchange={(e) => (p.dir_tag = e.currentTarget.value === 'logic' ? firstBlockRef(logic) : '')} aria-label="Retningens kilde">
              <option value="tag">et tag</option><option value="logic">en logikblok</option>
            </select>
          {/if}
          {#if isLogicRef(p.dir_tag ?? '')}
            <select bind:value={p.dir_tag} aria-label="Retningens logikblok">
              {#if logic.length}<optgroup label="Dette symbol">{#each logic as b}<option value={'@' + b.id}>{blockLabel(b)}</option>{/each}</optgroup>{/if}
              {#if pool.length}<optgroup label="Andre symboler">{#each pool as q}<option value={poolRef(q)}>{poolLabel(q)}</option>{/each}</optgroup>{/if}
            </select>
          {:else}
            <TagSelect value={p.dir_tag ?? ''} {tags} placeholder="— ingen —" onchange={(v) => (p.dir_tag = v)} />
          {/if}
        </label>
      {/if}
      <label class="opt small"><input type="checkbox" bind:checked={p.reverse} /> Omvendt</label>
      {@render colorInput(p, 'base', 'Rør')}{@render colorInput(p, 'light', 'Lys')}
      {@render numInput(p, 'speed', 'Fart')}{@render numInput(p, 'dash', 'Streg')}
    {/if}
  </div>

<style>
  .params { margin-top: .3rem; }
  .wrap { flex-wrap: wrap; gap: .35rem .6rem; align-items: center; }
  .opt { display: inline-flex; align-items: center; gap: .3rem; }
  .n { width: 5.5em; }
  .lbl { width: 7em; }
  .params :global(select) { width: auto; max-width: 15em; }
</style>
