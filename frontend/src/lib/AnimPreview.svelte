<script lang="ts">
  // Live preview ved animationerne i symbol-guiden (v2.10.0): symbolet tegnes lille ved siden af animationerne og følger
  // deres indstillinger med det samme. Samme animationsmotor som Overview (renderAll); gemmer og skriver intet.
  import { onDestroy, untrack } from 'svelte';
  import type { TagMeta } from './api';
  import { buildPreview, playState, previewValues } from './animPreview';
  import { renderAll } from './canvas';
  import type { SymbolConfig } from './symbolConfig';

  let { cfg, element, svg, kindOf, metaOf }: {
    cfg: SymbolConfig; element: string;
    /** Hele tegningens SVG (symbolet findes i den via element-id'et) */
    svg: string;
    kindOf: (tag: string) => 'bool' | 'num' | 'unknown';
    metaOf: (tag: string) => TagMeta | undefined;
  } = $props();

  let host = $state<SVGSVGElement | null>(null);
  let built = $state(0);          // tæller op, hver gang symbolet er tegnet forfra
  let found = $state(true);
  let vals = $state<Record<string, number>>({});
  let playing = $state(false);
  let playVals = $state<Record<string, number>>({});
  let timer: ReturnType<typeof setInterval> | null = null;
  let t0 = 0;

  const preview = $derived(buildPreview(cfg, element, kindOf));
  const bindingsKey = $derived(JSON.stringify(preview.bindings));
  const values = $derived(previewValues(preview.controls, playing ? playVals : vals));

  // Tegn symbolet forfra, når tegningen eller animationerne ændrer sig (så en fjernet animation ikke sætter spor)
  $effect(() => {
    void bindingsKey;
    const h = host, text = svg, id = element;
    if (!h) return;
    untrack(() => {
      h.replaceChildren();
      if (!text) { found = false; return; }
      const doc = new DOMParser().parseFromString(text, 'image/svg+xml');
      const src = doc.querySelector(`[id="${CSS.escape(id)}"]`);
      if (!src) { found = false; return; }
      for (const x of doc.querySelectorAll('svg > defs, svg > style')) h.appendChild(document.importNode(x, true));
      // Symbolets egen transform (placeringen i tegningen) medregnes ikke af getBBox på selve elementet — mål på en indpakning
      const wrap = document.createElementNS('http://www.w3.org/2000/svg', 'g') as SVGGraphicsElement;
      wrap.appendChild(document.importNode(src, true));
      h.appendChild(wrap);
      try {
        const b = wrap.getBBox();
        const pad = 4 + Math.max(b.width, b.height) * 0.05;
        h.setAttribute('viewBox', `${b.x - pad} ${b.y - pad} ${b.width + 2 * pad} ${b.height + 2 * pad}`);
      } catch {
        h.setAttribute('viewBox', '0 0 100 100');   // getBBox findes ikke overalt
      }
      found = true;
      built++;
    });
  });

  // Anvend animationerne med kontrollernes værdier
  $effect(() => {
    void built;
    const h = host, b = preview.bindings, v = values;
    if (!h || !found) return;
    const metas: Record<string, TagMeta> = {};
    for (const x of b) { const m = metaOf(x.tag); if (m) metas[x.tag] = m; }
    renderAll(h as unknown as HTMLElement, b, v, metas);
  });

  function set(name: string, v: number): void {
    stop();
    vals = { ...vals, [name]: v };
  }
  function start(): void {
    t0 = Date.now();
    playVals = playState(preview.controls, 0);
    playing = true;
    timer = setInterval(() => { playVals = playState(preview.controls, (Date.now() - t0) / 1000); }, 100);
  }
  function stop(): void {
    if (timer) { clearInterval(timer); timer = null; }
    if (playing) vals = { ...vals, ...playVals };
    playing = false;
  }
  function reset(): void {
    stop();
    vals = {};
  }
  onDestroy(() => { if (timer) clearInterval(timer); });
  const shown = (name: string): number => values[name]?.value === true ? 1 : Number(values[name]?.value ?? 0);
</script>

<aside class="preview" aria-label="Preview af animationerne">
  <h5>Preview</h5>
  {#if !found}
    <p class="small muted">Symbolet kunne ikke vises (findes ikke i tegningen endnu).</p>
  {:else}
    <div class="stage"><svg bind:this={host} xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Symbolet med animationerne"></svg></div>
  {/if}
  {#if !preview.bindings.length}
    <p class="small muted">Tilføj en animation og vælg dens kilde for at se den her.</p>
  {/if}
  {#if preview.unset}<p class="small muted">{preview.unset} {preview.unset === 1 ? 'animation mangler' : 'animationer mangler'} en kilde og vises ikke.</p>{/if}
  {#each preview.controls as c (c.name)}
    <div class="ctl">
      <span class="small lbl" title={c.label}>{c.label}</span>
      {#if c.kind === 'bool'}
        <span class="row">
          <button class="small" class:on={shown(c.name) < 1} onclick={() => set(c.name, 0)} aria-pressed={shown(c.name) < 1}>Fra</button>
          <button class="small" class:on={shown(c.name) >= 1} onclick={() => set(c.name, 1)} aria-pressed={shown(c.name) >= 1}>Til</button>
        </span>
      {:else if c.kind === 'pos'}
        <span class="row">
          {#each c.labels as l, j}
            <button class="small" class:on={Math.round(shown(c.name)) === j} onclick={() => set(c.name, j)} aria-pressed={Math.round(shown(c.name)) === j}>{l}</button>
          {/each}
        </span>
      {:else}
        <span class="row"><input type="range" min={c.min} max={c.max} step={c.step} value={shown(c.name)} aria-label={c.label}
          oninput={(e) => set(c.name, Number(e.currentTarget.value))} /> <span class="small mono">{Math.round(shown(c.name) * 100) / 100}</span></span>
      {/if}
    </div>
  {/each}
  {#if preview.controls.length}
    <div class="row">
      <button class="small" onclick={() => (playing ? stop() : start())}>{playing ? 'Stop' : 'Afspil'}</button>
      <button class="small" onclick={reset}>Nulstil</button>
    </div>
  {/if}
</aside>

<style>
  .preview { border: 1px solid var(--line); background: var(--panel-2); border-radius: var(--radius); padding: .5rem; position: sticky; top: 0; align-self: start; min-width: 0; }
  h5 { margin: 0 0 .35rem; font-size: .85rem; color: var(--muted); }
  .stage { background: #fff; border: 1px solid var(--line); border-radius: var(--radius); padding: .3rem; display: flex; justify-content: center; }
  .stage svg { width: 100%; height: 130px; }
  .ctl { margin-top: .45rem; display: flex; flex-direction: column; gap: .15rem; }
  .lbl { color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .row { display: flex; gap: .25rem; flex-wrap: wrap; align-items: center; }
  .ctl input[type=range] { flex: 1; min-width: 0; }
  button.on { background: var(--accent); border-color: var(--accent); color: #fff; }
  .ctl + .row { margin-top: .5rem; }
</style>
