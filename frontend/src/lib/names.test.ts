// Navne til symboler uden navn ved "Indsæt opsætning" (svgedit-host/names.js).
import { describe, expect, it } from 'vitest';
// @ts-expect-error — ren JS-fil i værtsmappen til SVG-Edit (ingen typer)
import { MAX_NAME, numberedNames } from '../../svgedit-host/names.js';

describe('nummererede navne', () => {
  it('kildens navn + løbenummer, ledige numre', () => {
    expect(numberedNames('varme pumpe tilgang', 3, [])).toEqual(['varme pumpe tilgang_1', 'varme pumpe tilgang_2', 'varme pumpe tilgang_3']);
    expect(numberedNames('Rør', 2, ['Rør_1', 'Rør_3', 'Rør'])).toEqual(['Rør_2', 'Rør_4']);
    expect(numberedNames('Rør', 0, [])).toEqual([]);
  });
  it('tomt navn, mellemrum og længdegrænse', () => {
    expect(numberedNames('  ', 1, [])).toEqual(['Symbol_1']);
    expect(numberedNames(' a   b ', 1, [])).toEqual(['a b_1']);
    const long = 'x'.repeat(80);
    const [n1] = numberedNames(long, 1, []);
    expect(n1.length).toBe(MAX_NAME);
    expect(n1.endsWith('_1')).toBe(true);
    const ten = numberedNames(long, 10, []);
    expect(ten[9].length).toBe(MAX_NAME);
    expect(ten[9].endsWith('_10')).toBe(true);
  });
});
