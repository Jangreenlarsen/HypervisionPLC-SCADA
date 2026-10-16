<script lang="ts">
  // Symbol-guiden (symbolstandarden, fase 6): 6 trin til én konfiguration pr. symbol.
  // Valideringen er serverens (POST …/preview, kaldt løbende) — guiden viser fejl pr. trin og skriveplanen.
  // Reference for opførsel: docs/prototyper/symbolguide.html · teknik: docs/SYMBOLSTANDARD_IMPLEMENTERING.md afsnit 8.
  import { onDestroy, onMount } from 'svelte';
  import { api, get, post, put, type LiveValue } from './api';
  import { LiveClient } from './live';
  import TagSelect from './TagSelect.svelte';
  import {
    ALARM_TXT, ANIM_TXT, BLINK_TXT, CMP_TXT, MAX_ANIMS, MAX_LOGIC, MAX_LOGIC_INPUTS, MAX_PLANES, MAX_POSITIONS, OP_TXT, POS, STEPS,
    activeAt, animDefaults, cycleCell, describeBlock, emptyConfig, evalLogic, foundPosition, isLogicRef, newBlock, newSignal, partLabel,
    libraryDefault, preset, removeBlock, resize, setOp, tagKind, template, typesFor,
    type Anim, type AnimType, type LogicBlock, type Op, type PoolBlock, type Signal, type SrcKind, type SymbolConfig, type SymbolInfo,
  } from './symbolConfig';

  interface TagRow { name: string; source: string; unit: string; writable: boolean; plc: string }
  interface Write { tag: string; value: unknown; kind?: string; [k: string]: unknown }
  interface Preview {
    steps: Record<string, string[]>; warnings: string[]; errors: number;
    plans: { position: number; label: string; writes: Write[] }[];
  }

  let { drawingId, element, name, tags, onclose, onsaved }: {
    drawingId: string; element: string; name: string; tags: TagRow[];
    onclose: () => void; onsaved: () => void;
  } = $props();

  const enc = encodeURIComponent;
  const base = $derived(`/api/drawings/${enc(drawingId)}/symbols/${enc(element)}`);

  let cfg = $state<SymbolConfig>(emptyConfig());
  let symbol = $state<SymbolInfo | null>(null);
  let exists = $state(false);
  let hasPin = $state(false);
  let pin = $state('');
  let notes = $state<string[]>([]);
  let pool = $state<PoolBlock[]>([]);   // logikblokke i andre symboler på tegningen
  let step = $state(0);
  let loading = $state(true);
  let error = $state('');       // fejl fra gem/fjern — vises, men stopper ikke guiden
  let loadError = $state('');   // symbolet kunne ikke hentes — guiden kan ikke bruges
  let saving = $state(false);
  let preview = $state<Preview | null>(null);
  let previewError = $state('');
  let checking = $state(false);   // en ændring venter på serverens kontrol
  let liveVals = $state<Record<string, LiveValue>>({});

  const tagByName = $derived(new Map(tags.map((t) => [t.name, t])));
  const sigKind = (id: string): 'bool' | 'num' | 'unknown' => {
    const s = cfg.signals.find((x) => x.id === id);
    return s ? tagKindOf(s.tag) : 'unknown';
  };
  function tagKindOf(tag: string): 'bool' | 'num' | 'unknown' {
    const k = tagKind(tagByName.get(tag)?.source);
    if (k !== 'unknown') return k;
    const v = liveVals[tag]?.value;   // ST-variabel: typen kendes fra live-værdien
    return typeof v === 'boolean' ? 'bool' : typeof v === 'number' ? 'num' : 'unknown';
  }
  const srcKind = (a: Anim): SrcKind => (a.src === POS ? 'pos' : isLogicRef(a.src) || tagKindOf(a.src) === 'bool' ? 'bool' : 'num');
  const n = $derived(cfg.positions.length);
  const isPos = $derived(cfg.op === 'positions');
  const partIds = $derived(['all', ...Object.keys(symbol?.parts ?? {})]);
  const partInfo = (id: string) => (id === 'all' ? symbol ?? undefined : symbol?.parts[id]);
  const locks = $derived(isPos && cfg.lock.positions.some(Boolean));
  const pinOk = $derived(pin === '' || /^\d{4}$/.test(pin));
  const needPin = $derived(locks && !hasPin && !pin);
  const pinMissing = $derived(exists ? 'Symbolet har ingen kode (fx efter gendannelse af en backup) — sæt en ny kode.' : 'Låste positioner kræver en kode.');
  const stepErrors = (k: number): string[] => [...(preview?.steps[String(k + 1)] ?? []), ...(k === 4 && needPin ? [pinMissing] : [])];
  const canSave = $derived(!!preview && !checking && preview.errors === 0 && !needPin && pinOk && !saving && !previewError);

  // ---------------------------------------------------------------- indlæsning
  onMount(async () => {
    try {
      const r = await get<{ config: SymbolConfig | null; has_pin: boolean; symbol: SymbolInfo | null; orphaned: boolean; warnings: string[]; logic_pool?: PoolBlock[] }>(`${base}/config`);
      if (r.orphaned || !r.symbol) throw new Error(`Elementet '${element}' findes ikke i den aktive version af tegningen`);
      symbol = r.symbol;
      pool = r.logic_pool ?? [];
      hasPin = r.has_pin;
      if (r.config) {
        cfg = normalize(r.config);
        exists = true;
      } else {
        await convert(false);
        const proposal = libraryDefault(symbol);
        if (proposal && !cfg.anims.length && !cfg.signals.length) {
          cfg = proposal.config;
          notes = [...notes, proposal.note];
        }
      }
    } catch (e) {
      loadError = (e as Error).message;
    } finally {
      loading = false;
    }
  });

  /** Udfyld felter serveren kan have udeladt, så formularen altid har dem. */
  function normalize(c: SymbolConfig): SymbolConfig {
    const d = emptyConfig(c.type);
    return {
      ...d, ...c, fault: c.fault ?? '', lock: { ...d.lock, ...(c.lock ?? {}) },
      signals: (c.signals ?? []).map((s: Partial<Signal> & { id: string }) => ({ ...{ tag: '', fb: '', write: 'set' as const, ms: 500, rest: null }, ...s })),
      anims: (c.anims ?? []).map((a) => ({ ...a, src: a.src ?? '', params: a.params ?? {}, only: a.only ?? null })),
      logic: (c.logic ?? []).map((b) => ({
        id: b.id, name: b.name ?? '', op: b.op ?? 'and', invert: Boolean(b.invert),
        inputs: (b.inputs ?? []).map((i) => ({ src: i.src ?? '', neg: Boolean(i.neg), cmp: i.cmp ?? '', value: i.value ?? null })),
      })),
    };
  }

  /** Forslag ud fra symbolets bindinger i dag (Konvertér). */
  async function convert(ask: boolean): Promise<void> {
    if (ask && !confirm('Erstat guidens indhold med et forslag ud fra symbolets bindinger i dag?')) return;
    try {
      const s = await get<{ config: SymbolConfig; notes: string[]; convertible: boolean }>(`${base}/suggest`);
      notes = s.notes ?? [];
      if (s.convertible) cfg = normalize(s.config);
      else if (!ask) cfg = emptyConfig(symbol?.type ?? 'custom');
    } catch (e) {
      notes = [`Forslaget kunne ikke hentes: ${(e as Error).message}`];
      if (!ask) cfg = emptyConfig(symbol?.type ?? 'custom');
    }
  }

  // ---------------------------------------------------------------- serverens validering (løbende)
  let timer: ReturnType<typeof setTimeout> | null = null;
  let seq = 0;
  $effect(() => {
    const body = JSON.stringify(cfg);
    if (loading || loadError) return;
    if (timer) clearTimeout(timer);
    const mine = ++seq;   // hver ændring gør ældre svar forældede — også dem der allerede er undervejs
    checking = true;
    timer = setTimeout(async () => {
      try {
        const r = await post<Preview>(`${base}/preview`, { config: JSON.parse(body) });
        if (mine !== seq) return;
        preview = r;
        previewError = '';
        checking = false;
      } catch (e) {
        if (mine !== seq) return;
        previewError = (e as Error).message;
        checking = false;
      }
    }, 300);
  });

  // ---------------------------------------------------------------- live-værdier (trin 6)
  const live = new LiveClient((changes) => { liveVals = { ...liveVals, ...changes }; });
  const usedTags = $derived([...new Set([
    ...cfg.signals.flatMap((s) => [s.tag, s.fb]), cfg.fault, ...cfg.anims.map((a) => a.src), ...cfg.anims.map((a) => a.params.dir_tag ?? ''),
    ...cfg.logic.flatMap((b) => b.inputs.map((i) => i.src)),
  ].filter((t) => t && t !== POS && !isLogicRef(t) && tagByName.has(t)))].sort());
  /** Pseudo-tags for blokke i andre symboler som denne konfiguration bruger (til live-værdierne i trin 6). */
  const foreignTags = $derived([...new Set([
    ...cfg.logic.flatMap((b) => b.inputs.map((i) => i.src)), ...cfg.anims.map((a) => a.src), ...cfg.anims.map((a) => a.params.dir_tag ?? ''),
  ].filter((s) => isLogicRef(s) && s.includes(':')).map(pseudoOf))]);
  function pseudoOf(ref: string): string {
    const k = ref.lastIndexOf(':');
    return `sym:${drawingId}:${ref.slice(1, k)}:logic:${ref.slice(k + 1)}`;
  }
  $effect(() => { live.subscribe([...usedTags, ...foreignTags]); });
  onDestroy(() => {
    live.close();
    if (timer) clearTimeout(timer);
  });
  const valueOf = (t: string) => liveVals[t]?.value;
  const found = $derived(isPos ? foundPosition(cfg, valueOf) : null);
  const logicNow = $derived(evalLogic(cfg.logic, valueOf, (ref) => { const v = valueOf(pseudoOf(ref)); return typeof v === 'boolean' ? v : null; }));
  const triText = (v: boolean | null | undefined) => (v === true ? 'Til' : v === false ? 'Fra' : 'ukendt');
  const fmt = (v: unknown) => (v === undefined || v === null ? '—' : typeof v === 'boolean' ? (v ? 'Til' : 'Fra') : String(v));

  // ---------------------------------------------------------------- redigering
  function changeOp(op: Op): void {
    setOp(cfg, op);
  }
  function addPosition(): void {
    if (n >= MAX_POSITIONS) return;
    cfg.positions.push({ label: String(n + 1) });
    resize(cfg, sigKind);
  }
  function removePosition(j: number): void {
    if (n <= 2) return;
    cfg.positions.splice(j, 1);
    for (const p of cfg.planes) p.values.splice(j, 1);
    cfg.lock.positions.splice(j, 1);
    for (const a of cfg.anims) {
      a.only?.splice(j, 1);
      for (const k of ['colors', 'set', 'angles', 'dxs', 'dys', 'dirs']) if (Array.isArray(a.params[k])) a.params[k].splice(j, 1);
    }
  }
  function addSignal(): void {
    if (cfg.signals.length >= 8) return;
    cfg.signals.push(newSignal(cfg));
  }
  function removeSignal(i: number): void {
    const id = cfg.signals[i].id;
    cfg.signals.splice(i, 1);
    cfg.planes = cfg.planes.filter((p) => p.signal !== id);
  }
  function addPlane(): void {
    if (cfg.planes.length >= MAX_PLANES) return;
    const free = cfg.signals.find((s) => !cfg.planes.some((p) => p.signal === s.id)) ?? newSignal(cfg);
    if (!cfg.signals.includes(free)) cfg.signals.push(free);
    cfg.planes.push({ signal: free.id, values: cfg.positions.map(() => (sigKind(free.id) === 'num' ? null : 0)) });
  }
  function setCell(p: { values: (number | null)[] }, j: number, raw: string): void {
    const t = raw.trim().replace(',', '.');
    p.values[j] = t === '' ? null : Number.isFinite(Number(t)) ? Number(t) : p.values[j];
  }
  function applyTemplate(t: 'A' | 'B' | 'C' | 'D'): void {
    if (cfg.planes.length && !confirm('Erstat kontaktplanerne med skabelonen?')) return;
    template(cfg, t);
  }
  function applyPreset(): void {
    if (!confirm('Indsæt eksemplet "7-trins vælger" (erstatter positioner, signaler og kontaktplaner)?')) return;
    preset(cfg);
    step = 1;
  }

  // ---- logikblokke
  const blockLabel = (b: LogicBlock) => `${b.id}${b.name ? ` – ${b.name}` : ''}`;
  const poolLabel = (p: PoolBlock) => `${p.symbol} · ${p.id}${p.name ? ` – ${p.name}` : ''}`;
  const poolRef = (p: PoolBlock) => `@${p.element}:${p.id}`;
  const firstBlockRef = (local: LogicBlock[]) => (local[0] ? `@${local[0].id}` : pool[0] ? poolRef(pool[0]) : '');
  const srcMode = (a: Anim): string => (a.src === POS ? POS : isLogicRef(a.src) ? 'logic' : 'tag');
  function setSrcMode(a: Anim, mode: string): void {
    a.src = mode === POS ? POS : mode === 'logic' ? firstBlockRef(cfg.logic) : '';
    resetParams(a);
  }
  function addBlock(): void {
    if (cfg.logic.length >= MAX_LOGIC) return;
    cfg.logic.push(newBlock(cfg));
  }
  function addInput(b: LogicBlock): void {
    if (b.inputs.length >= MAX_LOGIC_INPUTS) return;
    b.inputs.push({ src: '', neg: false, cmp: '', value: null });
  }
  /** Tagget er valgt: et tal-tag får en sammenligning (≥), et til/fra-tag ingen. */
  function inputTagChanged(i: LogicBlock['inputs'][number]): void {
    const k = tagKindOf(i.src);
    if (k === 'num') {
      if (!i.cmp) i.cmp = 'ge';
    } else if (k === 'bool') {
      i.cmp = '';
      i.value = null;
    }
  }
  /** Blokke en indgang må bruge: kun dem over blokken (serveren afviser løkker). */
  const earlier = (b: LogicBlock) => cfg.logic.slice(0, cfg.logic.indexOf(b));
  function setInputMode(b: LogicBlock, i: LogicBlock['inputs'][number], mode: string): void {
    i.src = mode === 'block' ? firstBlockRef(earlier(b)) : '';
    i.cmp = '';
    i.value = null;
  }
  const num2 = (v: string): number | null => (v.trim() !== '' && Number.isFinite(Number(v.replace(',', '.'))) ? Number(v.replace(',', '.')) : null);

  function addAnim(): void {
    if (cfg.anims.length >= MAX_ANIMS) return;
    const part = partIds.find((p) => p !== 'all') ?? 'all';
    const src = isPos ? POS : cfg.signals[0]?.tag ?? '';
    const a: Anim = { part, type: 'fill', src, params: {}, only: null };
    a.params = animDefaults('fill', srcKind(a), n);
    cfg.anims.push(a);
  }
  function resetParams(a: Anim): void {
    if (!typesFor(partInfo(a.part)).includes(a.type)) a.type = 'fill';
    a.params = animDefaults(a.type, srcKind(a), n);
    if (a.src !== POS) a.only = isPos ? a.only : null;
  }
  function moveAnim(i: number, d: -1 | 1): void {
    const j = i + d;
    if (j < 0 || j >= cfg.anims.length) return;
    [cfg.anims[i], cfg.anims[j]] = [cfg.anims[j], cfg.anims[i]];
  }
  function toggleOnly(a: Anim, j: number): void {
    const only = a.only ?? cfg.positions.map(() => true);
    only[j] = !only[j];
    a.only = only.every(Boolean) ? null : only;
  }
  const num = (v: string, fallback: number) => (Number.isFinite(Number(v.replace(',', '.'))) && v.trim() !== '' ? Number(v.replace(',', '.')) : fallback);

  // ---------------------------------------------------------------- gem / fjern
  async function save(): Promise<void> {
    saving = true;
    error = '';
    try {
      const body: Record<string, unknown> = { config: $state.snapshot(cfg) };
      if (pin) body.pin = pin;   // skriv-kun: koden sendes kun når den sættes, og vises aldrig igen
      const r = await put<{ has_pin: boolean }>(`${base}/config`, body);
      hasPin = r.has_pin;
      pin = '';
      onsaved();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      saving = false;
    }
  }
  async function remove(): Promise<void> {
    if (!confirm(`Fjern symbol-konfigurationen for ${name}? Symbolets gamle bindinger gælder så igen.`)) return;
    saving = true;
    error = '';
    try {
      await api('DELETE', `${base}/config`);
      onsaved();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      saving = false;
    }
  }
  /** Fjern koden straks (skriv-kun; serveren svarer kun has_pin). */
  async function clearPin(): Promise<void> {
    const msg = locks ? 'Fjern koden? De låste positioner kan så ikke vælges, før en ny kode er sat.' : 'Fjern koden?';
    if (!confirm(msg)) return;
    error = '';
    try {
      const r = await api<{ has_pin: boolean }>('DELETE', `${base}/pin`);
      hasPin = r.has_pin;
      pin = '';
    } catch (e) {
      error = (e as Error).message;
    }
  }
  const writeText = (w: Write) => `${w.tag} := ${fmt(w.value)}${w.kind === 'pulse' ? ' (puls)' : ''}`;
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={() => !saving && onclose()}>
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="panel guide" role="dialog" aria-modal="true" aria-label="Opsæt symbol {name}" tabindex="-1" onclick={(e) => e.stopPropagation()}>
    <header class="row head">
      <h2>Opsæt symbol: {name}</h2>
      <span class="muted small">{element}{symbol?.type ? ` · ${symbol.type}` : ''}{exists ? ' · konfigureret' : ''}</span>
      <button class="close" onclick={onclose} disabled={saving} aria-label="Luk">✕</button>
    </header>

    {#if loading}
      <p class="muted">Henter…</p>
    {:else if !symbol}
      <p class="error">{loadError}</p>
    {:else}
      <nav class="steps" aria-label="Trin">
        {#each STEPS as s, k}
          {@const disabled = !isPos && k === 2}
          <button class:active={step === k} {disabled} onclick={() => (step = k)}>
            {k + 1}. {s}{#if stepErrors(k).length}<span class="dot" title="{stepErrors(k).length} fejl"></span>{/if}
          </button>
        {/each}
      </nav>

      <div class="body">
        {#if step === 0}
          <p class="muted small">Vælg hvordan symbolet betjenes. Alt andet i guiden følger af dette valg.</p>
          <div class="ops">
            {#each Object.entries(OP_TXT) as [op, txt]}
              <label class="opt"><input type="radio" name="op" checked={cfg.op === op} onchange={() => changeOp(op as Op)} /> {txt}</label>
            {/each}
          </div>
          <div class="row">
            <button onclick={() => convert(true)}>Foreslå ud fra symbolet</button>
            <button onclick={applyPreset}>Eksempel: 7-trins vælger</button>
          </div>
          {#if notes.length}
            <div class="notice small"><strong>Forslag fra de gamle bindinger:</strong><ul>{#each notes as m}<li>{m}</li>{/each}</ul></div>
          {/if}
        {:else if step === 1}
          {#if cfg.op === 'view'}
            <p class="muted small">Kun visning: symbolet skriver intet. Animationerne vælger deres tags under trin 4.</p>
          {:else if cfg.op === 'pulse' || cfg.op === 'entry'}
            <label class="field-row">{cfg.op === 'pulse' ? 'Signal der pulses' : 'Register der skrives'}
              <TagSelect bind:value={cfg.signals[0].tag} {tags} writableOnly />
            </label>
          {:else}
            <p class="muted small">Signalerne symbolet skriver. Tilbagemelding (valgfri) bruges til at finde PLC'ens position; ellers bruges kommandoen.</p>
            <table class="grid">
              <thead><tr><th>Id</th><th>Kommando</th><th>Tilbagemelding</th><th>Skrives som</th><th></th></tr></thead>
              <tbody>
                {#each cfg.signals as s, i (s.id)}
                  <tr>
                    <td><strong>{s.id}</strong></td>
                    <td><TagSelect bind:value={s.tag} {tags} writableOnly /></td>
                    <td><TagSelect bind:value={s.fb} {tags} placeholder="— ingen —" /></td>
                    <td class="skriv">
                      <select bind:value={s.write}><option value="set">Sæt</option><option value="pulse">Puls</option></select>
                      {#if s.write === 'pulse'}
                        <input class="n" type="number" min="100" max="10000" step="100" bind:value={s.ms} title="Pulslængde (ms)" /> ms
                        hvile <input class="n" value={s.rest ?? ''} placeholder="0" title="Værdi efter pulsen (tom = 0/Fra)"
                          onchange={(e) => { const t = e.currentTarget.value.trim(); s.rest = t === '' ? null : num(t, 0); }} />
                      {/if}
                    </td>
                    <td><button class="small" onclick={() => removeSignal(i)} disabled={cfg.signals.length <= 1} aria-label="Fjern {s.id}">✕</button></td>
                  </tr>
                {/each}
              </tbody>
            </table>
            <button class="small" onclick={addSignal} disabled={cfg.signals.length >= 8}>+ Signal</button>
          {/if}
          {#if cfg.op !== 'view'}
            <label class="field-row">Fejlsignal (valgfrit — betjening spærres når det er sat)
              <TagSelect bind:value={cfg.fault} {tags} placeholder="— intet —" />
            </label>
          {/if}
        {:else if step === 2 && isPos}
          <div class="row wrap">
            <span class="small muted">Positioner:</span>
            {#each cfg.positions as p, j}
              <span class="pos"><input class="lbl" maxlength="20" bind:value={p.label} aria-label="Position {j + 1}" />
                <button class="small" onclick={() => removePosition(j)} disabled={n <= 2} aria-label="Fjern position {j + 1}">✕</button></span>
            {/each}
            <button class="small" onclick={addPosition} disabled={n >= MAX_POSITIONS}>+ Position</button>
          </div>
          <div class="row wrap">
            <span class="small muted">Skabelon:</span>
            <button class="small" onclick={() => applyTemplate('A')} title="Ét register med positionens nummer">A · ét register</button>
            <button class="small" onclick={() => applyTemplate('B')} title="Ét til/fra-signal pr. position">B · ét signal pr. position</button>
            <button class="small" onclick={() => applyTemplate('C')} title="Ét register med en bit pr. position">C · bitmaske</button>
            <button class="small" onclick={() => applyTemplate('D')} title="Positionens nummer binært på flere signaler">D · dec → bin</button>
          </div>
          <table class="grid planes">
            <thead><tr><th>Signal</th>{#each cfg.positions as p}<th>{p.label}</th>{/each}<th></th></tr></thead>
            <tbody>
              {#each cfg.planes as p, i}
                {@const k = sigKind(p.signal)}
                <tr>
                  <td><select bind:value={p.signal}>{#each cfg.signals as s}<option value={s.id}>{s.id}{s.tag ? ` · ${s.tag}` : ''}</option>{/each}</select></td>
                  {#each p.values as v, j}
                    <td>
                      {#if k === 'bool'}
                        <button class="cell" class:on={v === 1} class:off={v === 0} onclick={() => (p.values[j] = cycleCell(v))}>{v === 1 ? 'Til' : v === 0 ? 'Fra' : '–'}</button>
                      {:else}
                        <input class="n" value={v ?? ''} placeholder="–" onchange={(e) => setCell(p, j, e.currentTarget.value)} aria-label="{p.signal} i {cfg.positions[j].label}" />
                      {/if}
                    </td>
                  {/each}
                  <td><button class="small" onclick={() => cfg.planes.splice(i, 1)} aria-label="Fjern plan">✕</button></td>
                </tr>
              {/each}
              <tr class="active-row">
                <td class="small muted">Aktive signaler</td>
                {#each cfg.positions as _, j}<td class="small">{activeAt(cfg, j, sigKind).join(' ') || '—'}</td>{/each}<td></td>
              </tr>
            </tbody>
          </table>
          <button class="small" onclick={addPlane} disabled={cfg.planes.length >= MAX_PLANES}>+ Kontaktplan</button>
          <p class="small muted">Til/fra-signaler: klik i cellen (Til → Fra → røres ikke). Registre: skriv værdien, tom = røres ikke.</p>
        {:else if step === 3}
          <div class="row wrap">
            {#if isPos}
              <label class="field-row">Vis
                <select bind:value={cfg.display}><option value="remote">PLC'ens position</option><option value="local">Valgt position</option></select>
              </label>
              <label class="field-row">Tid til at bekræfte (s)
                <input class="n" type="number" min="0.5" max="120" step="0.5" bind:value={cfg.validate_s} />
              </label>
            {/if}
            {#if cfg.op !== 'view'}
              <label class="field-row">Alarm ved afvigelse/fejl
                <select bind:value={cfg.alarm}>{#each Object.entries(ALARM_TXT) as [v, t]}<option value={v}>{t}</option>{/each}</select>
              </label>
            {/if}
          </div>
          <h4>Logik ({cfg.logic.length}/{MAX_LOGIC})</h4>
          <p class="small muted">Saml flere tags i én betingelse (fx pumpe kører OG ventil åben), og brug den som kilde til en animation. En blok kan også bruge blokkene over sig og blokke i andre symboler på tegningen (og omvendt — dine blokke kan bruges dér).</p>
          {#each cfg.logic as b (b.id)}
            <div class="anim logic">
              <div class="row wrap">
                <strong>{b.id}</strong>
                <input class="name" bind:value={b.name} maxlength="40" placeholder="Navn (fx Pumpe kører og ventil åben)" aria-label="Blokkens navn" />
                <select bind:value={b.op} aria-label="Regel"><option value="and">AND — alle skal være Til</option><option value="or">OR — mindst én Til</option></select>
                <label class="opt small"><input type="checkbox" bind:checked={b.invert} /> NOT på resultatet</label>
                <span class="spacer"></span>
                <button class="small" onclick={() => removeBlock(cfg, b.id)} aria-label="Fjern blok">✕</button>
              </div>
              {#each b.inputs as inp, k}
                {@const refs = earlier(b)}
                {@const isBlock = isLogicRef(inp.src)}
                <div class="row wrap small input">
                  <label class="opt"><input type="checkbox" bind:checked={inp.neg} /> NOT</label>
                  {#if refs.length || pool.length}
                    <select value={isBlock ? 'block' : 'tag'} onchange={(e) => setInputMode(b, inp, e.currentTarget.value)} aria-label="Indgangstype">
                      <option value="tag">tag</option><option value="block">blok</option>
                    </select>
                  {/if}
                  {#if isBlock}
                    <select bind:value={inp.src} aria-label="Blok">
                      {#if refs.length}<optgroup label="Dette symbol">{#each refs as r}<option value={'@' + r.id}>{blockLabel(r)}</option>{/each}</optgroup>{/if}
                      {#if pool.length}<optgroup label="Andre symboler">{#each pool as p}<option value={poolRef(p)}>{poolLabel(p)}</option>{/each}</optgroup>{/if}
                    </select>
                  {:else}
                    <TagSelect bind:value={inp.src} {tags} onchange={() => inputTagChanged(inp)} />
                    {#if inp.src && tagKindOf(inp.src) !== 'bool'}
                      <select bind:value={inp.cmp} aria-label="Sammenligning">
                        {#if tagKindOf(inp.src) === 'unknown'}<option value="">er Til</option>{/if}
                        {#each Object.entries(CMP_TXT) as [v, t]}<option value={v}>{t}</option>{/each}
                      </select>
                      {#if inp.cmp}<input class="n" value={inp.value ?? ''} onchange={(e) => (inp.value = num2(e.currentTarget.value))} aria-label="Grænseværdi" />{/if}
                    {/if}
                  {/if}
                  <button class="small" onclick={() => b.inputs.splice(k, 1)} disabled={b.inputs.length <= 1} aria-label="Fjern indgang">✕</button>
                </div>
              {/each}
              <div class="row small"><button class="small" onclick={() => addInput(b)} disabled={b.inputs.length >= MAX_LOGIC_INPUTS}>+ Indgang ({b.inputs.length}/{MAX_LOGIC_INPUTS})</button>
                <span class="muted">{describeBlock(b)}</span></div>
            </div>
          {/each}
          <button class="small" onclick={addBlock} disabled={cfg.logic.length >= MAX_LOGIC}>+ Logikblok</button>
          <h4>Animationer ({cfg.anims.length}/{MAX_ANIMS})</h4>
          {#each cfg.anims as a, i}
            {@const kind = srcKind(a)}
            <div class="anim">
              <div class="row wrap">
                <select bind:value={a.part} onchange={() => resetParams(a)} aria-label="Del">
                  {#each partIds as p}<option value={p}>{partLabel(p, symbol)}</option>{/each}
                </select>
                <select bind:value={a.type} onchange={() => resetParams(a)} aria-label="Animation">
                  {#each typesFor(partInfo(a.part)) as t}<option value={t}>{ANIM_TXT[t]}</option>{/each}
                </select>
                <span class="small muted">styres af</span>
                {#if isPos || cfg.logic.length || pool.length}
                  <select value={srcMode(a)} onchange={(e) => setSrcMode(a, e.currentTarget.value)} aria-label="Kilde">
                    {#if isPos}<option value={POS}>symbolets position</option>{/if}<option value="tag">et tag</option>
                    {#if cfg.logic.length || pool.length}<option value="logic">en logikblok</option>{/if}
                  </select>
                {/if}
                {#if srcMode(a) === 'tag'}<TagSelect bind:value={a.src} {tags} onchange={() => resetParams(a)} />{/if}
                {#if srcMode(a) === 'logic'}
                  <select bind:value={a.src} onchange={() => resetParams(a)} aria-label="Logikblok">
                    {#if cfg.logic.length}<optgroup label="Dette symbol">{#each cfg.logic as b}<option value={'@' + b.id}>{blockLabel(b)}</option>{/each}</optgroup>{/if}
                    {#if pool.length}<optgroup label="Andre symboler">{#each pool as p}<option value={poolRef(p)}>{poolLabel(p)}</option>{/each}</optgroup>{/if}
                  </select>
                {/if}
                <span class="spacer"></span>
                <button class="small" onclick={() => moveAnim(i, -1)} disabled={i === 0} aria-label="Op">▲</button>
                <button class="small" onclick={() => moveAnim(i, 1)} disabled={i === cfg.anims.length - 1} aria-label="Ned">▼</button>
                <button class="small" onclick={() => cfg.anims.splice(i, 1)} aria-label="Fjern animation">✕</button>
              </div>
              {@render params(a, kind)}
              {#if isPos && a.src !== POS}
                <div class="row wrap small"><span class="muted">Gælder i:</span>
                  {#each cfg.positions as p, j}<label class="opt"><input type="checkbox" checked={a.only?.[j] ?? true} onchange={() => toggleOnly(a, j)} /> {p.label}</label>{/each}
                </div>
              {/if}
            </div>
          {/each}
          <button class="small" onclick={addAnim} disabled={cfg.anims.length >= MAX_ANIMS}>+ Animation</button>
        {:else if step === 4}
          {#if cfg.op === 'view'}
            <p class="muted small">Kun visning — intet at betjene.</p>
          {:else}
            <label class="opt"><input type="checkbox" bind:checked={cfg.confirm} /> Operatøren skal bekræfte før der skrives</label>
            {#if cfg.op === 'pulse'}
              <label class="field-row">Pulslængde (ms) <input class="n" type="number" min="100" max="10000" step="100" bind:value={cfg.pulse_ms} /></label>
            {/if}
            {#if isPos}
              <h4>Nøglelås</h4>
              <div class="row wrap small"><span class="muted">Låste positioner:</span>
                {#each cfg.positions as p, j}<label class="opt"><input type="checkbox" bind:checked={cfg.lock.positions[j]} /> {p.label}</label>{/each}
              </div>
              <label class="opt small"><input type="checkbox" bind:checked={cfg.lock.leave} disabled={!locks} /> Koden kræves også for at forlade en låst position</label>
              {#if locks}
                <label class="field-row">Kode (4 cifre){hasPin ? ' — en kode er sat; udfyld kun for at skifte den' : ''}
                  <input class="n pin" type="password" inputmode="numeric" autocomplete="new-password" maxlength="4" bind:value={pin} placeholder={hasPin ? '••••' : ''} />
                </label>
                {#if !pinOk}<p class="small error">Koden skal være præcis 4 cifre.</p>{/if}
                {#if exists && hasPin}<div class="row"><button class="small danger" onclick={clearPin}>Fjern kode</button></div>{/if}
                <p class="small muted">Koden gemmes kun som hash og kommer ikke med i backup — efter en gendannelse skal den sættes igen.</p>
              {:else if exists && hasPin}
                <p class="small muted">Der er en kode, men ingen låste positioner. <button class="small danger" onclick={clearPin}>Fjern kode</button></p>
              {/if}
            {/if}
          {/if}
        {:else if step === 5}
          {#if cfg.signals.some((s) => s.tag)}
            <h4>Live</h4>
            <table class="grid">
              <thead><tr><th>Signal</th><th>Kommando</th><th>Tilbagemelding</th></tr></thead>
              <tbody>
                {#each cfg.signals.filter((s) => s.tag) as s}
                  <tr><td>{s.id}</td><td>{s.tag}: <strong>{fmt(valueOf(s.tag))}</strong></td><td>{s.fb ? `${s.fb}: ` : '—'}{#if s.fb}<strong>{fmt(valueOf(s.fb))}</strong>{/if}</td></tr>
                {/each}
              </tbody>
            </table>
            {#if isPos}<p class="small">PLC'ens position lige nu: <strong>{found !== null ? cfg.positions[found].label : 'ingen entydig position'}</strong></p>{/if}
          {/if}
          {#if cfg.logic.length}
            <h4>Logik (live)</h4>
            <table class="grid">
              <tbody>
                {#each cfg.logic as b}<tr><td><strong>{b.id}</strong> {b.name}</td><td class="small">{describeBlock(b)}</td><td><strong>{triText(logicNow[b.id])}</strong></td></tr>{/each}
              </tbody>
            </table>
          {/if}
          {#if preview?.plans.length}
            <h4>Skriveplan pr. position (fra den aktuelle tilstand)</h4>
            <table class="grid">
              <tbody>
                {#each preview.plans as pl}<tr><td><strong>{pl.label}</strong></td><td class="small">{pl.writes.map(writeText).join(' → ') || 'intet at skrive'}</td></tr>{/each}
              </tbody>
            </table>
          {/if}
        {/if}

        {#if stepErrors(step).length}
          <ul class="errors small">{#each stepErrors(step) as m}<li>{m}</li>{/each}</ul>
        {/if}
        {#if step === 5}
          {#each [1, 2, 3, 4] as k}
            {#if stepErrors(k).length}<p class="small error">Trin {k + 1} ({STEPS[k]}): {stepErrors(k).join(' ')}</p>{/if}
          {/each}
          {#if preview?.warnings.length}<ul class="warnings small">{#each preview.warnings as w}<li>{w}</li>{/each}</ul>{/if}
        {/if}
        {#if previewError}<p class="small error">Kontrol fejlede: {previewError}</p>{/if}
        {#if error}<p class="error">{error}</p>{/if}
      </div>

      <footer class="row">
        {#if exists}<button class="danger" onclick={remove} disabled={saving}>Fjern konfiguration</button>{/if}
        <span class="spacer"></span>
        <span class="small muted">{checking ? 'Kontrollerer…' : preview ? (preview.errors || needPin ? `${preview.errors + (needPin ? 1 : 0)} fejl` : 'Ingen fejl') : 'Kontrollerer…'}</span>
        <button onclick={() => (step = Math.max(0, step - 1 - (!isPos && step === 3 ? 1 : 0)))} disabled={step === 0}>Tilbage</button>
        {#if step < 5}
          <button onclick={() => (step = Math.min(5, step + 1 + (!isPos && step === 1 ? 1 : 0)))}>Næste</button>
        {:else}
          <button class="primary" onclick={save} disabled={!canSave}>{saving ? 'Gemmer…' : 'Gem'}</button>
        {/if}
      </footer>
    {/if}
  </div>
</div>

{#snippet colorInput(obj: Record<string, any>, key: string | number, label: string)}
  <label class="opt small"><input type="color" bind:value={obj[key]} /> {label}</label>
{/snippet}

{#snippet numInput(obj: Record<string, any>, key: string | number, label: string)}
  <label class="opt small">{label} <input class="n" value={obj[key] ?? ''} onchange={(e) => (obj[key] = num(e.currentTarget.value, obj[key] ?? 0))} /></label>
{/snippet}

{#snippet params(a: Anim, kind: SrcKind)}
  {@const p = a.params}
  <div class="row wrap params">
    {#if (a.type === 'fill' || a.type === 'stroke')}
      {#if kind === 'pos'}
        {#each cfg.positions as pos, j}{@render colorInput(p.colors, j, pos.label)}{/each}
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
    {:else if a.type === 'blink' || a.type === 'visible' || a.type === 'spin'}
      {#if kind === 'pos'}
        {#each cfg.positions as pos, j}<label class="opt small"><input type="checkbox" bind:checked={p.set[j]} /> {pos.label}</label>{/each}
      {:else if kind === 'num'}
        {@render numInput(p, 'at_least', 'Når ≥')}
      {:else}
        <label class="opt small"><input type="checkbox" bind:checked={p.invert} /> Omvendt (når Fra)</label>
      {/if}
      {#if a.type === 'blink'}
        <select bind:value={p.speed} aria-label="Blinkfrekvens">{#each Object.entries(BLINK_TXT) as [v, t]}<option value={v}>{t}</option>{/each}</select>
      {/if}
    {:else if a.type === 'level' || a.type === 'opacity'}
      {@render numInput(p, 'min', 'Min')}{@render numInput(p, 'max', 'Max')}
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
      {/if}
    {:else if a.type === 'rotate'}
      {#if kind === 'pos'}
        {#each cfg.positions as pos, j}{@render numInput(p.angles, j, `${pos.label} °`)}{/each}
      {:else}
        {@render numInput(p, 'min', 'Min')}{@render numInput(p, 'max', 'Max')}{@render numInput(p, 'angle_min', '° ved min')}{@render numInput(p, 'angle_max', '° ved max')}
      {/if}
    {:else if a.type === 'move'}
      {#if kind === 'pos'}
        {#each cfg.positions as pos, j}<span class="opt small">{pos.label} {@render numInput(p.dxs, j, 'x')}{@render numInput(p.dys, j, 'y')}</span>{/each}
      {:else}
        {@render numInput(p, 'min', 'Min')}{@render numInput(p, 'max', 'Max')}{@render numInput(p, 'dx', 'x ved max')}{@render numInput(p, 'dy', 'y ved max')}
      {/if}
    {:else if a.type === 'flow'}
      {#if kind === 'pos'}
        {#each cfg.positions as pos, j}
          <label class="opt small">{pos.label} <select bind:value={p.dirs[j]}><option value={0}>stop</option><option value={1}>frem</option><option value={-1}>tilbage</option></select></label>
        {/each}
      {:else}
        <select bind:value={p.mode} aria-label="Styring"><option value="onoff">Til/fra</option><option value="signed">Fortegn (+/−)</option><option value="code">Kode 0/1/2</option></select>
        <label class="opt small">Retning fra
          {#if cfg.logic.length || pool.length}
            <select value={isLogicRef(p.dir_tag ?? '') ? 'logic' : 'tag'} onchange={(e) => (p.dir_tag = e.currentTarget.value === 'logic' ? firstBlockRef(cfg.logic) : '')} aria-label="Retningens kilde">
              <option value="tag">et tag</option><option value="logic">en logikblok</option>
            </select>
          {/if}
          {#if isLogicRef(p.dir_tag ?? '')}
            <select bind:value={p.dir_tag} aria-label="Retningens logikblok">
              {#if cfg.logic.length}<optgroup label="Dette symbol">{#each cfg.logic as b}<option value={'@' + b.id}>{blockLabel(b)}</option>{/each}</optgroup>{/if}
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
{/snippet}

<style>
  .backdrop { position: fixed; inset: 0; background: rgba(0, 0, 0, .35); display: flex; align-items: flex-start; justify-content: center; padding: 4vh 16px 0; z-index: 20; }
  .guide { width: 100%; max-width: 960px; max-height: 92vh; display: flex; flex-direction: column; box-shadow: 0 8px 30px rgba(0, 0, 0, .25); }
  .head { align-items: baseline; gap: .6rem; }
  .head h2 { margin: 0; font-size: 1.15rem; }
  .close { margin-left: auto; }
  .steps { display: flex; flex-wrap: wrap; gap: .25rem; margin: .6rem 0; border-bottom: 1px solid var(--line); padding-bottom: .4rem; }
  .steps button { position: relative; }
  .steps button.active { background: var(--accent); color: #fff; border-color: var(--accent); }
  .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--alarm); margin-left: .35rem; vertical-align: middle; }
  .body { overflow: auto; flex: 1; min-height: 240px; padding-right: .3rem; }
  .body h4 { margin: .8rem 0 .3rem; }
  footer { gap: .5rem; align-items: center; border-top: 1px solid var(--line); padding-top: .5rem; margin-top: .5rem; }
  .spacer { flex: 1; }
  .ops { display: flex; flex-wrap: wrap; gap: .4rem 1.2rem; margin: .4rem 0 .8rem; }
  .opt { display: inline-flex; align-items: center; gap: .3rem; }
  .wrap { flex-wrap: wrap; gap: .35rem .6rem; align-items: center; }
  .grid { border-collapse: collapse; margin: .3rem 0; }
  .grid th, .grid td { border: 1px solid var(--line); padding: .2rem .35rem; text-align: left; }
  /* En tag-dropdown er ellers lige så bred som sin længste valgmulighed ("navn · kilde (type) [enhed]") og presser nabokolonnerne */
  .grid :global(select), .anim :global(select) { width: auto; max-width: 15em; }   /* :global — TagSelect er en underkomponent */
  .grid td.skriv { min-width: 13em; }
  .planes td, .planes th { text-align: center; }
  .n { width: 5.5em; }
  .lbl { width: 7em; }
  .pin { letter-spacing: .3em; }
  .pos { display: inline-flex; gap: .15rem; }
  .cell { min-width: 3.2em; }
  .cell.on { background: #c8e6c9; border-color: var(--ok); }
  .cell.off { background: #eeeeee; }
  .active-row td { background: var(--panel-2); }
  .name { min-width: 14em; }
  .logic .input { margin: .15rem 0 .15rem 1rem; }
  .anim { border: 1px solid var(--line); border-radius: var(--radius); padding: .4rem; margin: .35rem 0; background: var(--panel-2); }
  .params { margin-top: .3rem; }
  .errors { color: var(--alarm); margin: .5rem 0; }
  .warnings { color: var(--warn); }
  .notice { background: #fff8e1; border: 1px solid #ffe082; padding: .4rem .6rem; border-radius: var(--radius); }
  .notice ul { margin: .2rem 0 0 1rem; padding: 0; }
  .danger { color: var(--alarm); }
  .error { color: var(--alarm); }
  .field-row { display: flex; flex-direction: column; gap: .2rem; margin: .3rem 0; }
</style>
