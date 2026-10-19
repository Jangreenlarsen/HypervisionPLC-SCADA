import { describe, expect, it } from 'vitest';
import { selectorMismatch, withSelectorAngles } from './selectorRedraw';
import { emptyConfig } from './symbolConfig';
import { selectorAngles } from './symbols';

describe('omskifterens tegning følger opsætningen (v0.91.1)', () => {
  it('forskel i antal eller navne; mellemrum ignoreres; under 2 positioner = ingen forskel', () => {
    expect(selectorMismatch(['Hånd', '0', 'Auto'], ['Hånd', '0', 'Auto', 'Service'])).toBe(true);
    expect(selectorMismatch(['Hånd', '0', 'Auto'], ['Manuel', '0', 'Auto'])).toBe(true);
    expect(selectorMismatch(['Hånd', '0', 'Auto'], [' Hånd', '0 ', 'Auto'])).toBe(false);
    expect(selectorMismatch(['0', '1'], [])).toBe(false);
  });

  it('grebets vinkler pr. position følger den nye tegning, og animationen flyttes til det nye greb', () => {
    const cfg = emptyConfig('omskifter3');
    cfg.op = 'positions';
    cfg.positions = ['Hånd', '0', 'Auto', 'Service', 'Test'].map((label) => ({ label }));
    cfg.anims = [
      { part: 'o_greb', type: 'rotate', src: '@pos', params: { angles: [-45, 0, 45, 0, 0] }, only: null },
      { part: 'all', type: 'fill', src: '@pos', params: { colors: ['#a', '#b', '#c', '#d', '#e'] }, only: null },
      { part: 'o_greb', type: 'rotate', src: 'Tag', params: { min: 0, max: 1 }, only: null },
    ];
    const out = withSelectorAngles(cfg, 'o_greb_2', 'o_greb');
    expect(out.anims[0]).toMatchObject({ part: 'o_greb_2', params: { angles: selectorAngles(5) } });
    expect(selectorAngles(5)).toEqual([-90, -45, 0, 45, 90]);
    expect(out.anims[1]).toBe(cfg.anims[1]);                   // andre animationer røres ikke
    expect(out.anims[2]).toBe(cfg.anims[2]);                   // drej efter et tag (ikke positionen) røres ikke
    expect(cfg.anims[0].params.angles).toEqual([-45, 0, 45, 0, 0]);   // originalen er uændret
  });
});
