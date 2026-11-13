<script lang="ts">
  // Ind/ud, navne og veje på et symbol (v4.13.0, PLAN.md › Signalveje 2): punkter med navn (A, B, AB …), rolle (ind/ud/begge) og
  // "fælles", og de veje symbolet kan lave (AB → A, AB → B). Gemmes pr. symboltype og bruges af flowberegningen (v6.1.0). Punkterne er
  // brøkdele af symbolets boks. v6.3.0: flow-profilen — rolle (forbruger/pumpe/rørstykke), medie og standarder — for enhver symboltype.
  import { tick } from 'svelte';
  import { del, put } from './api';
  import { ask } from './ask';
  import {
    FLOW_DEFAULTS, KIND_LABEL, MEDIUM_LABEL, PIECE_TYPES, ROLE_LABEL, UNITS, hasProfile, validateDef, waysOf, wayKey, wayLabel,
    type FlowDef, type FlowKind, type FlowMedium, type PortDef, type PortRole,
  } from './symbolFlow';
  // @ts-expect-error — ren JS uden typer (deles med Tegn)
  import { autoPorts, boxOfRoot } from '../../svgedit-host/symbolPorts.js';

  type Pt = [number, number];
  type Box = { x: number; y: number; w: number; h: number };
  let { svg, label, type, custom, onsaved, ondirty }: {
    svg: string; label: string; type: string; custom: FlowDef | undefined;
    onsaved: (type: string, def: FlowDef | null) => void; ondirty?: (dirty: boolean) => void;
  } = $props();

  const NAMES = 'ABCDEFGHIJKL';
  let ports = $state<PortDef[]>([]);
  let ownWays = $state(false);
  let ways = $state<[string, string][]>([]);
  // flow-profilen (v6.3.0)
  let kind = $state<FlowKind>('consumer');
  let medium = $state<FlowMedium>('water');
  let capacity = $state<number | null>(null);
  let restrict = $state<number | null>(null);
  let box = $state<Box | null>(null);
  let viewBox = $state('0 0 100 100');
  let picked = $state<number | null>(null);
  let dirty = $state(false);
  let busy = $state(false);
  let error = $state('');
  let info = $state('');
  let svgEl = $state<SVGSVGElement>();
  let holder = $state<SVGGElement>();
  let dragging: number | null = null;

  const source = $derived<'custom' | 'default' | 'none'>(custom ? 'custom' : FLOW_DEFAULTS[type] ? 'default' : 'none');
  const shownWays = $derived<[string, string][]>(ownWays ? ways : waysOf({ ports }));
  const r = $derived(box ? Math.max(box.w, box.h) * 0.035 + 1.5 : 3);
  const toLocal = (p: { x: number; y: number }): Pt => (box ? [box.x + p.x * box.w, box.y + p.y * box.h] : [0, 0]);

  function setDirty(v: boolean): void {
    dirty = v;
    ondirty?.(v);
  }

  /** Læs symbolets boks, og start fra den rettede definition, ellers standarden. */
  async function load(): Promise<void> {
    picked = null;
    error = info = '';
    await tick();
    const root = holder?.firstElementChild as SVGGraphicsElement | null;
    box = root ? boxOfRoot(root) : null;
    if (box) {
      const pad = Math.max(box.w, box.h) * 0.18 + 6;
      viewBox = `${box.x - pad} ${box.y - pad} ${box.w + 2 * pad} ${box.h + 2 * pad}`;
    }
    const d = custom ?? FLOW_DEFAULTS[type];
    ports = (d?.ports ?? []).map((p) => ({ ...p }));
    ownWays = !!d?.ways?.length;
    ways = (d?.ways ?? []).map((w) => [w[0], w[1]] as [string, string]);
    kind = d?.kind ?? (PIECE_TYPES.has(type) ? 'piece' : 'consumer');
    medium = d?.medium ?? 'water';
    capacity = d?.capacity ?? null;
    restrict = d?.restrict ?? null;
    setDirty(false);
  }
  $effect(() => { void type; void svg; void custom; void load(); });

  function fracAt(e: MouseEvent): { x: number; y: number } | null {
    if (!svgEl || !box) return null;
    const m = svgEl.getScreenCTM();
    if (!m) return null;
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(m.inverse());
    const clamp = (v: number) => Math.round(Math.min(1, Math.max(0, v)) * 1e4) / 1e4;
    return { x: clamp(box.w ? (p.x - box.x) / box.w : 0.5), y: clamp(box.h ? (p.y - box.y) / box.h : 0.5) };
  }
  const nextName = () => [...NAMES].map((c) => c).find((c) => !ports.some((p) => p.name === c)) ?? `P${ports.length + 1}`;

  function downOnCanvas(e: MouseEvent): void {
    if (e.button !== 0) return;
    const f = fracAt(e);
    if (!f) return;
    if (ports.length >= 12) { error = 'Højst 12 punkter pr. symbol'; return; }
    ports = [...ports, { ...f, name: nextName(), role: 'both' }];
    picked = ports.length - 1;
    setDirty(true);
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
    ports = ports.map((p, i) => (i === dragging ? { ...p, ...f } : p));
    setDirty(true);
  }
  const up = (): void => { dragging = null; };

  /** Fjern et punkt — og de veje, der brugte det. */
  function remove(i: number | null): void {
    if (i === null) return;
    const gone = ports[i].name;
    ports = ports.filter((_, k) => k !== i);
    ways = ways.filter((w) => w[0] !== gone && w[1] !== gone);
    picked = null;
    setDirty(true);
  }
  function rename(i: number, name: string): void {
    const old = ports[i].name;
    ports = ports.map((p, k) => (k === i ? { ...p, name } : p));
    ways = ways.map((w) => [w[0] === old ? name : w[0], w[1] === old ? name : w[1]] as [string, string]);
    setDirty(true);
  }
  function patch(i: number, change: Partial<PortDef>): void {
    ports = ports.map((p, k) => (k === i ? { ...p, ...change } : p));
    setDirty(true);
  }
  function startFromAuto(): void {
    const root = holder?.firstElementChild as SVGGraphicsElement | null;
    if (!root) return;
    ports = (autoPorts(root) as Pt[]).slice(0, 12).map((p, i) => ({ x: p[0], y: p[1], name: NAMES[i] ?? `P${i + 1}`, role: 'both' as PortRole }));
    ways = [];
    ownWays = false;
    setDirty(true);
  }
  function addWay(): void {
    if (ports.length < 2) return;
    ownWays = true;
    if (!ways.length) ways = waysOf({ ports }).map((w) => [w[0], w[1]] as [string, string]);
    ways = [...ways, [ports[0].name, ports[1].name]];
    setDirty(true);
  }
  function setWay(i: number, k: 0 | 1, name: string): void {
    ways = ways.map((w, j) => (j === i ? (k === 0 ? [name, w[1]] : [w[0], name]) as [string, string] : w));
    setDirty(true);
  }
  function removeWay(i: number): void {
    ways = ways.filter((_, j) => j !== i);
    setDirty(true);
  }
  function useDerived(): void {
    ownWays = false;
    ways = [];
    setDirty(true);
  }

  const current = (): FlowDef => ({
    ports: ports.map((p) => ({ ...p })), ...(ownWays && ways.length ? { ways } : {}),
    // rollen gemmes, når den afviger fra symbolets indbyggede (så en indbygget pumpe/et rørstykke kan blive en forbruger)
    ...(kind !== (PIECE_TYPES.has(type) ? 'piece' : type === 'pumpe' ? 'pump' : 'consumer') || kind !== 'consumer' ? { kind } : {}),
    ...(medium !== 'water' ? { medium } : {}),
    ...(capacity != null ? { capacity } : {}), ...(restrict != null ? { restrict } : {}),
  });
  const canSave = $derived(ports.length > 0 || hasProfile({ ports: [], kind, medium, capacity: capacity ?? undefined, restrict: restrict ?? undefined }));
  const unit = $derived(UNITS[medium]);

  async function save(): Promise<void> {
    const d = current();
    const bad = validateDef(d);
    if (bad) { error = bad; return; }
    busy = true;
    error = info = '';
    try {
      const saved = await put<FlowDef & { type: string }>(`/api/symbol-flow/${encodeURIComponent(type)}`,
        { ports: d.ports, ways: d.ways ?? [], kind: d.kind ?? null, medium: d.medium ?? null, capacity: d.capacity ?? null, restrict: d.restrict ?? null });
      const { type: _t, ...def } = saved;
      onsaved(type, def);
      setDirty(false);
      await tick();    // den nye definition genindlæser editoren (og nulstiller beskeden) — vis beskeden bagefter
      info = `Gemt: ${label} — ${KIND_LABEL[saved.kind ?? 'consumer'].split(' (')[0].toLowerCase()}, ${saved.ports.length} navngivne punkter. Det gælder alle tegninger med symbolet.`;
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  async function reset(): Promise<void> {
    if (!(await ask(`Brug standarden for "${label}" igen?`, { ok: 'Brug standarden' }))) return;
    busy = true;
    error = info = '';
    try {
      await del(`/api/symbol-flow/${encodeURIComponent(type)}`);
      onsaved(type, null);
      setDirty(false);
      await tick();
      info = `${label} bruger nu standarden.`;
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }
</script>

<svelte:window onmouseup={up} />

<p class="muted small">
  Giv punkterne et <strong>navn</strong> og en <strong>rolle</strong>, og markér det <strong>fælles</strong> punkt på en flervejs-ventil (AB).
  <strong>Ind/ud:</strong> en pumpe bestemmer flowets retning. <strong>Veje:</strong> en 3-vejsventil kan kun bruges gennem
  én af sine veje (AB → A eller AB → B). Resten af tegningen ændres ikke.
</p>
<h3>{label}
  {#if source === 'custom'}<span class="tag">rettet</span>{:else if source === 'default'}<span class="muted small">standard</span>{:else}<span class="muted small">ingen definition</span>{/if}</h3>

<!-- Flow-profilen (v6.3.0): gælder alle symboltyper, også elektriske komponenter -->
<fieldset class="profile">
  <legend>Flow-rolle</legend>
  <label class="pf">Rolle
    <select value={kind} onchange={(e) => { kind = e.currentTarget.value as FlowKind; setDirty(true); }} aria-label="Flow-rolle">
      {#each Object.entries(KIND_LABEL) as [k, v] (k)}<option value={k}>{v}</option>{/each}</select></label>
  <label class="pf">Medie
    <select value={medium} onchange={(e) => { medium = e.currentTarget.value as FlowMedium; setDirty(true); }} aria-label="Medie">
      {#each Object.entries(MEDIUM_LABEL) as [k, v] (k)}<option value={k}>{v}{UNITS[k as FlowMedium] ? ` (${UNITS[k as FlowMedium]})` : ''}</option>{/each}</select></label>
  {#if kind === 'pump'}
    <label class="pf">Standard-kapacitet
      <input type="number" min="0" max="65535" step="1" value={capacity ?? ''} placeholder="100" aria-label="Standard-kapacitet"
        oninput={(e) => { const v = e.currentTarget.value; capacity = v === '' ? null : Math.round(Number(v)); setDirty(true); }} /> {unit} ved fuld rate</label>
  {/if}
  {#if kind === 'consumer'}
    <label class="pf">Standard-restriktion
      <input type="number" min="0" max="1" step="0.01" value={restrict ?? ''} placeholder="1,00" aria-label="Standard-restriktion"
        oninput={(e) => { const v = e.currentTarget.value; restrict = v === '' ? null : Math.round(Number(v) * 100) / 100; setDirty(true); }} />
      <span class="small muted">0,00 = blokeret … 1,00 = ingen restriktion</span></label>
  {/if}
  <p class="small muted">Rollen og standarderne gælder, når et symbol af typen ikke har sin egen flow-opsætning i guiden (trin 4 › Flow). En
    <em>pumpe/kilde</em> giver flow fra IND til UD (fx en strømforsyning, der giver strøm); et <em>rørstykke/ledning</em> hører under
    forbindelserne og viser flowet med løbelys. Mediet bestemmer kun enheden, flowet vises i.</p>
</fieldset>
<!-- klik tilføjer et punkt; træk et punkt for at flytte det; højreklik fjerner det -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<svg bind:this={svgEl} class="stage" {viewBox} onmousedown={downOnCanvas} onmousemove={move} oncontextmenu={(e) => e.preventDefault()}>
  {#if box}<rect x={box.x} y={box.y} width={box.w} height={box.h} class="bbox" />{/if}
  <g bind:this={holder}>{@html svg}</g>
  {#each ports as p, i}
    {@const l = toLocal(p)}
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <g onmousedown={(e) => downOnPort(e, i)} oncontextmenu={(e) => { e.preventDefault(); remove(i); }}>
      <circle cx={l[0]} cy={l[1]} r={picked === i ? r * 1.6 : r * 1.2} class="port {p.role}" class:picked={picked === i} class:common={p.common}>
        <title>{p.name} ({ROLE_LABEL[p.role]}{p.common ? ', fælles' : ''}) — træk for at flytte, højreklik for at fjerne</title>
      </circle>
      <text x={l[0] + r * 1.8} y={l[1] - r * 1.4} class="plabel" font-size={r * 3.2}>{p.name}</text>
    </g>
  {/each}
</svg>
<p class="muted small">Klik for at tilføje et punkt · træk for at flytte · højreklik fjerner det.
  {#if !ports.length}<button class="linkish" onclick={startFromAuto}>Start fra tilslutningspunkterne</button>{/if}</p>

{#if ports.length}
  <table class="ports">
    <thead><tr><th>Navn</th><th>Rolle</th><th title="Det fælles punkt på en flervejs-ventil (AB)">Fælles</th><th title="Delens id i symbolet — bruges til at give netop denne port en animation">Del</th><th></th></tr></thead>
    <tbody>
      {#each ports as p, i (i)}
        <tr class:picked={picked === i} onclick={() => (picked = i)}>
          <td><input class="nm" value={p.name} maxlength="12" aria-label="Navn på punkt {i + 1}" onchange={(e) => rename(i, e.currentTarget.value.trim())} /></td>
          <td><select value={p.role} aria-label="Rolle for {p.name}" onchange={(e) => patch(i, { role: e.currentTarget.value as PortRole })}>
            {#each Object.entries(ROLE_LABEL) as [k, v] (k)}<option value={k}>{v}</option>{/each}</select></td>
          <td><input type="checkbox" checked={!!p.common} aria-label="{p.name} er fælles" onchange={(e) => patch(i, { common: e.currentTarget.checked || undefined })} /></td>
          <td><input class="nm" value={p.part ?? ''} placeholder="fx port_ab" aria-label="Del for {p.name}" onchange={(e) => patch(i, { part: e.currentTarget.value.trim() || undefined })} /></td>
          <td><button class="small" onclick={() => remove(i)} aria-label="Fjern {p.name}">✕</button></td>
        </tr>
      {/each}
    </tbody>
  </table>

  <h4>Veje gennem symbolet</h4>
  {#if !ownWays}
    <p class="muted small">{shownWays.length ? 'Laves automatisk: hvert fælles punkt parret med hvert af de andre.' : 'Ingen fælles punkt og ingen veje: alle forbindelser er tilladt.'}</p>
  {/if}
  <ul class="ways">
    {#each shownWays as w, i (wayKey(w))}
      <li>
        {#if ownWays}
          <select value={w[0]} aria-label="Vej {i + 1}, fra" onchange={(e) => setWay(i, 0, e.currentTarget.value)}>{#each ports as p (p.name)}<option>{p.name}</option>{/each}</select>
          →
          <select value={w[1]} aria-label="Vej {i + 1}, til" onchange={(e) => setWay(i, 1, e.currentTarget.value)}>{#each ports as p (p.name)}<option>{p.name}</option>{/each}</select>
          <button class="small" onclick={() => removeWay(i)} aria-label="Fjern vej {i + 1}">✕</button>
        {:else}{wayLabel(w)}{/if}
      </li>
    {/each}
  </ul>
  <div class="row">
    <button class="small" onclick={addWay} disabled={ports.length < 2}>+ Vej</button>
    {#if ownWays}<button class="small" onclick={useDerived}>Lav vejene automatisk</button>{/if}
  </div>
{/if}

<div class="row actions">
  <button class="primary" onclick={save} disabled={busy || !dirty || !canSave}>Gem</button>
  <button onclick={() => load()} disabled={busy || !dirty}>Fortryd ændringer</button>
  <button onclick={reset} disabled={busy || source !== 'custom'}>Brug standarden</button>
</div>
{#if error}<p class="error" role="alert">{error}</p>{/if}
{#if info}<p class="notice">{info}</p>{/if}

<style>
  .profile { border: 1px solid var(--line); border-radius: var(--radius); padding: .4rem .6rem; margin: .4rem 0 .6rem; display: flex; flex-wrap: wrap; gap: .4rem 1rem; align-items: center; max-width: 640px; }
  .profile legend { font-weight: 600; font-size: .85rem; }
  .profile p { flex-basis: 100%; margin: .2rem 0 0; }
  .pf { display: inline-flex; gap: .35rem; align-items: center; font-size: .88rem; }
  .pf input[type='number'] { width: 6rem; }
  .tag { font-size: .7rem; padding: 0 6px; border-radius: 8px; background: #e7f3e8; color: #2e7d32; border: 1px solid #a9d3ab; align-self: center; }
  .stage { width: 100%; max-width: 640px; height: 360px; background: #f6f6f6; border: 1px solid var(--line); border-radius: var(--radius); cursor: crosshair; display: block; }
  .bbox { fill: none; stroke: #9db8e8; stroke-dasharray: 3 2; vector-effect: non-scaling-stroke; }
  .port { fill: #fff; stroke: #1565c0; stroke-width: 2; vector-effect: non-scaling-stroke; cursor: move; }
  .port.in { stroke: #2e7d32; fill: #c8e6c9; }
  .port.out { stroke: #c62828; fill: #ffcdd2; }
  .port.common { stroke-width: 4; }
  .port.picked { fill: #ffe082; }
  .plabel { fill: #1a237e; font-weight: 700; pointer-events: none; paint-order: stroke; stroke: #fff; stroke-width: 2px; }
  .ports { border-collapse: collapse; margin: .5rem 0; }
  .ports th, .ports td { padding: .2rem .4rem; text-align: left; border-bottom: 1px solid var(--line); }
  .ports tr.picked { background: #e3f2fd; }
  .nm { width: 7rem; }
  .ways { list-style: none; margin: .2rem 0; padding: 0; }
  .ways li { padding: .15rem 0; }
  .actions { gap: .5rem; flex-wrap: wrap; margin-top: .6rem; }
  .linkish { background: none; border: none; color: var(--accent); text-decoration: underline; cursor: pointer; padding: 0; font: inherit; }
</style>
