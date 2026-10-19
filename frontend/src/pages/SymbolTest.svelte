<script lang="ts">
  import { CATEGORIES, SYMBOLS, SYMBOL_COLORS, type SymbolCategory } from '../lib/symbols';
  import { ANIM_TXT, type AnimType, type SrcKind } from '../lib/symbolConfig';
  import type { Binding } from '../lib/api';
  import { MAX_POSITIONS, MIN_POSITIONS, ROOT, animsFor, applyTest, librarySetup, resetTest, runSetup, testBinding, testParts, valueRange } from '../lib/symbolTest';

  let category = $state<SymbolCategory | 'alle'>('alle');
  let search = $state('');
  let selected = $state(SYMBOLS[0].id);
  let background = $state<'lys' | 'moerk' | 'skak'>('lys');
  let zoom = $state(3);
  let part = $state(ROOT);
  let anim = $state<AnimType>('fill');
  let kind = $state<SrcKind>('bool');
  let value = $state(1);
  let count = $state(3);   // antal positioner i den frie afprøvning
  let host = $state<HTMLElement>();
  let error = $state('');
  /** viewBox efter symbolets egen størrelse (getBBox medregner ikke stregen, derfor lidt luft). */
  function fit(svg: SVGSVGElement): void {
    try {
      const b = (svg.firstElementChild as SVGGraphicsElement).getBBox();
      const pad = Math.max(b.width, b.height) * 0.08 + 4, size = Math.max(b.width, b.height) + 2 * pad;
      const cx = b.x + b.width / 2, cy = b.y + b.height / 2;
      svg.setAttribute('viewBox', `${cx - size / 2} ${cy - size / 2} ${size} ${size}`);
    } catch {
      // symbolet er ikke tegnet endnu (fx skjult fane): beholder standardvinduet
    }
  }
  const fitting = (node: SVGSVGElement) => fit(node);
  let applied: Binding[] = [];   // det der er sat på symbolet nu, så Nulstil kan rydde det

  const shown = $derived(SYMBOLS.filter((s) => (category === 'alle' || s.category === category)
    && (!search.trim() || `${s.label} ${s.id}`.toLowerCase().includes(search.trim().toLowerCase()))));
  const def = $derived(SYMBOLS.find((s) => s.id === selected) ?? SYMBOLS[0]);
  const parts = $derived(testParts(def.svg, def.id));
  const current = $derived(parts.find((p) => p.id === part) ?? parts[0]);
  const n = $derived(Math.min(MAX_POSITIONS, Math.max(MIN_POSITIONS, Math.round(Number(count)) || MIN_POSITIONS)));
  const animList = $derived(animsFor(current.types, kind));
  const setup = $derived(librarySetup(def.svg, def.id));
  const range = $derived(kind === 'bool' ? { min: 0, max: 1 } : kind === 'pos' ? { min: 0, max: n - 1 }
    : valueRange(testBinding(part, anim, kind).params));
  const whole = $derived(kind !== 'num');   // til/fra og position: hele tal

  // delen eller kilden er skiftet: vælg en animation der findes for den
  $effect(() => { if (!animList.includes(anim)) anim = animList[0]; });
  $effect(() => { if (value > range.max) value = range.max; });

  function select(id: string): void {
    selected = id;
    part = ROOT;
    value = 1;
    applied = [];
    error = '';
  }

  /** Bibliotekets opsætning afprøves med én værdi (positionens nummer, til/fra eller tal). */
  function runLibrary(v: number): void {
    if (!host || !setup) return;
    const missing = runSetup(host, setup, v);
    error = missing.length ? `Delen "${missing[0]}" findes ikke i symbolet.` : '';
    for (const b of setup.bindings) if (!applied.some((a) => a.element === b.element && a.anim === b.anim)) applied.push(b);
  }

  function run(b: Binding, v: number): void {
    if (!host) return;
    if (!applyTest(host, b.element, b, v)) {
      error = `Delen "${b.element}" findes ikke i symbolet.`;
      return;
    }
    error = '';
    if (!applied.some((a) => a.element === b.element && a.anim === b.anim)) applied.push(b);
  }

  function test(): void {
    run(testBinding(part, anim, kind, n), value);
  }

  /** Symbolets egne animationer (data-hv-part) afprøves med samme værdi. */
  function runOwn(): void {
    for (const p of parts) for (const o of p.own) run({ element: p.id, tag: 'test', anim: o.anim, params: o.params }, value);
  }

  function reset(): void {
    if (host) resetTest(host, applied);
    applied = [];
    value = 1;
  }

  // et nyt symbol tegnes forfra — så ryddes tidligere animationer af sig selv
  $effect(() => {
    if (!host) return;
    host.innerHTML = `<svg viewBox="-10 -10 260 260" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;overflow:visible">${def.svg}</svg>`;
    fit(host.firstElementChild as SVGSVGElement);
  });
</script>

