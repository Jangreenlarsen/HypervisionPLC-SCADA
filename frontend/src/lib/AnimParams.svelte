<script lang="ts">
  // Parametrene for én animation (farver, grænser, tekster, drej/flyt, løbelys …) — bruges af Symbol-guiden og af gruppernes
  // animationer (v0.131.0). Ændrer `a.params` direkte (a er en $state-proxy hos den der bruger komponenten).
  // v6.13.4 (Jan: "gøre animations del mere pæn"): hver indstilling har sin egen række — etiket til venstre, felt til højre (.frows).
  import { textFor } from './animate';
  import { expressionError } from './expression';
  import TagSelect from './TagSelect.svelte';
  import type { TagMeta } from './api';
  import { BLINK_TXT, GLIDE_SPEEDS, glideSeconds, isLogicRef, type Anim, type LogicBlock, type PoolBlock, type SrcKind } from './symbolConfig';

  let { a, kind, positions = [], logic = [], pool = [], tags, valueOf, metaOf, palette = [] }: {
    a: Anim; kind: SrcKind;
    /** Brugte farver (#rrggbb) som hurtigvalg ved farvefelterne: animationernes egne, symbolets tegnede, tegningens */
    palette?: string[];
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

{#snippet swatches(obj: Record<string, any>, key: string | number)}
  {#each palette as c (c)}
    <button type="button" class="sw" class:cur={String(obj[key] ?? '').toLowerCase() === c} style:background={c} title={`Brug ${c}`} aria-label={`Brug farven ${c}`}
      onclick={() => (obj[key] = c)}></button>
  {/each}
{/snippet}

{#snippet colorCell(obj: Record<string, any>, key: string | number, label: string)}
  <span class="colorfield"><input type="color" bind:value={obj[key]} aria-label={label} />{@render swatches(obj, key)}</span>
{/snippet}

{#snippet numCell(obj: Record<string, any>, key: string | number, label: string, unit = '')}
  <input class="n" value={obj[key] ?? ''} aria-label={label} onchange={(e) => (obj[key] = num(e.currentTarget.value, obj[key] ?? 0))} />{#if unit}<span class="small muted">{unit}</span>{/if}
{/snippet}

<div class="params frows">
  {#if (a.type === 'fill' || a.type === 'stroke')}
    {#if kind === 'pos'}
      {#each positions as pos, j}<span class="fl">{pos.label}</span><span class="fc">{@render colorCell(p.colors, j, `Farve, ${pos.label}`)}</span>{/each}
    {:else if kind === 'num'}
      <!-- v6.8.1 (Jan: "rodebutik"): én række pr. værdiområde — fra-farven, aktiv-farven og de ekstra grænser — i stigende orden.
           Aktiv-grænsen (v6.3.0) står i aktiv-rækken: tom = aktiv, når værdien ikke er 0. -->
      <span class="fl">Farve pr. værdi</span>
      <span class="fc">
        <span class="bands small">
          <span class="bh">Værdi</span><span class="bh">Farve</span><span></span>
          <span class="bv">{p.at_least != null ? `under ${p.at_least}` : '0'}</span>
          <span class="bc"><input type="color" bind:value={p.off} aria-label="Farve, når den ikke er aktiv" />{@render swatches(p, 'off')}</span>
          <span class="muted">ikke aktiv</span>
          <span class="bv"><label class="opt" title="Fra hvilken værdi animationen er aktiv. Tomt: aktiv, når værdien ikke er 0">≥
            <input class="n" value={p.at_least ?? ''} placeholder="≠ 0" aria-label="Aktiv når værdien er mindst"
              onchange={(e) => { const v = e.currentTarget.value.trim(); p.at_least = v === '' ? null : num(v, p.at_least ?? 0); }} /></label></span>
          <span class="bc"><input type="color" bind:value={p.on} aria-label="Farve, når den er aktiv" />{@render swatches(p, 'on')}</span>
          <span class="muted">aktiv</span>
          {#each p.thresholds ?? [] as th, ti}
            <span class="bv">≥ <input class="n" value={th.value} aria-label="Grænse {ti + 1}" onchange={(e) => (th.value = num(e.currentTarget.value, th.value))} /></span>
            <span class="bc"><input type="color" bind:value={th.color} aria-label="Farve ved grænse {ti + 1}" />{@render swatches(th, 'color')}</span>
            <span><button class="small" onclick={() => p.thresholds.splice(ti, 1)} aria-label="Fjern grænse">✕</button></span>
          {/each}
        </span>
        <button class="small" onclick={() => (p.thresholds = [...(p.thresholds ?? []), { value: Math.max(0, ...(p.thresholds ?? []).map((t: { value: number }) => t.value + 10), Number(p.at_least ?? 0) + 10), color: '#b26a00' }])}>+ Grænse</button>
      </span>
    {:else}
      <span class="fl">{kind === 'bool' ? 'Til' : 'Over 0'}</span><span class="fc">{@render colorCell(p, 'on', kind === 'bool' ? 'Farve, Til' : 'Farve, over 0')}</span>
      <span class="fl">{kind === 'bool' ? 'Fra' : '0'}</span><span class="fc">{@render colorCell(p, 'off', kind === 'bool' ? 'Farve, Fra' : 'Farve, 0')}</span>
    {/if}
  {:else if a.type === 'blink' || a.type === 'visible' || a.type === 'spin' || a.type === 'flicker'}
    {#if a.type === 'flicker' && Array.isArray(p.palette)}
      {#each [0, 1, 2] as i}<span class="fl">Farve {i + 1}</span><span class="fc">{@render colorCell(p.palette, i, `Flammefarve ${i + 1}`)}</span>{/each}
    {/if}
    {#if kind === 'pos'}
      <span class="fl">Aktiv i</span><span class="fc">{#each positions as pos, j}<label class="opt small"><input type="checkbox" bind:checked={p.set[j]} /> {pos.label}</label>{/each}</span>
    {:else if kind === 'num'}
      <span class="fl">Aktiv når ≥</span><span class="fc">{@render numCell(p, 'at_least', 'Aktiv når værdien er mindst')}</span>
    {:else}
      <span class="fl">Omvendt</span><span class="fc"><label class="opt small"><input type="checkbox" bind:checked={p.invert} /> Aktiv, når tagget er Fra</label></span>
    {/if}
    {#if a.type === 'blink'}
      <span class="fl">Hastighed</span>
      <span class="fc"><select bind:value={p.speed} aria-label="Blinkfrekvens">{#each Object.entries(BLINK_TXT) as [v, t]}<option value={v}>{t}</option>{/each}</select></span>
    {/if}
  {:else if a.type === 'level' || a.type === 'opacity' || a.type === 'scale'}
    <span class="fl">Min</span><span class="fc">{@render numCell(p, 'min', 'Min')}</span>
    <span class="fl">Max</span><span class="fc">{@render numCell(p, 'max', 'Max')}</span>
    {#if a.type === 'scale'}
      <span class="fl">Størrelse min</span><span class="fc">{@render numCell(p, 'size_min', 'Størrelse ved min', '%')}</span>
      <span class="fl">Størrelse max</span><span class="fc">{@render numCell(p, 'size_max', 'Størrelse ved max', '%')}</span>
    {/if}
    {#if a.type === 'level'}
      <span class="fl">Retning</span>
      <span class="fc"><select bind:value={p.direction} aria-label="Retning"><option value="up">Op</option><option value="down">Ned</option><option value="left">Venstre</option><option value="right">Højre</option></select></span>
    {/if}
  {:else if a.type === 'text'}
    {#if kind === 'pos'}
      <span class="fl">Tekst</span><span class="fc small muted">Viser positionens navn.</span>
    {:else if kind === 'bool'}
      <span class="fl">Tekst ved Til</span><span class="fc"><input class="lbl" bind:value={p.true_text} aria-label="Tekst ved Til" /></span>
      <span class="fl">Tekst ved Fra</span><span class="fc"><input class="lbl" bind:value={p.false_text} aria-label="Tekst ved Fra" /></span>
    {:else}
      <span class="fl">Decimaler</span><span class="fc">{@render numCell(p, 'decimals', 'Decimaler')}</span>
      <span class="fl">Før</span><span class="fc"><input class="lbl" bind:value={p.prefix} aria-label="Tekst før værdien" /></span>
      <span class="fl">Efter</span><span class="fc"><input class="lbl" bind:value={p.suffix} aria-label="Tekst efter værdien" /></span>
      <!-- v6.12.7: tekst pr. værdi (højst 5) — fx 0 = Stop, 1 = Kører; andre værdier vises som tal -->
      <span class="fl" title="Er tagets værdi præcis en af disse (før en beregning), vises teksten i stedet for tallet. Andre værdier vises som tal">Tekst pr. værdi</span>
      <span class="fc vtlist">
        {#each p.texts ?? [] as t, k (k)}
          <span class="vt"><input class="n" value={t.value} aria-label="Værdi {k + 1}" onchange={(e) => (t.value = num(e.currentTarget.value, t.value))} />
            <span class="muted">=</span> <input class="lbl wide" bind:value={t.text} maxlength="40" aria-label="Tekst {k + 1}" placeholder="fx Kører" />
            <button type="button" class="small" onclick={() => (p.texts = (p.texts ?? []).filter((_: unknown, j: number) => j !== k))} aria-label="Fjern tekst {k + 1}">✕</button></span>
        {/each}
        {#if (p.texts ?? []).length < 5}
          <span><button type="button" class="small" onclick={() => { const l = p.texts ?? []; p.texts = [...l, { value: l.length ? Math.max(...l.map((x: { value: number }) => Number(x.value) || 0)) + 1 : 0, text: '' }]; }}>+ Tekst</button></span>
        {/if}
      </span>
      <!-- som på siden Bindinger (v0.73.0): beregning på værdien før visning, og tagets enhed efter tallet -->
      <span class="fl">Beregning</span><span class="fc"><input class="lbl wide" bind:value={p.expression} maxlength="80" placeholder="fx x / 10" aria-label="Beregning" /></span>
      <span class="fl">Enhed</span><span class="fc"><label class="opt small"><input type="checkbox" checked={p.show_unit !== false} onchange={(e) => (p.show_unit = e.currentTarget.checked)} /> Vis tagets enhed</label></span>
      {#if expressionError(p.expression ?? '')}<span class="fl"></span><span class="fc small error">Beregning: {expressionError(p.expression ?? '')}</span>{/if}
      {#if valueOf(a.src) !== undefined && valueOf(a.src) !== null}<span class="fl">Lige nu</span><span class="fc small muted">{fmt(valueOf(a.src))} → <strong>{textFor(valueOf(a.src), metaOf(a.src), p)}</strong></span>{/if}
    {/if}
  {:else if a.type === 'segments'}
    <span class="fl">Decimaler</span><span class="fc">{@render numCell(p, 'decimals', 'Decimaler')}</span>
    <span class="fl">Beregning</span><span class="fc"><input class="lbl wide" bind:value={p.expression} maxlength="80" placeholder="fx x / 10" aria-label="Beregning" /></span>
    <span class="fl">Justering</span><span class="fc"><select bind:value={p.align} aria-label="Justering"><option value="right">Højre</option><option value="left">Venstre</option></select></span>
    <span class="fl">Nuller</span><span class="fc"><label class="opt small" title="Fylder op med nuller foran tallet (fx 0042)"><input type="checkbox" bind:checked={p.zeros} /> Foranstillede nuller</label></span>
    <span class="fl">Tændt</span><span class="fc">{@render colorCell(p, 'on', 'Farve, tændt')}</span>
    <span class="fl">Slukket</span><span class="fc">{@render colorCell(p, 'off', 'Farve, slukket')}</span>
    {#if expressionError(p.expression ?? '')}<span class="fl"></span><span class="fc small error">Beregning: {expressionError(p.expression ?? '')}</span>{/if}
    {#if valueOf(a.src) !== undefined && valueOf(a.src) !== null}<span class="fl">Lige nu</span><span class="fc small muted">{fmt(valueOf(a.src))}</span>{/if}
  {:else if a.type === 'rotate'}
    {#if kind === 'pos'}
      {#each positions as pos, j}<span class="fl">{pos.label}</span><span class="fc">{@render numCell(p.angles, j, `Vinkel, ${pos.label}`, '°')}</span>{/each}
    {:else}
      <span class="fl">Min</span><span class="fc">{@render numCell(p, 'min', 'Min')}</span>
      <span class="fl">Max</span><span class="fc">{@render numCell(p, 'max', 'Max')}</span>
      <span class="fl">Vinkel min</span><span class="fc">{@render numCell(p, 'angle_min', 'Vinkel ved min', '°')}</span>
      <span class="fl">Vinkel max</span><span class="fc">{@render numCell(p, 'angle_max', 'Vinkel ved max', '°')}</span>
    {/if}
    <span class="fl" title="Hvor hurtigt delen drejer til den nye vinkel (glidende kræver, at delen ikke selv er drejet/flyttet i tegningen)">Hastighed</span>
    <span class="fc"><select value={String(glideSeconds(p.glide_s, kind === 'pos'))} onchange={(e) => (p.glide_s = Number(e.currentTarget.value))} aria-label="Hastighed">
      {#each GLIDE_SPEEDS as g (g.s)}<option value={String(g.s)}>{g.label}</option>{/each}
    </select></span>
  {:else if a.type === 'move'}
    {#if kind === 'pos'}
      {#each positions as pos, j}<span class="fl">{pos.label}</span><span class="fc"><span class="small muted">x</span>{@render numCell(p.dxs, j, `x, ${pos.label}`)}<span class="small muted">y</span>{@render numCell(p.dys, j, `y, ${pos.label}`)}</span>{/each}
    {:else}
      <span class="fl">Min</span><span class="fc">{@render numCell(p, 'min', 'Min')}</span>
      <span class="fl">Max</span><span class="fc">{@render numCell(p, 'max', 'Max')}</span>
      <span class="fl">Flyt x (max)</span><span class="fc">{@render numCell(p, 'dx', 'x ved max')}</span>
      <span class="fl">Flyt y (max)</span><span class="fc">{@render numCell(p, 'dy', 'y ved max')}</span>
    {/if}
  {:else if a.type === 'flow'}
    {#if kind === 'pos'}
      {#each positions as pos, j}
        <span class="fl">{pos.label}</span><span class="fc"><select bind:value={p.dirs[j]} aria-label="Løbelys, {pos.label}"><option value={0}>stop</option><option value={1}>frem</option><option value={-1}>tilbage</option></select></span>
      {/each}
    {:else}
      <span class="fl">Styring</span>
      <span class="fc"><select bind:value={p.mode} aria-label="Styring"><option value="onoff">Til/fra</option><option value="signed">Fortegn (+/−)</option><option value="code">Kode 0/1/2</option></select></span>
      <span class="fl">Retning fra</span>
      <span class="fc">
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
      </span>
    {/if}
    <span class="fl">Retning</span><span class="fc"><label class="opt small"><input type="checkbox" bind:checked={p.reverse} /> Omvendt</label></span>
    <span class="fl">Rør</span><span class="fc">{@render colorCell(p, 'base', 'Rørets farve')}</span>
    <span class="fl">Lys</span><span class="fc">{@render colorCell(p, 'light', 'Lysets farve')}</span>
    <span class="fl">Fart</span><span class="fc">{@render numCell(p, 'speed', 'Fart')}</span>
    <span class="fl">Streg</span><span class="fc">{@render numCell(p, 'dash', 'Stregens længde')}</span>
  {/if}
</div>

<style>
  .params { margin-top: .3rem; }
  .opt { display: inline-flex; align-items: center; gap: .3rem; }
  .n { width: 5.5em; }
  .lbl { width: 7em; }
  .lbl.wide { width: 14em; max-width: 100%; }
  .colorfield { display: inline-flex; align-items: center; flex-wrap: wrap; gap: .15rem; }
  .sw { width: 1rem; height: 1rem; padding: 0; margin: 0 0 0 .1rem; border: 1px solid var(--line); border-radius: 3px; cursor: pointer; }
  .sw.cur { outline: 2px solid var(--accent); outline-offset: 1px; }
  .params :global(select) { width: auto; max-width: 24em; }
  .bands { display: grid; grid-template-columns: auto auto 1fr; gap: .25rem .6rem; align-items: center; flex-basis: 100%; }
  .bh { font-size: .72rem; text-transform: uppercase; letter-spacing: .04em; color: var(--muted, #666); }
  .bv { display: inline-flex; align-items: center; gap: .3rem; white-space: nowrap; }
  .bc { display: inline-flex; align-items: center; gap: .15rem; flex-wrap: wrap; }
  .params .fc.vtlist { flex-direction: column; align-items: flex-start; }
  .vt { display: inline-flex; align-items: center; gap: .3rem; font-size: .85rem; }
  .vt input.n { width: 3.5rem; }
</style>
