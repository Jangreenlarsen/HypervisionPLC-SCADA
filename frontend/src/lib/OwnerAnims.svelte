<script lang="ts">
  // Skrivebeskyttet oversigt over animationer på et symbol, som ejes af andre end den der redigeres (v0.131.0):
  // symbolets egne i neutral farve, hver gruppes i gruppens farve med gruppens navn — så man kan se, hvad man ikke skal røre.
  import { ANIM_TXT, ON, parseAlarmRef, parseValRef, partLabel, type AnimType, type SymbolInfo } from './symbolConfig';
  import type { OwnerBlock } from './symbolGroups';

  let { owners, symbol = null, title = 'Andre animationer på symbolet (kan ikke ændres her)' }: {
    owners: OwnerBlock[]; symbol?: SymbolInfo | null; title?: string;
  } = $props();

  const srcText = (src: string): string => {
    if (src === ON) return 'altid til';
    if (src === '@pos') return 'symbolets position';
    const val = parseValRef(src);
    if (val !== null) return `fast værdi ${val}`;
    const al = parseAlarmRef(src);
    if (al) return `alarm ${al.kind === 'unack' ? 'ukvitteret' : 'aktiv'} på ${al.tag}`;
    return src || '(intet tag valgt)';
  };
</script>

{#if owners.some((o) => o.anims.length)}
  <div class="owners">
    <h4>{title}</h4>
    {#each owners as o (o.key)}
      {#if o.anims.length}
        <div class="owner" style:--c={o.color ?? '#777'}>
          <span class="tag" class:own={!o.color}>{o.label}</span>
          {#each o.anims as a}
            <div class="row small">
              {partLabel(a.part, symbol)}: <strong>{ANIM_TXT[a.type as AnimType] ?? a.type}</strong>
              <span class="muted">← {srcText(a.src)}</span>
            </div>
          {/each}
        </div>
      {/if}
    {/each}
  </div>
{/if}

<style>
  .owners { margin: .6rem 0; }
  .owners h4 { margin: 0 0 .3rem; }
  .owner { border: 1px solid var(--c); border-left-width: 5px; border-radius: var(--radius); padding: .25rem .5rem; margin: .25rem 0; opacity: .85; background: color-mix(in srgb, var(--c) 8%, transparent); }
  .tag { display: inline-block; font-weight: 600; font-size: .8rem; color: var(--c); margin-bottom: .1rem; }
  .tag.own { color: var(--muted); }
</style>
