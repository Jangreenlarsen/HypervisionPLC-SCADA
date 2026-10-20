<script lang="ts">
  import { untrack } from 'svelte';
  import { CATEGORIES, SYMBOLS, SYMBOL_COLORS, type SymbolCategory } from '../lib/symbols';
  import { ANIM_TXT, type AnimType, type SrcKind } from '../lib/symbolConfig';
  import { ROOT, librarySetup, testParts } from '../lib/symbolTest';
  import {
    MAX_ANIMS, MAX_TAGS, applyAlarmMarks, clampCount, clampValue, defaultParams, fromOwn, fromSetup, newAnim, newTag, retune, syncSim,
    tagRange, type Applied, type SimAnim, type SimTag,
  } from '../lib/symbolSim';
  import SimParams from '../lib/SimParams.svelte';

  let category = $state<SymbolCategory | 'alle'>('alle');
  let search = $state('');
  let selected = $state(SYMBOLS[0].id);
  let background = $state<'lys' | 'moerk' | 'skak'>('lys');
  let zoom = $state(3);
  let host = $state<HTMLElement>();
  let tags = $state<SimTag[]>([]);
  let anims = $state<SimAnim[]>([]);
  let picked = $state('');   // farve valgt i paletten nederst
  let copied = $state('');
  let missing = $state<string[]>([]);
  const applied = new Map<string, Applied>();
  let renderToken = $state<object>({});   // symbolet er tegnet forfra → animationerne skal anvendes igen

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

  const shown = $derived(SYMBOLS.filter((s) => (category === 'alle' || s.category === category)
    && (!search.trim() || `${s.label} ${s.id}`.toLowerCase().includes(search.trim().toLowerCase()))));
  const def = $derived(SYMBOLS.find((s) => s.id === selected) ?? SYMBOLS[0]);
  const parts = $derived(testParts(def.svg, def.id));
  const setup = $derived(librarySetup(def.svg, def.id));
  const ownCount = $derived(parts.reduce((n, p) => n + p.own.length, 0));
  const tagOf = (id: string): SimTag => tags.find((t) => t.id === id) ?? tags[0];

  /** Et nyt symbol: bibliotekets opsætning hvis den findes, ellers ét til/fra-tag med en farveanimation på hele symbolet. */
  function initial(symbolId: string): { tags: SimTag[]; anims: SimAnim[] } {
    const s = SYMBOLS.find((x) => x.id === symbolId) ?? SYMBOLS[0];
    const su = librarySetup(s.svg, s.id);
    if (su) return fromSetup(su);
    const t = newTag([], 'bool');
    return { tags: [t], anims: [newAnim(t, ROOT, 'fill')] };
  }

  function select(id: string): void {
    selected = id;
    applied.clear();   // delene tegnes forfra
    const l = initial(id);
    tags = l.tags;
    anims = l.anims;
  }

  // ---- tags
  function addTag(kind: SrcKind = 'bool'): void {
    if (tags.length >= MAX_TAGS) return;
    tags.push(newTag(tags, kind));
  }
  function removeTag(id: string): void {
    anims = anims.filter((a) => a.tag !== id);
    tags = tags.filter((t) => t.id !== id);
    if (!tags.length) addTag();
  }
  /** Art eller antal positioner ændret: værdien holdes inden for tagget, og animationerne får nye standardparametre. */
  function retag(t: SimTag): void {
    t.count = clampCount(t.count);
    t.value = clampValue(t);
    retune(anims, t);
  }
  const setValue = (t: SimTag, v: number) => { t.value = v; };

  // ---- animationer
  function addAnim(): void {
    if (anims.length >= MAX_ANIMS) return;
    anims.push(newAnim(tags[0], ROOT, 'fill'));
  }
  function setPart(a: SimAnim, part: string): void {
    a.part = part;
    const types = parts.find((p) => p.id === part)?.types ?? [];
    if (!types.includes(a.anim) && types.length) setType(a, types[0]);
  }
  function setType(a: SimAnim, type: AnimType): void {
    a.anim = type;
    a.params = defaultParams(type, tagOf(a.tag));
    a.posTag = undefined;
  }
  function setTag(a: SimAnim, id: string): void {
    a.tag = id;
    a.params = defaultParams(a.anim, tagOf(id));
    a.posTag = undefined;
  }
  function loadSetup(): void {
    if (!setup) return;
    const l = fromSetup(setup);
    tags = l.tags;
    anims = l.anims;
  }
  function loadOwn(): void {
    const l = fromOwn(parts);
    tags = l.tags;
    anims = l.anims;
  }
  function reset(): void {
    anims = [];
    for (const t of tags) { t.value = t.kind === 'bool' ? 1 : 0; t.missing = false; t.quality = 'good'; t.alarm = ''; }
  }

  async function copy(c: string): Promise<void> {
    picked = c;
    try {
      await navigator.clipboard.writeText(c);
      copied = c;
    } catch {
      copied = '';   // udklipsholderen er ikke tilgængelig (fx http): farven vises stadig og kan skrives af
    }
  }

  // ---- tegning og anvendelse
  { const l = initial(SYMBOLS[0].id); tags = l.tags; anims = l.anims; }
  $effect(() => {
    if (!host) return;
    host.innerHTML = `<svg viewBox="-10 -10 260 260" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;overflow:visible">${def.svg}</svg>`;
    fit(host.firstElementChild as SVGSVGElement);
    applied.clear();
    renderToken = {};
  });
  $effect(() => {
    void renderToken;
    const a = $state.snapshot(anims), t = $state.snapshot(tags);
    const svg = host?.firstElementChild;   // symbolets omslag: "Hele symbolet" er dets første barn, som i en tegning
    if (!svg) return;
    untrack(() => {
      missing = syncSim(svg, a, t, applied);
      applyAlarmMarks(svg, a, t);
    });
  });
