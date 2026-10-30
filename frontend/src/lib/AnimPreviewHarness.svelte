<script lang="ts">
  // Kun til AnimPreviewPanel.test.ts: holder opsætningen i $state, som guiden gør, så ændringer i den kan prøves.
  import AnimPreview from './AnimPreview.svelte';
  import { emptyConfig, type Anim, type SymbolConfig } from './symbolConfig';

  let { anims, svg, element }: { anims: Anim[]; svg: string; element: string } = $props();
  // svelte-ignore state_referenced_locally — kun startværdien bruges (testen ændrer opsætningen bagefter)
  const cfg = $state<SymbolConfig>({ ...emptyConfig('pumpe'), anims: structuredClone(anims) });
  export const setOn = (color: string): void => { cfg.anims[0].params.on = color; };
  export const clear = (): void => { cfg.anims = []; };
</script>

<AnimPreview {cfg} {element} {svg} kindOf={() => 'bool'} metaOf={() => undefined} />
