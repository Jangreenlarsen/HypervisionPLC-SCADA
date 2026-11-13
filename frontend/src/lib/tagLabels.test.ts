import { describe, expect, it } from 'vitest';
import { tagLines, tagsByElement } from './tagLabels';

describe('tags oven på tegningen', () => {
  it('samler symbolets og bindingernes tags uden dubletter og uden interne værdier', () => {
    const m = tagsByElement(
      [{ element: 'P1', tags: ['Drift', 'Fejl'] }, { element: 'P2', tags: [] }],
      [
        { element: 'P1', tag: 'Drift', anim: 'fill', params: {} },
        { element: 'T1', tag: 'Temp', anim: 'text', params: {} },
        { element: 'T1', tag: '@on', anim: 'flow', params: { dir_tag: 'Retning' } },
        { element: 'X', tag: 'sym:d:P1:pos', anim: 'text', params: {} },
        { element: 'Y', tag: 'flow:d:R1', anim: 'flow', params: {} },
      ],
    );
    expect(m).toEqual({ P1: ['Drift', 'Fejl'], T1: ['Temp', 'Retning'] });
  });

  it('afkorter lange lister', () => {
    expect(tagLines(['a', 'b'])).toEqual(['a', 'b']);
    expect(tagLines(['a', 'b', 'c', 'd'])).toEqual(['a', 'b', 'c', 'd']);
    expect(tagLines(['a', 'b', 'c', 'd', 'e', 'f'])).toEqual(['a', 'b', 'c', '+3 flere']);
  });
});