</script>

<section class="panel">
  <h2>Symboltest</h2>
  <p class="muted">Afprøv et symbol uden PLC: simulér tags, læg animationer på delene og ret deres indstillinger. Intet gemmes.</p>
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
      {#if missing.length}<div class="error">Delen "{missing[0]}" findes ikke i symbolet.</div>{/if}

      <h4>Tags <small class="muted">(simulerede værdier)</small></h4>
      {#each tags as t (t.id)}
        <div class="card">
          <div class="row">
            <input class="name" bind:value={t.name} aria-label="Navn på tag" />
            <label>Art
              <select bind:value={t.kind} onchange={() => retag(t)}>
                <option value="bool">Til/fra</option><option value="num">Tal</option><option value="pos">Position</option>
              </select>
            </label>
            {#if t.kind === 'pos'}
              <label>Positioner <input type="number" min="2" max="8" bind:value={t.count} onchange={() => retag(t)} style="width:4em" /></label>
            {:else if t.kind === 'num'}
              <label>Fra <input type="number" bind:value={t.min} onchange={() => retag(t)} style="width:5em" /></label>
              <label>Til <input type="number" bind:value={t.max} onchange={() => retag(t)} style="width:5em" /></label>
              <label>Enhed <input bind:value={t.unit} style="width:4em" /></label>
            {/if}
            <button class="small" onclick={() => removeTag(t.id)} aria-label="Fjern tag {t.name}">Fjern</button>
          </div>
          <div class="row">
            {#if t.kind === 'bool'}
              <button class:primary={t.value === 0} onclick={() => setValue(t, 0)}>Fra</button>
              <button class:primary={t.value === 1} onclick={() => setValue(t, 1)}>Til</button>
            {:else if t.kind === 'pos'}
              {#each Array.from({ length: clampCount(t.count) }, (_, j) => j) as j}
                <button class:primary={t.value === j} onclick={() => setValue(t, j)}>{t.labels[j] ? `${j}: ${t.labels[j]}` : j}</button>
              {/each}
            {:else}
              <input type="range" min={tagRange(t).min} max={tagRange(t).max} step={(tagRange(t).max - tagRange(t).min) / 100} bind:value={t.value} aria-label="Værdi for {t.name}" />
              <input type="number" bind:value={t.value} style="width:6em" aria-label="Værdi for {t.name}" />
            {/if}
          </div>
        </div>
      {/each}
      <div class="row">
        <button onclick={() => addTag('bool')} disabled={tags.length >= MAX_TAGS}>+ Til/fra</button>
        <button onclick={() => addTag('num')} disabled={tags.length >= MAX_TAGS}>+ Tal</button>
        <button onclick={() => addTag('pos')} disabled={tags.length >= MAX_TAGS}>+ Position</button>
      </div>

      <h4>Animationer</h4>
      {#each anims as a (a.id)}
        {@const tag = tagOf(a.tag)}
        {@const types = parts.find((p) => p.id === a.part)?.types ?? []}
        <details class="card" open>
          <summary>
            {parts.find((p) => p.id === a.part)?.label ?? a.part} — {ANIM_TXT[a.anim]} — {tag.name}
          </summary>
          <div class="row">
            <label>Del
              <select value={a.part} onchange={(e) => setPart(a, e.currentTarget.value)}>
                {#each parts as p}<option value={p.id}>{p.label}{p.id === ROOT ? '' : ` (${p.id})`}</option>{/each}
              </select>
            </label>
            <label>Animation
              <select value={a.anim} onchange={(e) => setType(a, e.currentTarget.value as AnimType)}>
                {#each types as ty}<option value={ty}>{ANIM_TXT[ty]}</option>{/each}
              </select>
            </label>
            <label>Følger
              <select value={a.tag} onchange={(e) => setTag(a, e.currentTarget.value)}>
                {#each tags as t}<option value={t.id}>{t.name}</option>{/each}
              </select>
            </label>
            <button class="small" onclick={() => (anims = anims.filter((x) => x.id !== a.id))} aria-label="Fjern animation">Fjern</button>
          </div>
          <SimParams anim={a} {tag} {tags}
            onparams={(params) => { a.params = params; }}
            onpos={(id) => { a.posTag = id; }} />
        </details>
      {/each}
      {#if !anims.length}<p class="muted small">Ingen animationer endnu — tilføj en, eller hent symbolets opsætning.</p>{/if}
      <div class="row">
        <button class="primary" onclick={addAnim} disabled={anims.length >= MAX_ANIMS}>+ Tilføj animation</button>
        {#if setup}<button onclick={loadSetup} title="Som guiden foreslår den">Hent bibliotekets opsætning</button>{/if}
        {#if ownCount}<button onclick={loadOwn} title="data-hv-part i symbolet">Hent symbolets egne ({ownCount})</button>{/if}
        <button class="danger" onclick={reset}>Nulstil</button>
      </div>
      {#if setup}<p class="muted small">{setup.note}</p>{/if}

      <h4>Dele</h4>
      <table class="small">
        <thead><tr><th>Navn</th><th>Id</th><th>Figur</th></tr></thead>
        <tbody>{#each parts as p}<tr><td>{p.label}</td><td>{p.id === ROOT ? '' : p.id}</td><td>{p.tag}</td></tr>{/each}</tbody>
      </table>
      {#if parts.length === 1}<p class="muted">Ingen navngivne dele — kun hele symbolet kan animeres (SYMBOLSTANDARD §8).</p>{/if}

      <h4>Farver</h4>
      <p class="muted small">Bibliotekets palette. Klik en farve for at se og kopiere koden; i animationernes farvefelter vælger du den direkte i paletten.</p>
      <div class="row">
        {#each SYMBOL_COLORS as c}
          <button type="button" class="sw" class:on={picked === c} style="background:{c}" title={c} aria-label={c} onclick={() => copy(c)}></button>
        {/each}
      </div>
      {#if picked}<p class="small"><span class="sw big" style="background:{picked}"></span> <code>{picked}</code>{copied === picked ? ' — kopieret' : ''}</p>{/if}
    </div>
  </div>
</section>

<style>
  .layout { display: grid; grid-template-columns: minmax(260px, 1fr) minmax(360px, 1.6fr); gap: 16px; }
  @media (max-width: 800px) { .layout { grid-template-columns: 1fr; } }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(84px, 1fr)); gap: 6px; margin-top: 8px; max-height: 70vh; overflow: auto; }
  .tile { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 6px; font-size: 11px; }
  .tile.on { border-color: var(--accent); background: var(--panel-2); }
  .stage { border: 1px solid var(--line); margin: 8px 0; max-width: 100%; }
  .bg-lys { background: #ffffff; }
  .bg-moerk { background: #1f1f1f; }
  .bg-skak { background: repeating-conic-gradient(#d6d6d6 0 25%, #ffffff 0 50%) 0 0 / 16px 16px; }
  .row { display: flex; flex-wrap: wrap; gap: 8px; align-items: end; margin: 6px 0; }
  .card { border: 1px solid var(--line); border-radius: 4px; padding: 6px 8px; margin: 6px 0; background: var(--panel); }
  .card summary { cursor: pointer; font-weight: 600; font-size: .9em; }
  .name { width: 7em; font-weight: 600; }
  .sw { width: 22px; height: 22px; padding: 0; border: 1px solid var(--line); display: inline-block; cursor: pointer; }
  .sw.on { outline: 2px solid var(--accent); outline-offset: 1px; }
  .sw.big { width: 28px; height: 28px; vertical-align: middle; cursor: default; }
</style>
