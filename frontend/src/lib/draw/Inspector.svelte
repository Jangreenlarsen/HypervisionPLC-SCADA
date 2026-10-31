<script lang="ts">
  // Panelet "Egenskaber" i den nye tegne-editor: placering, størrelse, drejning og stil for det markerede.
  // Alle ændringer går gennem scada-core (kan fortrydes med Ctrl+Z).
  import ColorField from '../ColorField.svelte';

  export interface Inspect {
    count: number;
    tag: string | null;
    box: { x: number; y: number; w: number; h: number };
    angle: number;
    pipeRadius: number | null;
    paint: { fill: string; stroke: string; strokeWidth: number; opacity: number; fontSize: number | null; fontFamily: string | null; bold: boolean | null; rx: number | null } | null;
  }
  export interface InspectApi {
    inspect(): Inspect | null;
    setBox(field: 'x' | 'y' | 'w' | 'h', value: string, keepRatio?: boolean): { ok?: boolean; error?: string };
    setAngle(deg: string): { ok?: boolean; error?: string };
    setStyle(attr: string, value: string | null): { ok?: boolean; error?: string };
    setPipeRadius(value: string): { ok?: boolean; error?: string };
    straightenPipe(): { ok?: boolean; error?: string };
  }

  let { api, rev, keepRatio = false }: { api: InspectApi | null; rev: number; keepRatio?: boolean } = $props();

  let info = $state<Inspect | null>(null);
  let error = $state('');
  $effect(() => {
    void rev;
    info = api?.inspect() ?? null;
  });

  const FONTS = ['sans-serif', 'serif', 'monospace', 'Arial', 'Verdana', 'Courier New'];
  const isNone = (c: string | undefined) => !c || c === 'none' || c === 'transparent';

  function run(r: { ok?: boolean; error?: string } | undefined): void {
    error = r?.error ?? '';
    info = api?.inspect() ?? null;
  }
  // Ét felt ad gangen: Enter eller forlad feltet. Ugyldigt → feltet viser den gamle værdi igen.
  function onField(e: Event, apply: (v: string) => { ok?: boolean; error?: string } | undefined): void {
    const el = e.currentTarget as HTMLInputElement;
    run(apply(el.value.trim().replace(',', '.')));
  }
  const key = (e: KeyboardEvent) => { if (e.key === 'Enter') (e.currentTarget as HTMLInputElement).blur(); };
</script>

