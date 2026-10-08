<script lang="ts">
  // Ugeoversigt: én række pr. dag (man–søn), 00–24, farvet efter værdien. Data beregnes af serveren.
  import { fmtValue, textOn, valueColor } from './scheduleUi';

  interface Seg { from: number; to: number; value: number | null }
  let { week, isBool, unit = '', compact = false }: {
    week: { day: string; date: string; segments: Seg[] }[];
    isBool: boolean;
    unit?: string;
    compact?: boolean;
  } = $props();

  const all = $derived(week.flatMap((d) => d.segments.map((s) => s.value)));
  const hhmm = (m: number) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
  const today = new Date().toISOString().slice(0, 10);
</script>

<div class="week" class:compact>
  {#if !compact}
    <div class="row-h"><span></span><div class="hours">{#each [0, 6, 12, 18, 24] as h}<span style="left:{(h / 24) * 100}%">{h}</span>{/each}</div></div>
  {/if}
  {#each week as d}
    <div class="row-h" class:today={d.date === today}>
      <span class="day">{d.day}</span>
      <div class="track">
        {#each d.segments as s}
          {@const bg = valueColor(s.value, isBool, all)}
          <div class="seg" class:none={s.value === null} style="left:{(s.from / 1440) * 100}%;width:{((s.to - s.from) / 1440) * 100}%;background:{bg};color:{textOn(bg)}"
            title="{d.day} {hhmm(s.from)}–{hhmm(s.to)}: {fmtValue(s.value, isBool, unit)}">
            {#if !compact && s.to - s.from >= 150}{fmtValue(s.value, isBool, unit)}{/if}
          </div>
        {/each}
      </div>
    </div>
  {/each}
</div>

<style>
  .week { display: grid; gap: 3px; font-size: .75rem; }
  .row-h { display: grid; grid-template-columns: 2.2rem 1fr; align-items: center; gap: .4rem; }
  .day { color: var(--muted); text-transform: capitalize; }
  .today .day { color: var(--text); font-weight: 600; }
  .track { position: relative; height: 22px; background: repeating-linear-gradient(45deg, #f4f4f2, #f4f4f2 4px, #ebebe8 4px, #ebebe8 8px); border-radius: 3px; overflow: hidden; }
  .compact .track { height: 10px; }
  .seg { position: absolute; top: 0; bottom: 0; display: flex; align-items: center; justify-content: center; white-space: nowrap; overflow: hidden; border-right: 1px solid #fff; }
  .seg.none { background: transparent !important; }
  .hours { position: relative; height: 1rem; color: var(--muted); }
  .hours span { position: absolute; transform: translateX(-50%); }
  .hours span:first-child { transform: none; }
  .hours span:last-child { transform: translateX(-100%); }
</style>
