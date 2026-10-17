import { describe, expect, it } from 'vitest';
import { SYMBOLS } from './symbols';
import { hasTextSlot, nameHint, stretchesByDefault, suggestSymbols, type SelectionInfo } from './symbolSuggest';

const sel = (over: Partial<SelectionInfo>): SelectionInfo => ({
  id: 'svg_1', tag: 'g', counts: {}, children: 1, w: 70, h: 70, angle: 0, fill: '', stroke: '', strokeWidth: 0, rx: 0, name: '',
  symbolType: '', ids: ['svg_1'], texts: [], apexAngle: null, axisAngle: null, similar: 0, similarAny: 0, similarGroups: [], ...over,
});
const top = (s: SelectionInfo) => suggestSymbols(s)[0]?.id;
const ids = (s: SelectionInfo) => suggestSymbols(s).map((x) => x.id);

// Opbygningerne er målt på den rigtige "varme"-tegning (se CHANGELOG 0.55.0)
describe('forslag til symboler (opbygninger fra "varme"-tegningen)', () => {
  it('pille-etiket (afrundet, ufyldt rektangel) → statusfelt', () => {
    const s = sel({ tag: 'rect', counts: { rect: 1 }, w: 68.4, h: 24.3, rx: 10, fill: 'none', stroke: '#000000', strokeWidth: 2, texts: ['STF'] });
    expect(top(s)).toBe('statusfelt');
    expect(ids(s)).toContain('vaerdi');
  });

  it('etiket tegnet som sti (ATT1 m.fl., 71×29, ufyldt kontur) → statusfelt; en tynd linje eller et rør er det ikke', () => {
    expect(top(sel({ tag: 'path', counts: { path: 1 }, w: 70.9, h: 28.6, fill: 'none', stroke: '#000000', strokeWidth: 2, texts: ['ATT1'] }))).toBe('statusfelt');
    expect(suggestSymbols(sel({ tag: 'path', counts: { path: 1 }, w: 300, h: 3, fill: 'none', stroke: '#000', strokeWidth: 2 }))).toEqual([]);
    expect(suggestSymbols(sel({ tag: 'path', counts: { path: 1 }, w: 40, h: 200, fill: 'none', stroke: '#000', strokeWidth: 2 }))).toEqual([]);
  });

  it('flere løse dele (3 trekanter, prik, motorcirkel, streg, bogstaver) → 3-vejs motorventil', () => {
    const s = sel({ tag: 'markering', counts: { path: 3, ellipse: 2, line: 1, text: 4 }, children: 10, w: 118, h: 96 });
    expect(top(s)).toBe('trevejs_motorventil');
    expect(ids(s)).toEqual(expect.arrayContaining(['trevejs_motorventil_ab', 'motorventil']));
    // for få figurer eller for lille/stor: intet forslag
    expect(suggestSymbols(sel({ tag: 'markering', counts: { path: 1, ellipse: 1 }, w: 100, h: 100 }))).toEqual([]);
    expect(suggestSymbols(sel({ tag: 'markering', counts: { path: 3, ellipse: 2, line: 1 }, w: 20, h: 20 }))).toEqual([]);
  });

  it('cirkel + trekant (72×70) → pumpe, med ventilator og motor som alternativer', () => {
    const s = sel({ counts: { g: 2, ellipse: 1, path: 1 }, w: 72.5, h: 70 });
    expect(ids(s).slice(0, 3)).toEqual(['pumpe', 'ventilator', 'motor']);
  });

  it('cirkel med streger (72×70, ingen trekant) → pumpe med lavere sikkerhed', () => {
    const s = sel({ counts: { g: 2, ellipse: 1, line: 2 }, w: 72.5, h: 70 });
    expect(top(s)).toBe('pumpe');
    expect(suggestSymbols(s)[0].score).toBeLessThan(90);
  });

  it('ventil med stilk/greb og kun én prik (Bypas, sikkerhedsventil) → manuel ventil først; sikkerheds- og reguleringsventil som alternativ', () => {
    const s = sel({ counts: { g: 3, ellipse: 1, line: 2, path: 2 }, w: 77.6, h: 74.9 });
    expect(top(s)).toBe('ventil');
    expect(ids(s)).toEqual(expect.arrayContaining(['regventil', 'sikkerhedsventil', 'motorventil']));
  });

  it('ventil med motorcirkel (to ellipser) → motorventil først', () => {
    expect(top(sel({ counts: { g: 2, ellipse: 2, line: 1, path: 2 }, w: 70, h: 75 }))).toBe('motorventil');
  });

  it('to løse trekanter og en prik (AVTA/AVTB/Laddomat) → ventil eller reguleringsventil', () => {
    const s = sel({ tag: 'markering', counts: { path: 2, ellipse: 1 }, children: 3, w: 53, h: 75 });
    expect(ids(s).slice(0, 2)).toEqual(['ventil', 'regventil']);
  });

  it('trekant med tværstreg (40×53) → kontraventil', () => {
    expect(top(sel({ counts: { g: 2, path: 1, line: 1 }, w: 39.5, h: 52.5 }))).toBe('kontraventil');
  });

  it('lille cirkel med streg (målepunkt, 14×24) → føler/forbindelsespunkt', () => {
    const s = sel({ counts: { g: 2, ellipse: 1, line: 1 }, w: 22.7, h: 25 });
    expect(top(s)).toBe('foeler');
  });

  it('stort fyldt rektangel: høj → tank, bred → kedel; lille → også ekspansionsbeholder', () => {
    expect(top(sel({ tag: 'rect', counts: { rect: 1 }, w: 133, h: 217, fill: '#ff7f00', stroke: '#000', strokeWidth: 10 }))).toBe('tank');
    expect(top(sel({ tag: 'rect', counts: { rect: 1 }, w: 146.6, h: 155, fill: '#f27185' }))).toBe('kedel');
    const small = suggestSymbols(sel({ tag: 'rect', counts: { rect: 1 }, w: 97.5, h: 80.5, fill: '#fc0228', strokeWidth: 10 }));
    expect(small.find((x) => x.id === 'ekspansion')!.score).toBeGreaterThanOrEqual(60);
  });

  it('kedel-gruppen (rektangel + 2 stier, 131×217) → kedel', () => {
    expect(top(sel({ counts: { g: 2, path: 2, rect: 1, text: 2 }, w: 130.9, h: 216.5, texts: ['Pille', 'Fyr'] }))).toBe('kedel');
  });

  it('tykke streger → rør; vandret/lodret afgøres af formen, knæk giver bøjning', () => {
    const pipe = (w: number, h: number) => sel({ tag: 'path', counts: { path: 1 }, w, h, stroke: '#000', strokeWidth: 10 });
    expect(top(pipe(300, 10))).toBe('roer_v');
    expect(top(pipe(10, 300))).toBe('roer_l');
    expect(top(pipe(80, 60))).toBe('boejning90');
  });

  it('tynde streger, tekster og et symbol der allerede er et symbol giver ingen forslag', () => {
    expect(suggestSymbols(sel({ tag: 'path', counts: { path: 1 }, w: 200, h: 3, stroke: '#000', strokeWidth: 2 }))).toEqual([]);
    expect(suggestSymbols(sel({ tag: 'text', counts: { text: 1 }, w: 40, h: 15 }))).toEqual([]);
    expect(suggestSymbols(sel({ counts: { g: 2, ellipse: 1, path: 1 }, symbolType: 'pumpe' }))).toEqual([]);
  });

  it('alle foreslåede symboler findes i biblioteket (ingen stavefejl i id\'erne)', () => {
    const lib = new Set(SYMBOLS.map((s) => s.id));
    const samples: SelectionInfo[] = [
      sel({ tag: 'rect', counts: { rect: 1 }, w: 68, h: 24, rx: 10, fill: 'none' }),
      sel({ tag: 'rect', counts: { rect: 1 }, w: 133, h: 217, fill: '#f70' }),
      sel({ tag: 'rect', counts: { rect: 1 }, w: 90, h: 80, fill: '#f00' }),
      sel({ counts: { g: 2, ellipse: 1, path: 1 }, w: 72, h: 70 }),
      sel({ counts: { g: 2, ellipse: 1, line: 2 }, w: 72, h: 70 }),
      sel({ counts: { g: 3, ellipse: 1, line: 2, path: 2 }, w: 70, h: 70 }),
      sel({ counts: { g: 2, ellipse: 1, line: 1 }, w: 20, h: 24 }),
      sel({ counts: { g: 2, path: 2, rect: 1 }, w: 131, h: 217 }),
      sel({ tag: 'path', counts: { path: 1 }, w: 300, h: 10, strokeWidth: 10 }),
      sel({ tag: 'path', counts: { path: 1 }, w: 10, h: 300, strokeWidth: 10 }),
      sel({ tag: 'path', counts: { path: 1 }, w: 60, h: 60, strokeWidth: 10 }),
      sel({ tag: 'ellipse', counts: { ellipse: 1 }, w: 15, h: 15, fill: '#000' }),
    ];
    for (const x of samples) for (const g of suggestSymbols(x)) expect(lib.has(g.id), g.id).toBe(true);
  });

  it('forslagene er sorteret med højeste sikkerhed først og har en begrundelse', () => {
    const list = suggestSymbols(sel({ counts: { g: 3, ellipse: 1, line: 2, path: 2 }, w: 70, h: 70 }));
    for (let i = 1; i < list.length; i++) expect(list[i - 1].score).toBeGreaterThanOrEqual(list[i].score);
    for (const x of list) expect(x.why.length).toBeGreaterThan(5);
  });
});

