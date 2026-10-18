<script lang="ts">
  // Knappen "← Tilbage til <tegning>" øverst på Alarmer, Trends og Energi (v0.76.0).
  import { onMount } from 'svelte';
  import { get } from './api';
  import { backTarget, lastDrawing } from './backToDrawing';

  let target = $state(backTarget(null, null));
  onMount(async () => {
    const last = lastDrawing();
    if (!last) return;
    try {
      target = backTarget(last, await get<{ id: string; name: string }[]>('/api/drawings'));
    } catch {
      // tegningslisten kunne ikke hentes: knappen går til Overview (som er det, den viser i forvejen)
    }
  });
</script>

<a class="btn back" href={target.href}>← {target.label}</a>

<style>
  .back { white-space: nowrap; }
</style>
