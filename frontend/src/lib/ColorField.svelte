<script lang="ts">
  // Farvefelt til Symboltest: farveprøve, vælger, hex-felt og bibliotekets palette (klik på en farve for at bruge den).
  import { PALETTE, isColor, toHex6 } from './symbolSim';

  let { value, onchange, label = '' }: { value: string; onchange: (color: string) => void; label?: string } = $props();
  let open = $state(false);
  let invalid = $state(false);   // den skrevne kode er ikke en farve — symbolet beholder den gamle
</script>

<span class="cf">
  <button type="button" class="sw current" style="background:{value || 'transparent'}" title="{value || 'ingen farve'} — vis paletten"
          aria-label="Palette for {label || 'farve'}" aria-expanded={open} onclick={() => (open = !open)}></button>
  <input type="color" value={toHex6(value)} oninput={(e) => onchange(e.currentTarget.value)} aria-label="Vælg {label || 'farve'}" />
  <input type="text" class="hex" class:invalid value={value} maxlength="24" spellcheck="false" aria-label="Farvekode for {label || 'farve'}"
         title={invalid ? 'Ikke en farve — skriv fx #2e7d32 eller red' : ''} aria-invalid={invalid}
         oninput={(e) => { const v = e.currentTarget.value.trim(); invalid = false; if (isColor(v)) onchange(v); }}
         onchange={(e) => {
           const v = e.currentTarget.value.trim();
           if (isColor(v)) { invalid = false; onchange(v); } else { invalid = true; e.currentTarget.value = value; }
         }} />
  {#if open}
    <span class="pal" role="listbox" aria-label="Palette">
      {#each PALETTE as c}
        <button type="button" class="sw" class:on={c.toLowerCase() === (value ?? '').toLowerCase()} style="background:{c}" title={c} aria-label={c}
                onclick={() => { onchange(c); open = false; }}></button>
      {/each}
    </span>
  {/if}
</span>

<style>
  .cf { display: inline-flex; align-items: center; gap: 4px; flex-wrap: wrap; position: relative; }
  .sw { width: 20px; height: 20px; padding: 0; border: 1px solid var(--line); border-radius: 3px; cursor: pointer; }
  .sw.on { outline: 2px solid var(--accent); outline-offset: 1px; }
  .current { width: 24px; height: 24px; }
  input[type='color'] { width: 28px; height: 24px; padding: 0; border: 1px solid var(--line); background: none; }
  .hex { width: 6.5em; font-family: monospace; }
  .hex.invalid { border-color: var(--alarm, #c62828); outline: 1px solid var(--alarm, #c62828); }
  .pal { display: flex; flex-wrap: wrap; gap: 3px; max-width: 280px; padding: 6px; border: 1px solid var(--line); background: var(--panel); border-radius: 4px; flex-basis: 100%; }
</style>