describe('hjælpere til dialogen', () => {
  it('hasTextSlot: kun symboler med en del der hedder tekst kan overtage en tegnet tekst', () => {
    const slots = SYMBOLS.filter((s) => hasTextSlot(s.svg)).map((s) => s.id);
    expect(slots).toEqual(expect.arrayContaining(['statusfelt']));
    expect(hasTextSlot(SYMBOLS.find((s) => s.id === 'tank')!.svg)).toBe(false);
  });

  it('nameHint: nuværende navn, ellers tekst inde i delen, ellers symbolets eget navn', () => {
    expect(nameHint(sel({ name: 'Pumpe 1' }), 'Pumpe')).toBe('Pumpe 1');
    expect(nameHint(sel({ texts: ['STF'] }), 'Statusfelt')).toBe('Statusfelt STF');
    expect(nameHint(sel({ texts: ['en meget lang tekst der ikke er en etiket men en hel sætning'] }), 'Pumpe')).toBe('Pumpe');
    expect(nameHint(sel({}), 'Pumpe')).toBe('Pumpe');
  });

  it('rør strækkes til at fylde som standard, andre symboler beholder proportionerne', () => {
    expect(stretchesByDefault('roer_v')).toBe(true);
    expect(stretchesByDefault('pumpe')).toBe(false);
  });
});

describe('varmepumpe ud fra teksten (v0.66.0)', () => {
  it('"Varme Pumpe" i en tegnet kasse (som i "varme") → varmepumpe først', () => {
    const s = sel({ counts: { rect: 2, text: 3 }, w: 95, h: 95, texts: ['køre', 'Varme', 'Pumpe'] });
    expect(top(s)).toBe('varmepumpe');
    expect(top(sel({ tag: 'rect', counts: { rect: 1 }, w: 146, h: 155, fill: '#f27185', texts: ['Varmepumpe 2'] }))).toBe('varmepumpe');
  });
  it('andre tekster giver ikke varmepumpe', () => {
    expect(ids(sel({ counts: { rect: 1, path: 2 }, w: 130.9, h: 216.5, texts: ['Pille', 'Fyr'] }))).not.toContain('varmepumpe');
    expect(ids(sel({ texts: ['Pumpe 1'] }))).not.toContain('varmepumpe');
  });
});
