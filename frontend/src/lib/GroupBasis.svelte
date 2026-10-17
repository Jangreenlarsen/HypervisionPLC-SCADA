<script lang="ts">
  // "Opsæt de valgte samlet" (v0.63.0): de valgte symboler har forskellige opsætninger — vælg den, der er udgangspunktet.
  import { memberNames, type ConfigGroup, type Member } from './symbolCopy';

  let { groups, unconfigured, unnamed = 0, onpick, onclose }: {
    groups: ConfigGroup[]; unconfigured: Member[]; unnamed?: number;
    onpick: (m: Member) => void; onclose: () => void;
  } = $props();

  let chosen = $state(0);
  const total = $derived(groups.reduce((n, g) => n + g.members.length, 0) + unconfigured.length + unnamed);
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={onclose}>
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="panel dlg" role="dialog" aria-modal="true" aria-label="Vælg udgangspunkt" tabindex="-1" onclick={(e) => e.stopPropagation()}>
    <header class="row head">
      <h2>Vælg udgangspunkt</h2>
      <span class="muted small">{total} symboler valgt</span>
      <button class="close" onclick={onclose} aria-label="Luk">✕</button>
    </header>

    <p class="small">De valgte symboler har <strong>{groups.length} forskellige opsætninger</strong>. Vælg den, du vil redigere — når du gemmer i guiden, får <strong>alle {total}</strong> den.</p>
    <div class="list" role="radiogroup" aria-label="Opsætninger">
      {#each groups as g, i (g.key)}
        <label class="opt" class:sel={chosen === i}>
          <input type="radio" name="basis" value={i} bind:group={chosen} />
          <span>
            <strong>{g.summary}</strong>
            <span class="small muted">{g.members.length === 1 ? '1 symbol' : `${g.members.length} symboler`}: {memberNames(g.members)}</span>
          </span>
        </label>
      {/each}
    </div>
    {#if unconfigured.length}<p class="small muted">{unconfigured.length === 1 ? '1 af de valgte har' : `${unconfigured.length} af de valgte har`} ingen opsætning ({memberNames(unconfigured)}) og får også den valgte.</p>{/if}
    {#if unnamed}<p class="small muted">{unnamed === 1 ? '1 valgt element' : `${unnamed} valgte elementer`} uden navn navngives efter udgangspunktet (fx "{groups[chosen].members[0].name}_1") og får også den valgte.</p>{/if}
    <p class="small warn">⚠ De andre opsætninger erstattes, når du gemmer. Indtil da er intet ændret.</p>

    <footer class="row">
      <span class="spacer"></span>
      <button onclick={onclose}>Annullér</button>
      <button class="primary" onclick={() => onpick(groups[chosen].members[0])}>Rediger denne</button>
    </footer>
  </div>
</div>

<style>
  .backdrop { position: fixed; inset: 0; background: rgba(0, 0, 0, .35); display: flex; align-items: flex-start; justify-content: center; padding: 8vh 16px 0; z-index: 20; }
  .dlg { width: 100%; max-width: 600px; max-height: 84vh; display: flex; flex-direction: column; overflow-y: auto; box-shadow: 0 8px 30px rgba(0, 0, 0, .25); }
  .head { align-items: baseline; gap: .8rem; }
  .head h2 { margin: 0; }
  .close { margin-left: auto; }
  .list { display: flex; flex-direction: column; gap: .35rem; margin: .4rem 0; }
  .opt { display: flex; gap: .55rem; align-items: baseline; padding: .45rem .6rem; border: 1px solid var(--line); border-radius: var(--radius); cursor: pointer; }
  .opt.sel { outline: 2px solid var(--accent); background: var(--panel-2); }
  .opt > span { display: flex; flex-direction: column; gap: .1rem; min-width: 0; overflow-wrap: anywhere; }
  .warn { color: #8a4b00; background: #fff4e0; border: 1px solid #f0c27a; border-radius: var(--radius); padding: .35rem .6rem; }
  footer { margin-top: .6rem; padding-top: .6rem; border-top: 1px solid var(--line); }
  .spacer { flex: 1; }
</style>
