<script lang="ts">
  // "Erstat med symbol": vælg hvilket bibliotekssymbol den markerede tegnede del skal erstattes af. Forslag ud fra delens
  // form (symbolSuggest.ts), eller søg i hele biblioteket. Selve erstatningen sker i Tegn (host-API'et), i ét fortryd-trin.
  import { CATEGORIES, previewViewBox, PIPE_IDS, SYMBOLS, type SymbolDef } from './symbols';
  import { hasTextSlot, nameHint, stretchesByDefault, suggestSymbols, type SelectionInfo } from './symbolSuggest';

  export type SimilarMode = false | 'same' | 'any';
  export interface ReplaceOptions { symbol: SymbolDef; name: string; keepId: boolean; stretch: boolean; useText: boolean; similar: SimilarMode }

  let { info, lostBindings, onreplace, onclose }: {
    info: SelectionInfo;
    lostBindings: { own: number; similar: number };   // bindinger på delens underelementer/tekster (og på de lignende dele), som ikke følger med
    onreplace: (opts: ReplaceOptions) => void;
    onclose: () => void;
  } = $props();

  let query = $state('');
  let chosen = $state<SymbolDef | null>(null);
  let name = $state('');
  let keepId = $state(true);
  let stretch = $state(false);
  let useText = $state(true);
  let similar = $state<'none' | 'same' | 'any'>('same');

  const byId = new Map(SYMBOLS.map((s) => [s.id, s]));
  const suggestions = $derived(suggestSymbols(info).flatMap((x) => (byId.has(x.id) ? [{ ...x, symbol: byId.get(x.id)! }] : [])));
  const found = $derived.by(() => {
    const q = query.trim().toLowerCase();
    if (q.length < 2) return [];
    return SYMBOLS.filter((s) => s.label.toLowerCase().includes(q) || s.hint.toLowerCase().includes(q) || s.id.includes(q));
  });
  const lost = $derived(lostBindings.own + (similar === 'none' ? 0 : lostBindings.similar));
  const slot = $derived(!!chosen && hasTextSlot(chosen.svg) && info.texts.length > 0);

  function choose(s: SymbolDef): void {
    chosen = s;
    name = nameHint(info, s.label);
    stretch = stretchesByDefault(s.id);
    useText = true;
  }

  /** Forhåndsvisning: viewBox efter symbolets egen størrelse (som i paletten). */
  const fit = (id: string) => (svg: SVGSVGElement): void => {
    try {
      svg.setAttribute('viewBox', previewViewBox((svg.firstElementChild as SVGGraphicsElement).getBBox(), PIPE_IDS.has(id)));
    } catch {
      // getBBox kan fejle hvis knappen er skjult — standard-viewBox bruges så
    }
  };

  const describe = $derived(
    `${info.tag === 'g' ? 'gruppe' : info.tag} · ${Math.round(info.w)} × ${Math.round(info.h)}${info.angle ? ` · drejet ${Math.round(info.angle)}°` : ''}` +
    `${info.texts.length ? ` · tekst: ${info.texts.slice(0, 3).join(', ')}` : ''}`,
  );

  function go(): void {
    if (chosen) onreplace({ symbol: chosen, name: name.trim(), keepId, stretch, useText: slot && useText, similar: similar === 'none' ? false : similar });
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={onclose}>
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="panel dlg" role="dialog" aria-modal="true" aria-label="Erstat med symbol" tabindex="-1" onclick={(e) => e.stopPropagation()}>
    <header class="row head">
      <h2>Erstat med symbol</h2>
      <span class="muted small">{describe}</span>
      <button class="close" onclick={onclose} aria-label="Luk">✕</button>
    </header>

    <div class="body">
      {#if suggestions.length}
        <h4>Forslag ud fra delens form</h4>
        <div class="grid">
          {#each suggestions.slice(0, 6) as g (g.id)}
            <button class="sym" class:sel={chosen?.id === g.id} onclick={() => choose(g.symbol)} title={g.why}>
              <svg viewBox="-4 -4 168 152" aria-hidden="true" {@attach fit(g.id)}>{@html g.symbol.svg}</svg>
              <span>{g.symbol.label}</span>
              <span class="why muted">{g.why}</span>
            </button>
          {/each}
        </div>
      {:else}
        <p class="muted small">Ingen forslag til denne del — søg i biblioteket nedenfor.</p>
      {/if}

      <h4>Eller søg i hele biblioteket</h4>
      <input bind:value={query} placeholder="Søg symbol (fx pumpe, bøjning, kontaktor)" style="width:100%" />
      {#if query.trim().length >= 2}
        {#if found.length}
          <div class="grid">
            {#each found.slice(0, 12) as s (s.id)}
              <button class="sym" class:sel={chosen?.id === s.id} onclick={() => choose(s)} title={s.hint}>
                <svg viewBox="-4 -4 168 152" aria-hidden="true" {@attach fit(s.id)}>{@html s.svg}</svg>
                <span>{s.label}</span>
                <span class="why muted">{CATEGORIES.find((c) => c.id === s.category)?.label ?? ''}</span>
              </button>
            {/each}
          </div>
        {:else}<p class="muted small">Ingen symboler matcher "{query}".</p>{/if}
      {/if}

      {#if chosen}
        <h4>Indstillinger for «{chosen.label}»</h4>
        <label class="field">Navn
          <input bind:value={name} maxlength="60" />
        </label>
        <label class="opt"><input type="checkbox" bind:checked={keepId} /> Behold delens id{info.id ? ` (${info.id})` : ''} — så bindinger på selve delen følger med</label>
        {#if slot}<label class="opt"><input type="checkbox" bind:checked={useText} /> Overtag den tegnede tekst ({info.texts[0]}) og fjern den gamle</label>{/if}
        <label class="opt"><input type="checkbox" bind:checked={stretch} /> Stræk symbolet til at fylde delens boks (ellers beholdes proportionerne)</label>
        {#if info.similarAny > 0}
          <fieldset class="similar">
            <legend class="small">Andre dele af samme slags</legend>
            <label class="opt"><input type="radio" name="similar" value="none" bind:group={similar} /> Kun denne del</label>
            {#if info.similar > 0}
              <label class="opt"><input type="radio" name="similar" value="same" bind:group={similar} /> Også de <strong>{info.similar}</strong> lignende (samme opbygning og størrelse)</label>
            {/if}
            {#if info.similarAny > info.similar}
              <label class="opt"><input type="radio" name="similar" value="any" bind:group={similar} /> Alle <strong>{info.similarAny}</strong> af samme slags, uanset størrelse (fx etiketter med forskellig tekstlængde)</label>
            {/if}
          </fieldset>
        {/if}
        {#if lost > 0}
          <p class="small warn">⚠ {lost} binding{lost === 1 ? '' : 'er'} sidder på underelementer eller tekster i de dele der erstattes og følger <strong>ikke</strong> med — sæt dem op igen i guiden bagefter.</p>
        {/if}
        <p class="small muted">Symbolet får samme midte, størrelse og drejning som delen. Det er ét fortryd-trin (Ctrl+Z), og tegningen gemmes først, når du trykker <em>Gem kladde</em>.</p>
      {/if}
    </div>

    <footer class="row">
      <span class="spacer"></span>
      <button onclick={onclose}>Annullér</button>
      <button class="primary" onclick={go} disabled={!chosen}>Erstat</button>
    </footer>
  </div>
</div>

<style>
  .backdrop { position: fixed; inset: 0; background: rgba(0, 0, 0, .35); display: flex; align-items: flex-start; justify-content: center; padding: 4vh 16px 0; z-index: 20; }
  .dlg { width: 100%; max-width: 820px; max-height: 92vh; display: flex; flex-direction: column; box-shadow: 0 8px 30px rgba(0, 0, 0, .25); }
  .head { align-items: baseline; gap: .8rem; }
  .head h2 { margin: 0; }
  .close { margin-left: auto; }
  .body { overflow-y: auto; padding: .2rem 0 .4rem; }
  h4 { margin: .8rem 0 .3rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: .45rem; }
  .sym { display: flex; flex-direction: column; align-items: center; gap: .2rem; padding: .4rem; text-align: center; font-size: .8rem; line-height: 1.15; }
  .sym svg { width: 64px; height: 56px; }
  .sym.sel { outline: 2px solid var(--accent); background: var(--panel-2); }
  .why { font-size: .7rem; }
  .similar { border: 1px solid var(--line); border-radius: var(--radius); margin: .5rem 0; padding: .2rem .6rem .4rem; }
  .opt { display: flex; gap: .4rem; align-items: baseline; margin: .25rem 0; }
  .warn { color: #8a4b00; background: #fff4e0; border: 1px solid #f0c27a; border-radius: var(--radius); padding: .35rem .6rem; }
  footer { margin-top: .6rem; padding-top: .6rem; border-top: 1px solid var(--line); }
  .spacer { flex: 1; }
</style>
