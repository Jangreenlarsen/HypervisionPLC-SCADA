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
    for (const id of ['boejning90', 'boejning45', 't_stykke', 'kryds', 'kontraventil', 'kontaktor', 'sikring', 'motor3', 'jord', 'solpanel', 'inverter', 'batteri', 'elnet'])
      expect(ids.has(id), id).toBe(true);
  });
});

describe('betjeningssymboler', () => {
  const ANIMS = new Set(['text', 'fill', 'stroke', 'visible', 'blink', 'level', 'rotate', 'opacity', 'move',
    'click:write', 'click:toggle', 'click:pulse']);
  const interactive = SYMBOLS.filter((s) => s.category === 'betjening');
  it('har en klik-handling på roden og gyldige beskrivelser på delene', () => {
    expect(interactive.length).toBeGreaterThanOrEqual(5);
    for (const s of interactive) {
      const g = parse(s.svg).documentElement.firstElementChild!;
      const autos = JSON.parse(g.getAttribute('data-hv-auto')!);
      expect(autos.some((a: { anim: string }) => a.anim.startsWith('click:')), s.id).toBe(true);
      for (const a of autos) expect(ANIMS.has(a.anim), `${s.id}: ${a.anim}`).toBe(true);
      for (const p of g.querySelectorAll('[data-hv-part]')) {
        expect(p.id, `${s.id}: del uden id`).not.toBe('');
        expect(ANIMS.has(JSON.parse(p.getAttribute('data-hv-part')!).anim), s.id).toBe(true);
      }
    }
  });
});
