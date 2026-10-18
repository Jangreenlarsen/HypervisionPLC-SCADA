import { describe, expect, it } from 'vitest';
import { mergeMoved, orphanGroups } from './orphans';

const b = (element: string, tag: string, anim: 'fill' | 'text' = 'fill', params: Record<string, unknown> = {}) =>
  ({ element, tag, anim, params });

describe('forsvundne elementer (v0.83.0)', () => {
  it('bindingerne pr. forsvundet element', () => {
    const all = [b('svg_190', 'A'), b('lever', 'B'), b('svg_190', 'C', 'text'), b('PLC1_Val', 'D')];
    expect(orphanGroups(all, ['PLC1_Val', 'svg_190'])).toEqual({ PLC1_Val: [all[3]], svg_190: [all[0], all[2]] });
    expect(orphanGroups(all, ['væk'])).toEqual({ væk: [] });
  });

  it('flyt: målets egne først, dubletter springes over, element/position fjernes', () => {
    const r = mergeMoved([b('ny', 'A', 'fill', { on: '#0f0' })], [b('gl', 'A', 'fill', { on: '#0f0' }), b('gl', 'B', 'text')]);
    expect(r).toEqual({ bindings: [{ tag: 'A', anim: 'fill', params: { on: '#0f0' } }, { tag: 'B', anim: 'text', params: {} }] });
  });

  it('for mange bindinger giver en fejl', () => {
    const many = Array.from({ length: 8 }, (_, i) => b('ny', `T${i}`));
    expect(mergeMoved(many, [b('gl', 'X'), b('gl', 'Y')])).toHaveProperty('bindings');
    expect(mergeMoved(many, [b('gl', 'X'), b('gl', 'Y'), b('gl', 'Z')])).toEqual({ error: 'Elementet ville få 11 bindinger — højst 10. Fjern nogle først.' });
  });
});
