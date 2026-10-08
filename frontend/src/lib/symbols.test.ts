import { describe, expect, it } from 'vitest';
import { CATEGORIES, SYMBOLS } from './symbols';

const parse = (fragment: string) =>
  new DOMParser().parseFromString(`<svg xmlns="http://www.w3.org/2000/svg">${fragment}</svg>`, 'image/svg+xml');

describe('symbolbibliotek', () => {
  it('hvert symbol er gyldig SVG med præcis ét <g>-rodelement', () => {
    for (const s of SYMBOLS) {
      const doc = parse(s.svg);
      expect(doc.getElementsByTagName('parsererror').length, s.id).toBe(0);
      const roots = [...doc.documentElement.children];
      expect(roots.map((r) => r.tagName), s.id).toEqual(['g']);
    }
  });
  it('unikke id-er, kendte kategorier og ingen tom kategori', () => {
    expect(new Set(SYMBOLS.map((s) => s.id)).size).toBe(SYMBOLS.length);
    const cats = new Set(CATEGORIES.map((c) => c.id));
    for (const s of SYMBOLS) expect(cats.has(s.category), s.id).toBe(true);
    for (const c of CATEGORIES) expect(SYMBOLS.some((s) => s.category === c.id), c.id).toBe(true);
  });
  it('id-er inde i et symbol er unikke (de får præfiks ved indsættelse)', () => {
    for (const s of SYMBOLS) {
      const ids = [...parse(s.svg).querySelectorAll('[id]')].map((e) => e.id);
      expect(new Set(ids).size, s.id).toBe(ids.length);
    }
  });
  it('de ønskede fittings og el-symboler findes', () => {
    const ids = new Set(SYMBOLS.map((s) => s.id));
    for (const id of ['boejning90', 'boejning45', 't_stykke', 'kryds', 'kontraventil', 'kontaktor', 'sikring', 'motor3', 'jord'])
      expect(ids.has(id), id).toBe(true);
  });
});