{#if !info}
  <p class="muted small">Vælg et element i tegningen.</p>
{:else}
  <div class="insp">
    <p class="muted small what">{info.count > 1 ? `${info.count} valgt` : `<${info.tag}>`}</p>
    <div class="grid">
      {#each [['x', 'X'], ['y', 'Y'], ['w', 'B'], ['h', 'H']] as [f, l]}
        <label>{l}
          <input inputmode="decimal" value={info.box[f as 'x']} onchange={(e) => onField(e, (v) => api?.setBox(f as 'x', v, keepRatio))} onkeydown={key}
                 title={f === 'w' ? 'Bredde' : f === 'h' ? 'Højde' : f === 'x' ? 'Venstre kant' : 'Øverste kant'} />
        </label>
      {/each}
      {#if info.count === 1}
        <label>∠ <input inputmode="decimal" value={info.angle} onchange={(e) => onField(e, (v) => api?.setAngle(v))} onkeydown={key} title="Drejning i grader" /></label>
      {/if}
      {#if info.pipeRadius !== null}
        <label>Bøjningsradius <input inputmode="decimal" value={info.pipeRadius} onchange={(e) => onField(e, (v) => api?.setPipeRadius(v))} onkeydown={key}
               title="Bløde bøjninger i forbindelsens knæk (0 = skarpe 90°-knæk). Nye forbindelser får den senest brugte radius." /></label>
      {/if}
      {#if info.paint?.rx !== null && info.paint?.rx !== undefined && info.pipeRadius === null}
        <label>Hjørne <input inputmode="decimal" value={info.paint.rx} onchange={(e) => onField(e, (v) => api?.setStyle('rx', v === '0' ? null : v))} onkeydown={key} title="Afrundede hjørner (radius)" /></label>
      {/if}
    </div>
    {#if info.pipeRadius !== null}
      <div class="row pipe-acts">
        <button class="small" onclick={() => run(api?.straightenPipe())}
                title="Læg forbindelsen om mellem dens to ender med så få knæk som muligt — tilslutningerne bevares">Ret forbindelsen ud</button>
      </div>
    {/if}
    {#if info.paint}
      {@const p = info.paint}
      <div class="row paint">
        <span class="lbl">Fyld</span>
        {#if isNone(p.fill)}
          <button class="small" onclick={() => run(api?.setStyle('fill', '#ffffff'))}>Ingen — tilføj</button>
        {:else}
          <ColorField value={p.fill} label="fyld" onchange={(c) => run(api?.setStyle('fill', c))} />
          <button class="small" onclick={() => run(api?.setStyle('fill', 'none'))} title="Intet fyld">✕</button>
        {/if}
      </div>
      <div class="row paint">
        <span class="lbl">Streg</span>
        {#if isNone(p.stroke)}
          <button class="small" onclick={() => run(api?.setStyle('stroke', '#000000'))}>Ingen — tilføj</button>
        {:else}
          <ColorField value={p.stroke} label="streg" onchange={(c) => run(api?.setStyle('stroke', c))} />
          <button class="small" onclick={() => run(api?.setStyle('stroke', 'none'))} title="Ingen streg">✕</button>
        {/if}
      </div>
      <div class="grid">
        <label>Tykkelse <input inputmode="decimal" value={p.strokeWidth} onchange={(e) => onField(e, (v) => api?.setStyle('stroke-width', v))} onkeydown={key} /></label>
        <label>Synlighed
          <select value={String(Math.round(p.opacity * 100))} onchange={(e) => run(api?.setStyle('opacity', String(Number(e.currentTarget.value) / 100)))}>
            {#each [100, 90, 75, 50, 25, 10] as o}<option value={String(o)}>{o} %</option>{/each}
            {#if ![100, 90, 75, 50, 25, 10].includes(Math.round(p.opacity * 100))}<option value={String(Math.round(p.opacity * 100))}>{Math.round(p.opacity * 100)} %</option>{/if}
          </select>
        </label>
      </div>
      {#if p.fontSize !== null}
        <div class="grid">
          <label>Skrift <input inputmode="decimal" value={p.fontSize} onchange={(e) => onField(e, (v) => api?.setStyle('font-size', v))} onkeydown={key} /></label>
          <label>Font
            <select value={p.fontFamily} onchange={(e) => run(api?.setStyle('font-family', e.currentTarget.value))}>
              {#each FONTS.includes(p.fontFamily ?? '') ? FONTS : [p.fontFamily ?? '', ...FONTS] as f}<option value={f}>{f}</option>{/each}
            </select>
          </label>
          <label class="chk"><input type="checkbox" checked={!!p.bold} onchange={(e) => run(api?.setStyle('font-weight', e.currentTarget.checked ? 'bold' : null))} /> Fed</label>
        </div>
      {/if}
    {:else if info.count === 1}
      <p class="muted small">Farverne i en gruppe/et symbol ændres under <strong>Farver</strong> nedenfor.</p>
    {/if}
    {#if error}<p class="error small" role="alert">{error}</p>{/if}
  </div>
{/if}

<style>
  .what { margin: 0 0 .3rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(5.5rem, 1fr)); gap: .3rem .5rem; margin-bottom: .4rem; }
  .grid label { display: flex; flex-direction: column; font-size: .8rem; color: #555; }
  .grid label.chk { flex-direction: row; align-items: center; gap: .3rem; padding-top: 1rem; }
  .grid input, .grid select { width: 100%; min-width: 0; font-size: .9rem; padding: 2px 4px; }
  .pipe-acts { margin-bottom: .4rem; }
  .paint { align-items: center; gap: .4rem; margin-bottom: .35rem; flex-wrap: wrap; }
  .paint .lbl { width: 2.6rem; font-size: .85rem; }
</style>
