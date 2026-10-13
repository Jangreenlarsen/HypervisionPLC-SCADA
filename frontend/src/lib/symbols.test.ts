import { describe, expect, it } from 'vitest';
import { CATEGORIES, PIPE_IDS, PIPE_PREVIEW, previewViewBox, selectorAngles, selectorSymbol, SYMBOLS, withName } from './symbols';

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
    'click:write', 'click:toggle', 'click:pulse', 'click:select']);
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

describe('omskifter med egne positioner', () => {
  it('vinkler fordelt symmetrisk om lodret', () => {
    expect(selectorAngles(3)).toEqual([-45, 0, 45]);
    expect(selectorAngles(2)).toEqual([-30, 30]);
    expect(selectorAngles(8)[0]).toBe(-135);
  });
  it('symbolet beskriver klik + greb og har navnene', () => {
    const doc = parse(selectorSymbol(['1', '2', '3', '4']));
    const g = doc.documentElement.firstElementChild!;
    expect(doc.getElementsByTagName('parsererror').length).toBe(0);
    const [click] = JSON.parse(g.getAttribute('data-hv-auto')!);
    expect(click.anim).toBe('click:select');
    expect(click.params.positions).toEqual([{ value: 0, label: '1' }, { value: 1, label: '2' }, { value: 2, label: '3' }, { value: 3, label: '4' }]);
    const greb = JSON.parse(g.querySelector('#greb')!.getAttribute('data-hv-part')!);
    expect(greb).toMatchObject({ anim: 'rotate', params: { min: 0, max: 3 } });
    expect([...g.querySelectorAll('text')].map((t) => t.textContent)).toEqual(['1', '2', '3', '4']);
  });
  it('navne escapes; for få/for lange navne afvises', () => {
    expect(selectorSymbol(['A&B', '<x>'])).toContain('A&amp;B');
    expect(() => selectorSymbol(['kun én'])).toThrow('mindst 2');
    expect(() => selectorSymbol(['a', 'x'.repeat(21)])).toThrow('20 tegn');
  });
});

describe('withName', () => {
  it('giver rod-g et navn; alle symboler kan navngives og forbliver gyldig SVG', () => {
    for (const s of SYMBOLS) {
      const doc = parse(withName(s.svg, s.label));
      expect(doc.getElementsByTagName('parsererror').length, s.id).toBe(0);
      expect(doc.documentElement.firstElementChild!.getAttribute('data-hv-name'), s.id).toBe(s.label);
    }
  });
  it('escaper tegn og begrænser længden', () => {
    const g = parse(withName('<g id="a"><rect/></g>', 'A & "B" <c>')).documentElement.firstElementChild!;
    expect(g.getAttribute('data-hv-name')).toBe('A & "B" <c>');
    expect(withName('<g><rect/></g>', 'x'.repeat(80)).match(/data-hv-name="(x+)"/)![1]).toHaveLength(60);
  });
});

describe('rør og fittings (v0.28.1)', () => {
  const size = (vb: string) => Number(vb.split(' ')[2]);
  it('alle rør-id-er findes i biblioteket', () => {
    const ids = new Set(SYMBOLS.map((s) => s.id));
    for (const id of PIPE_IDS) expect(ids.has(id), id).toBe(true);
  });
  it('rør og fittings får samme målestok i paletten, uanset deres egen størrelse', () => {
    const roer = previewViewBox({ x: 0, y: 0, width: 90, height: 10 }, true);
    const boej = previewViewBox({ x: 0, y: 25, width: 45, height: 20 }, true);
    const kryds = previewViewBox({ x: 0, y: 0, width: 90, height: 90 }, true);
    expect(size(roer)).toBe(PIPE_PREVIEW);
    expect(size(boej)).toBe(PIPE_PREVIEW);
    expect(size(kryds)).toBe(PIPE_PREVIEW);
    expect(roer.split(' ')[3]).toBe(String(PIPE_PREVIEW)); // kvadratisk vindue
  });
  it('vinduet centreres om symbolet og vokser hvis et rør er længere end standarden', () => {
    expect(previewViewBox({ x: 0, y: 40, width: 90, height: 10 }, true)).toBe(`-7 -7 ${PIPE_PREVIEW} ${PIPE_PREVIEW}`);
    expect(size(previewViewBox({ x: 0, y: 0, width: 160, height: 10 }, true))).toBe(174);
  });
  it('andre symboler tilpasses stadig deres egen størrelse', () => {
    expect(previewViewBox({ x: 0, y: 0, width: 100, height: 50 }, false)).toBe('-8 -8 116 66');
  });
  it('bøjningerne er runde og har samme rørtykkelse som de lige rør', () => {
    for (const id of ['boejning90', 'boejning45']) {
      const svg = SYMBOLS.find((s) => s.id === id)!.svg;
      expect(svg, id).toMatch(/ A20 20 /);
      expect(svg, id).toMatch(/stroke-width="10"/);
    }
    for (const id of ['t_stykke', 'kryds']) expect(SYMBOLS.find((s) => s.id === id)!.svg, id).toMatch(/stroke-width="10"/);
    for (const id of ['roer_v', 'roer_l']) expect(SYMBOLS.find((s) => s.id === id)!.svg, id).toMatch(/(height|width)="10"/);
  });
});
