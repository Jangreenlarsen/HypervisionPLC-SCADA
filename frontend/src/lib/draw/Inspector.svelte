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
    paint: { fill: string; stroke: string; strokeWidth: number; opacity: number; fontSize: number | null; fontFamily: string | null; bold: boolean | null; italic: boolean | null; underline: boolean | null; anchor: string | null; text: string | null; rx: number | null } | null;
  }
  export interface InspectApi {
    inspect(): Inspect | null;
    setBox(field: 'x' | 'y' | 'w' | 'h', value: string, keepRatio?: boolean): { ok?: boolean; error?: string };
    setAngle(deg: string): { ok?: boolean; error?: string };
    setStyle(attr: string, value: string | null): { ok?: boolean; error?: string };
    setText(value: string): { ok?: boolean; error?: string };
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

  const FONTS = ['Segoe UI, Arial', 'Arial', 'Verdana', 'Tahoma', 'Georgia', 'Courier New', 'sans-serif', 'serif', 'monospace'];
  const SIZES = [8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 40, 48, 64];
  const ALIGN = [
    { v: 'start', label: 'Venstrestillet', d: 'M4 6 H20 M4 10 H14 M4 14 H20 M4 18 H12' },
    { v: 'middle', label: 'Centreret', d: 'M4 6 H20 M7 10 H17 M4 14 H20 M8 18 H16' },
    { v: 'end', label: 'Højrestillet', d: 'M4 6 H20 M10 10 H20 M4 14 H20 M12 18 H20' },
  ];
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
        <span class="lbl">{p.fontSize !== null ? 'Farve' : 'Fyld'}</span>
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
        <div class="textbox">
          <label class="full">Tekst
            <textarea rows={Math.min(5, Math.max(2, (p.text ?? '').split('\n').length))} value={p.text ?? ''}
                      onchange={(e) => run(api?.setText(e.currentTarget.value))}
                      title="Ret teksten — Enter giver en ny linje; klik uden for feltet for at gemme"></textarea>
          </label>
          <div class="grid">
            <label>Størrelse
              <input inputmode="decimal" list="hv-font-sizes" value={p.fontSize} onchange={(e) => onField(e, (v) => api?.setStyle('font-size', v))} onkeydown={key} />
            </label>
            <label>Skrifttype
              <select value={p.fontFamily} onchange={(e) => run(api?.setStyle('font-family', e.currentTarget.value))}>
                {#each FONTS.includes(p.fontFamily ?? '') ? FONTS : [p.fontFamily ?? '', ...FONTS] as f}<option value={f}>{f}</option>{/each}
              </select>
            </label>
          </div>
          <datalist id="hv-font-sizes">{#each SIZES as n}<option value={n}></option>{/each}</datalist>
          <div class="tbar" role="toolbar" aria-label="Tekstformat">
            <button class="fmt" class:on={p.bold} aria-pressed={!!p.bold} title="Fed" onclick={() => run(api?.setStyle('font-weight', p.bold ? null : 'bold'))}><b>F</b></button>
            <button class="fmt" class:on={p.italic} aria-pressed={!!p.italic} title="Kursiv" onclick={() => run(api?.setStyle('font-style', p.italic ? null : 'italic'))}><i>K</i></button>
            <button class="fmt" class:on={p.underline} aria-pressed={!!p.underline} title="Understreget" onclick={() => run(api?.setStyle('text-decoration', p.underline ? null : 'underline'))}><u>U</u></button>
            <span class="tsep"></span>
            {#each ALIGN as a}
              <button class="fmt" class:on={p.anchor === a.v} aria-pressed={p.anchor === a.v} title={a.label} aria-label={a.label}
                      onclick={() => run(api?.setStyle('text-anchor', a.v === 'start' ? null : a.v))}>
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d={a.d} /></svg>
              </button>
            {/each}
          </div>
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
  .grid input, .grid select { width: 100%; min-width: 0; font-size: .9rem; padding: 2px 4px; }
  .pipe-acts { margin-bottom: .4rem; }
  .textbox { border-top: 1px solid var(--line); padding-top: .4rem; margin-top: .2rem; }
  .full { display: flex; flex-direction: column; font-size: .8rem; color: #555; margin-bottom: .35rem; }
  .full textarea { width: 100%; font: inherit; font-size: .9rem; resize: vertical; padding: 3px 5px; }
  .tbar { display: flex; gap: 2px; align-items: center; flex-wrap: wrap; }
  .fmt { width: 30px; height: 28px; padding: 3px; border: 1px solid var(--line); border-radius: 4px; background: #fff; font-size: .95rem; line-height: 1; }
  .fmt.on { background: #dbe8ff; border-color: #6c93d8; }
  .fmt svg { width: 100%; height: 100%; fill: none; stroke: #333; stroke-width: 2; stroke-linecap: round; }
  .tsep { width: 1px; height: 20px; background: var(--line); margin: 0 4px; }
  .paint { align-items: center; gap: .4rem; margin-bottom: .35rem; flex-wrap: wrap; }
  .paint .lbl { width: 2.6rem; font-size: .85rem; }
</style>
