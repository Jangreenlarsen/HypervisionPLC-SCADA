import { describe, expect, it } from 'vitest';
import { suggestName } from './naming';

describe('suggestName', () => {
  it('rør, symbol og elementtype får hvert sit grundnavn, første ledige nummer', () => {
    expect(suggestName({ tag: 'path', pipe: true }, [])).toBe('Rør 1');
    expect(suggestName({ tag: 'path', pipe: true }, ['Rør 1', 'Rør 2'])).toBe('Rør 3');
    expect(suggestName({ tag: 'g', label: 'Pumpe' }, ['Pumpe 1'])).toBe('Pumpe 2');
    expect(suggestName({ tag: 'path' }, [])).toBe('Linje 1');
    expect(suggestName({ tag: 'foreignObject' }, [])).toBe('Element 1');
  });
});
