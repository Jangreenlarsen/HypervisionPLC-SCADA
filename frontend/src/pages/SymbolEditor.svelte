<script lang="ts">
  // Symbol-editoren (v2.16.0): ret et bibliotekssymbols tilslutningspunkter — de punkter, rør i Tegn sættes fast i.
  // Ændringen gælder symboler, der indsættes EFTER den; symboler i tegningerne beholder deres punkter (PLAN.md).
  import { onMount, tick } from 'svelte';
  import { del, get, put } from '../lib/api';
  import { ask } from '../lib/ask';
  import { CATEGORIES, SYMBOLS, type SymbolCategory } from '../lib/symbols';
  import { drawHref, parseSymbolRoute } from '../lib/symbolRoute';
  // @ts-expect-error — ren JS uden typer (deles med Tegn)
  import { autoPorts, boxOfRoot, snapCandidates, symbolType } from '../../svgedit-host/symbolPorts.js';

  let { route = 'symbols' }: { route?: string } = $props();
  const from = $derived(parseSymbolRoute(route));
  let backName = $state('');

  type Pt = [number, number];
  type Box = { x: number; y: number; w: number; h: number };

  let saved = $state<Record<string, Pt[]>>({});   // serverens rettede punkter pr. type
  let category = $state<SymbolCategory | 'alle'>('alle');
  let search = $state('');
  let selectedId = $state(SYMBOLS[0].id);
  let ports = $state<Pt[]>([]);        // det der redigeres (brøkdele af symbolets boks)
  let auto = $state<Pt[]>([]);
  let candidates: Pt[] = [];
  let box = $state<Box | null>(null);
  let viewBox = $state('0 0 100 100');
  let picked = $state<number | null>(null);
  let dirty = $state(false);
  let busy = $state(false);
  let error = $state('');
  let info = $state('');
  let svgEl = $state<SVGSVGElement>();
  let holder = $state<SVGGElement>();

  const def = $derived(SYMBOLS.find((s) => s.id === selectedId) ?? SYMBOLS[0]);
  const type = $derived(symbolType(def.id) as string);
  const isCustom = $derived(!!saved[type]);
  const list = $derived(SYMBOLS.filter((s) =>
    (category === 'alle' || s.category === category) && (!search.trim() || s.label.toLowerCase().includes(search.trim().toLowerCase()))));

  onMount(async () => {
    try {
      saved = await get<Record<string, Pt[]>>('/api/symbol-ports');
    } catch (e) {
      error = `Kunne ikke hente de rettede punkter: ${(e as Error).message}`;
    }
    // åbnet fra Tegn: vis tegningens navn på tilbage-knappen, og start på det valgte symbol
    if (from.drawing) {
      try {
        backName = (await get<{ id: string; name: string }[]>('/api/drawings')).find((d) => d.id === from.drawing)?.name ?? '';
      } catch { /* knappen viser så bare "tegningen" */ }
    }
    const start = from.type ? SYMBOLS.find((x) => symbolType(x.id) === from.type) : null;
    await show(start?.id ?? selectedId);
  });

  async function back(): Promise<void> {
    if (dirty && !(await ask('Du har ændringer, der ikke er gemt. Kassér dem og gå tilbage?', { ok: 'Kassér', danger: true }))) return;
    location.hash = drawHref(from.drawing);
  }

  /** Tegn symbolet og læs dets boks og automatiske punkter. */
  async function show(id: string): Promise<void> {
    selectedId = id;
    picked = null;
    dirty = false;
    error = info = '';
    await tick();
    const root = holder?.firstElementChild as SVGGraphicsElement | null;
    box = root ? boxOfRoot(root) : null;
    if (!root || !box) { auto = []; ports = []; return; }
    auto = autoPorts(root);
    candidates = snapCandidates(root);
    ports = (saved[symbolType(id)] ?? auto).map((p) => [p[0], p[1]] as Pt);
    const pad = Math.max(box.w, box.h) * 0.18 + 6;
    viewBox = `${box.x - pad} ${box.y - pad} ${box.w + 2 * pad} ${box.h + 2 * pad}`;
  }

  async function choose(id: string): Promise<void> {
    if (dirty && !(await ask('Du har ændringer, der ikke er gemt. Kassér dem?', { ok: 'Kassér', danger: true }))) return;
    await show(id);
  }

  const toLocal = (f: Pt): Pt => (box ? [box.x + f[0] * box.w, box.y + f[1] * box.h] : [0, 0]);
  /** Musen → brøkdel, fanget til et hjørnepunkt/en kantmidte inden for 10 skærmpunkter; altid inden for boksen. */
  function fracAt(e: MouseEvent): Pt | null {
    if (!svgEl || !box) return null;
    const m = svgEl.getScreenCTM();
    if (!m) return null;
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(m.inverse());
    const scale = Math.hypot(m.a, m.b) || 1;
    let best: Pt | null = null;
    let bd = 10 / scale;
    for (const c of candidates) {
      const l = toLocal(c);
      const d = Math.hypot(l[0] - p.x, l[1] - p.y);
      if (d <= bd) { best = c; bd = d; }
    }
    if (best) return [best[0], best[1]];
    const clamp = (v: number) => Math.round(Math.min(1, Math.max(0, v)) * 1e4) / 1e4;
    return [clamp(box.w ? (p.x - box.x) / box.w : 0.5), clamp(box.h ? (p.y - box.y) / box.h : 0.5)];
  }

  let dragging: number | null = null;
  function downOnCanvas(e: MouseEvent): void {
    if (e.button !== 0) return;
    const f = fracAt(e);
    if (!f) return;
    if (ports.length >= 32) { error = 'Højst 32 tilslutningspunkter pr. symbol'; return; }
    ports = [...ports, f];
    picked = ports.length - 1;
    dirty = true;
  }
  function downOnPort(e: MouseEvent, i: number): void {
    e.stopPropagation();
    if (e.button !== 0) return;
    picked = i;
    dragging = i;
  }
  function move(e: MouseEvent): void {
    if (dragging === null) return;
    const f = fracAt(e);
    if (!f) return;
    ports = ports.map((p, i) => (i === dragging ? f : p));
    dirty = true;
  }
  const up = (): void => { dragging = null; };
  function remove(i: number | null): void {
    if (i === null) return;
    ports = ports.filter((_, k) => k !== i);
    picked = null;
    dirty = true;
  }
  function onKey(e: KeyboardEvent): void {
    if ((e.key === 'Delete' || e.key === 'Backspace') && picked !== null && !(e.target instanceof HTMLInputElement)) {
      e.preventDefault();
      remove(picked);
    }
  }

  async function save(): Promise<void> {
    if (!ports.length) { error = 'Mindst ét punkt — eller tryk "Brug de automatiske" for at nulstille.'; return; }
    busy = true;
    error = info = '';
    try {
      const r = await put<{ ports: Pt[] }>(`/api/symbol-ports/${encodeURIComponent(type)}`, { ports });
      saved = { ...saved, [type]: r.ports };
      ports = r.ports.map((p) => [p[0], p[1]] as Pt);
      dirty = false;
      info = `Gemt: ${def.label} har nu ${r.ports.length} tilslutningspunkter. Det gælder symboler, du indsætter fremover.`;
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  async function reset(): Promise<void> {
    if (!(await ask(`Brug de automatisk fundne punkter for "${def.label}" igen? Symboler i tegningerne ændres ikke.`, { ok: 'Brug de automatiske' }))) return;
    busy = true;
    error = info = '';
    try {
      await del(`/api/symbol-ports/${encodeURIComponent(type)}`);
      const { [type]: _gone, ...rest } = saved;
      saved = rest;
      ports = auto.map((p) => [p[0], p[1]] as Pt);
      dirty = false;
      info = `${def.label} bruger nu de automatisk fundne punkter.`;
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  const isAuto = (p: Pt) => auto.some((a) => a[0] === p[0] && a[1] === p[1]);
  const r = $derived(box ? Math.max(box.w, box.h) * 0.035 + 1.5 : 3);
</script>

<svelte:window onkeydown={onKey} onmouseup={up} />

<div class="row title">
  <h2>Symboler — tilslutningspunkter</h2>
  {#if from.fromDraw}<button class="back" onclick={back}>← Tilbage til {backName ? `"${backName}"` : 'tegningen'}</button>{/if}
</div>
<p class="muted small">
  Tilslutningspunkterne er de grønne prikker, rør i <a href="#draw">Tegn</a> sættes fast i. Vælg et symbol, og ret punkterne.
  <strong>Ændringen gælder symboler, du indsætter fremover</strong> — symboler, der allerede står i en tegning, beholder deres punkter.
</p>

<div class="layout">
  <aside class="panel">
    <input placeholder="Søg symbol" bind:value={search} aria-label="Søg symbol" />
    <select bind:value={category} aria-label="Kategori">
      <option value="alle">Alle kategorier</option>
      {#each CATEGORIES as c}<option value={c.id}>{c.label}</option>{/each}
    </select>
    <ul class="list">
      {#each list as s (s.id)}
        <li>
          <button class:on={s.id === selectedId} onclick={() => choose(s.id)}>
            {s.label}{#if saved[symbolType(s.id)]}<span class="tag" title="Punkterne er rettet">rettet</span>{/if}
          </button>
        </li>
      {/each}
    </ul>
  </aside>

  <section class="panel edit">
    <h3>{def.label} {#if isCustom}<span class="tag">rettet</span>{:else}<span class="muted small">automatiske punkter</span>{/if}</h3>
    <!-- klik tilføjer et punkt; træk et punkt for at flytte det; højreklik eller Delete fjerner det -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <svg bind:this={svgEl} class="stage" {viewBox} onmousedown={downOnCanvas} onmousemove={move} oncontextmenu={(e) => e.preventDefault()}>
      {#if box}<rect x={box.x} y={box.y} width={box.w} height={box.h} class="bbox" />{/if}
      <g bind:this={holder}>{@html def.svg}</g>
      {#each ports as p, i}
        {@const l = toLocal(p)}
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <circle cx={l[0]} cy={l[1]} r={picked === i ? r * 1.5 : r} class="port" class:picked={picked === i} class:custom={!isAuto(p)}
                onmousedown={(e) => downOnPort(e, i)} oncontextmenu={(e) => { e.preventDefault(); remove(i); }}>
          <title>Punkt {i + 1} — træk for at flytte, højreklik for at fjerne</title>
        </circle>
      {/each}
    </svg>
    <p class="muted small">Klik for at tilføje et punkt (det fanger til rørender og kantmidter) · træk for at flytte · højreklik eller <kbd>Delete</kbd> fjerner det valgte.</p>
    <div class="row">
      <button class="primary" onclick={save} disabled={busy || !dirty}>Gem punkter ({ports.length})</button>
      <button onclick={() => show(selectedId)} disabled={busy || !dirty}>Fortryd ændringer</button>
      <button onclick={() => remove(picked)} disabled={busy || picked === null}>Fjern valgt punkt</button>
      <button onclick={reset} disabled={busy || !isCustom}>Brug de automatiske</button>
    </div>
    {#if error}<p class="error" role="alert">{error}</p>{/if}
    {#if info}<p class="notice">{info}</p>{/if}
  </section>
</div>

<style>
  .title { align-items: center; gap: 1rem; flex-wrap: wrap; }
  .title h2 { margin: 0; }
  .back { margin-left: auto; }
  .layout { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 1rem; align-items: start; }
  @media (max-width: 800px) { .layout { grid-template-columns: 1fr; } }
  aside { display: flex; flex-direction: column; gap: .4rem; max-height: 75vh; }
  .list { list-style: none; margin: 0; padding: 0; overflow-y: auto; }
  .list button { width: 100%; text-align: left; border: 0; background: transparent; padding: 4px 6px; border-radius: 4px; display: flex; justify-content: space-between; gap: .5rem; }
  .list button:hover { background: #eef2f8; }
  .list button.on { background: #dbe8ff; }
  .tag { font-size: .7rem; padding: 0 6px; border-radius: 8px; background: #e7f3e8; color: #2e7d32; border: 1px solid #a9d3ab; align-self: center; }
  .stage { width: 100%; max-width: 640px; height: 440px; background: #f6f6f6; border: 1px solid var(--line); border-radius: var(--radius); cursor: crosshair; display: block; }
  .bbox { fill: none; stroke: #9db8e8; stroke-dasharray: 3 2; vector-effect: non-scaling-stroke; }
  .port { fill: #fff; stroke: #2e7d32; stroke-width: 2; vector-effect: non-scaling-stroke; cursor: move; }
  .port.custom { fill: #c8e6c9; }
  .port.picked { fill: #2e7d32; }
  .edit .row { gap: .5rem; flex-wrap: wrap; }
</style>