<section class="panel">
  <h2>Symboltest</h2>
  <p class="muted">Afprøv et symbol uden PLC: vælg en del, en animation og en værdi. Intet gemmes.</p>
  <div class="layout">
    <div class="list">
      <div class="row">
        <select bind:value={category} aria-label="Kategori">
          <option value="alle">Alle ({SYMBOLS.length})</option>
          {#each CATEGORIES as c}<option value={c.id}>{c.label}</option>{/each}
        </select>
        <input type="search" placeholder="Søg symbol" bind:value={search} />
      </div>
      <div class="grid">
        {#each shown as s (s.id)}
          <button class="tile" class:on={s.id === selected} onclick={() => select(s.id)} title={s.hint}>
            <svg viewBox="-5 -5 250 250" width="56" height="56" use:fitting>{@html s.svg}</svg>
            <span>{s.label}</span>
          </button>
        {/each}
        {#if !shown.length}<p class="muted">Ingen symboler matcher.</p>{/if}
      </div>
    </div>

    <div class="detail">
      <h3>{def.label} <small class="muted">({def.id})</small></h3>
      <p class="muted">{def.hint}</p>
      <div class="row">
        <label>Baggrund
          <select bind:value={background}><option value="lys">Lys</option><option value="moerk">Mørk</option><option value="skak">Skak</option></select>
        </label>
        <label>Størrelse <input type="range" min="1" max="6" step="0.5" bind:value={zoom} /></label>
      </div>
      <div class="stage bg-{background}" style="width:{zoom * 80}px;height:{zoom * 80}px" bind:this={host}></div>
      {#if error}<div class="error">{error}</div>{/if}

      {#if setup}
        <h4>Som i guiden</h4>
        <p class="muted small">{setup.note}</p>
        <div class="row">
          {#if setup.positions.length}
            {#each setup.positions as label, j}<button onclick={() => runLibrary(j)}>{j}: {label}</button>{/each}
          {:else if setup.kind === 'num'}
            <input type="range" min="0" max="100" value="0" oninput={(e) => runLibrary(Number(e.currentTarget.value))} aria-label="Værdi" />
          {:else}
            <button onclick={() => runLibrary(0)}>Fra</button><button onclick={() => runLibrary(1)}>Til</button>
          {/if}
        </div>
      {/if}

      <h4>Afprøv en animation</h4>
      <div class="row">
        <label>Del
          <select bind:value={part}>{#each parts as p}<option value={p.id}>{p.label}{p.id === ROOT ? '' : ` (${p.id})`}</option>{/each}</select>
        </label>
        <label>Animation
          <select bind:value={anim}>{#each animList as a}<option value={a}>{ANIM_TXT[a]}</option>{/each}</select>
        </label>
        <label>Tag er
          <select bind:value={kind}><option value="bool">Til/fra</option><option value="num">Tal</option><option value="pos">Position</option></select>
        </label>
        {#if kind === 'pos'}
          <label>Positioner <input type="number" min={MIN_POSITIONS} max={MAX_POSITIONS} bind:value={count} style="width:4em" /></label>
        {/if}
      </div>
      <div class="row">
        <button onclick={() => { value = range.min; test(); }}>Fra</button>
        <button onclick={() => { value = range.max; test(); }}>Til</button>
        <input type="range" min={range.min} max={range.max} step={whole ? 1 : (range.max - range.min) / 100} bind:value oninput={test} />
        <output>{value}</output>
      </div>

      {#if parts.some((p) => p.own.length)}
        <h4>Symbolets egne animationer</h4>
        <ul class="small">
          {#each parts.filter((p) => p.own.length) as p}
            <li>{p.label}: {p.own.map((o) => ANIM_TXT[o.anim as AnimType] ?? o.anim).join(', ')}</li>
          {/each}
        </ul>
        <button onclick={runOwn}>Kør med værdien ovenfor</button>
      {/if}
      <div class="row"><button class="danger" onclick={reset}>Nulstil</button></div>

      <h4>Dele</h4>
      <table class="small">
        <thead><tr><th>Navn</th><th>Id</th><th>Figur</th></tr></thead>
        <tbody>{#each parts as p}<tr class:cur={p.id === current.id}><td>{p.label}</td><td>{p.id === ROOT ? '' : p.id}</td><td>{p.tag}</td></tr>{/each}</tbody>
      </table>
      {#if parts.length === 1}<p class="muted">Ingen navngivne dele — kun hele symbolet kan animeres (SYMBOLSTANDARD §8).</p>{/if}

      <h4>Farver</h4>
      <div class="row">
        {#each SYMBOL_COLORS as c}<span class="sw" style="background:{c}" title={c}></span>{/each}
      </div>
    </div>
  </div>
</section>

<style>
  .layout { display: grid; grid-template-columns: minmax(260px, 1fr) minmax(320px, 1.4fr); gap: 16px; }
  @media (max-width: 800px) { .layout { grid-template-columns: 1fr; } }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(84px, 1fr)); gap: 6px; margin-top: 8px; max-height: 70vh; overflow: auto; }
  .tile { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 6px; font-size: 11px; }
  .tile.on { border-color: var(--accent); background: var(--panel-2); }
  .stage { border: 1px solid var(--line); margin: 8px 0; max-width: 100%; }
  .bg-lys { background: #ffffff; }
  .bg-moerk { background: #1f1f1f; }
  .bg-skak { background: repeating-conic-gradient(#d6d6d6 0 25%, #ffffff 0 50%) 0 0 / 16px 16px; }
  .row { display: flex; flex-wrap: wrap; gap: 8px; align-items: end; margin: 6px 0; }
  .sw { width: 18px; height: 18px; border: 1px solid var(--line); display: inline-block; }
  tr.cur td { background: var(--panel-2); }
</style>
