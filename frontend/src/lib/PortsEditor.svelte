<script lang="ts">
  // Tilslutningspunkterne for ét bibliotekssymbol (v2.16.0; egen komponent v6.11.0, Symboler med symbolet i centrum): de punkter,
  // rør i Tegn sættes fast i. Ændringen gælder symboler, der indsættes EFTER den; symboler i tegningerne beholder deres punkter.
  // Klik tilføjer et punkt (fanger til rørender og kantmidter), træk flytter, højreklik eller Delete fjerner.
  import { onMount, tick } from 'svelte';
  import { del, put } from './api';
  import { ask } from './ask';
  // @ts-expect-error — ren JS uden typer (deles med Tegn)
  import { autoPorts, boxOfRoot, snapCandidates, symbolType } from '../../svgedit-host/symbolPorts.js';

  type Pt = [number, number];
  type Box = { x: number; y: number; w: number; h: number };

  let { def, saved = $bindable(), typePorts = [], ondirty }: {
    def: { id: string; label: string; svg: string };
    /** Typens punkter fra Ind/ud og veje (fx pumpens IND/UD) — dem bruger Tegn, når punkterne ikke er rettet (v6.8.5) */
    typePorts?: Pt[];
    /** Serverens rettede punkter pr. type (deles med listen, så mærket "punkter rettet" følger med) */
    saved: Record<string, Pt[]>;
    ondirty?: (dirty: boolean) => void;
  } = $props();

  const type = $derived(symbolType(def.id) as string);
  const isCustom = $derived(!!saved[type]);
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
  $effect(() => ondirty?.(dirty));

  /** Tegn symbolet og læs dets boks og automatiske punkter (komponenten oprettes forfra pr. symbol). */
  async function show(): Promise<void> {
    picked = null;
    dirty = false;
    error = info = '';
    await tick();
    const root = holder?.firstElementChild as SVGGraphicsElement | null;
    box = root ? boxOfRoot(root) : null;
    if (!root || !box) { auto = []; ports = []; return; }
    // standarden er det, Tegn bruger: typens punkter fra Ind/ud og veje, ellers de automatisk fundne (v6.11.0)
    auto = typePorts.length ? typePorts.map((p) => [p[0], p[1]] as Pt) : autoPorts(root);
    candidates = snapCandidates(root);
    ports = (saved[type] ?? auto).map((p) => [p[0], p[1]] as Pt);
    const pad = Math.max(box.w, box.h) * 0.18 + 6;
    viewBox = `${box.x - pad} ${box.y - pad} ${box.w + 2 * pad} ${box.h + 2 * pad}`;
  }
  onMount(show);

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
    if ((e.key === 'Delete' || e.key === 'Backspace') && picked !== null && !(e.target instanceof HTMLInputElement)
      && !(e.target instanceof HTMLTextAreaElement) && !(e.target instanceof HTMLSelectElement)) {
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
    if (!(await ask(`Brug ${typePorts.length ? 'typens punkter' : 'de automatisk fundne punkter'} for "${def.label}" igen? Symboler i tegningerne ændres ikke.`, { ok: typePorts.length ? 'Brug typens punkter' : 'Brug de automatiske' }))) return;
    busy = true;
    error = info = '';
    try {
      await del(`/api/symbol-ports/${encodeURIComponent(type)}`);
      const { [type]: _gone, ...rest } = saved;
      saved = rest;
      ports = auto.map((p) => [p[0], p[1]] as Pt);
      dirty = false;
      info = `${def.label} bruger nu ${typePorts.length ? 'typens punkter' : 'de automatisk fundne punkter'}.`;
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

<p class="muted small">
  De grønne prikker er de punkter, rør og ledninger i Tegn sættes fast i. {#if isCustom}<span class="tag">rettet</span>{:else if typePorts.length}Typens punkter fra <em>Ind/ud og veje</em> (fx IND og UD).{:else}Automatiske punkter.{/if}
  <strong>Ændringen gælder symboler, du indsætter fremover</strong> — symboler i tegningerne beholder deres punkter.
</p>
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
<div class="row acts">
  <button class="primary" onclick={save} disabled={busy || !dirty}>Gem punkter ({ports.length})</button>
  <button onclick={show} disabled={busy || !dirty}>Fortryd ændringer</button>
  <button onclick={() => remove(picked)} disabled={busy || picked === null}>Fjern valgt punkt</button>
  <button onclick={reset} disabled={busy || !isCustom}>{typePorts.length ? 'Brug typens punkter' : 'Brug de automatiske'}</button>
</div>
{#if error}<p class="error" role="alert">{error}</p>{/if}
{#if info}<p class="notice">{info}</p>{/if}

<style>
  .stage { width: 100%; max-width: 640px; height: 440px; background: #f6f6f6; border: 1px solid var(--line); border-radius: var(--radius); cursor: crosshair; display: block; }
  .bbox { fill: none; stroke: #9db8e8; stroke-dasharray: 3 2; vector-effect: non-scaling-stroke; }
  .port { fill: #fff; stroke: #2e7d32; stroke-width: 2; vector-effect: non-scaling-stroke; cursor: move; }
  .port.custom { fill: #c8e6c9; }
  .port.picked { fill: #2e7d32; }
  .acts { gap: .5rem; flex-wrap: wrap; margin-top: .3rem; }
  .tag { font-size: .7rem; padding: 0 6px; border-radius: 8px; background: #e7f3e8; color: #2e7d32; border: 1px solid #a9d3ab; }
</style>
