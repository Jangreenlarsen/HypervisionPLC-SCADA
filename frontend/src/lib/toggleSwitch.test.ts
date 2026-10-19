import { describe, expect, it } from 'vitest';
import { applyLever, defaultDirs, leverAnims, leverDirs, leverInSync } from './toggleSwitch';
import type { Anim } from './symbolConfig';

const G = 'v_greb', K = 'v_knop';

describe('vippekontaktens greb pr. position (v0.97.2)', () => {
  it('standard', () => {
    expect(defaultDirs(2, false)).toEqual(['down', 'up']);
    expect(defaultDirs(3, true)).toEqual(['up', 'mid', 'down']);
    expect(defaultDirs(3, false)).toEqual(['up', 'down', 'up']);
  });

  it('Op / Midt / Ned → Drej, grebet skjult og knoppen vist i Midt', () => {
    expect(leverAnims(G, K, ['up', 'mid', 'down'])).toEqual([
      { part: G, type: 'rotate', src: '@pos', params: { angles: [180, 180, 0] }, only: null },
      { part: G, type: 'visible', src: '@pos', params: { set: [true, false, true] }, only: null },
      { part: K, type: 'visible', src: '@pos', params: { set: [false, true, false] }, only: null },
    ]);
    expect(leverAnims(G, null, ['down', 'up'])).toEqual([{ part: G, type: 'rotate', src: '@pos', params: { angles: [0, 180] }, only: null }]);
  });

  it('læser stillingerne tilbage — også Jans håndlavede opsætning (180/90/0° og synlig efter en logikblok)', () => {
    expect(leverDirs(leverAnims(G, K, ['mid', 'up', 'down']), G, K, 3)).toEqual(['mid', 'up', 'down']);
    const jan: Anim[] = [
      { part: G, type: 'rotate', src: '@pos', params: { angles: [180, 90, 0] }, only: null },
      { part: G, type: 'visible', src: '@L1', params: {}, only: null },
    ];
    expect(leverDirs(jan, G, K, 3)).toEqual(['up', 'mid', 'down']);
    expect(leverInSync(jan, G, K, 3)).toBe(false);
    expect(leverDirs([], G, K, 3)).toEqual(['up', 'mid', 'down']);   // ingen animationer: standarden
  });

  it('anvend: grebets og knoppens Drej/Synlig erstattes, resten og hastigheden bevares', () => {
    const anims: Anim[] = [
      { part: G, type: 'rotate', src: '@pos', params: { angles: [180, 90, 0], glide_s: 1 }, only: null },
      { part: G, type: 'visible', src: '@L1', params: {}, only: null },
      { part: 'v', type: 'fill', src: 'Tag', params: { on: '#0f0', off: '#999' }, only: null },
    ];
    const out = applyLever(anims, G, K, ['up', 'mid', 'down']);
    expect(out).toHaveLength(4);
    expect(out[0].params).toEqual({ angles: [180, 180, 0], glide_s: 1 });
    expect(out.map((a) => `${a.part}:${a.type}:${a.src}`)).toEqual([`${G}:rotate:@pos`, `${G}:visible:@pos`, `${K}:visible:@pos`, 'v:fill:Tag']);
    expect(leverInSync(out, G, K, 3)).toBe(true);
  });
});
