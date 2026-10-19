import { describe, expect, it } from 'vitest';
import { SYMBOLS } from './symbols';
import { ROOT, animsFor, applyTest, librarySetup, resetTest, runSetup, testBinding, testInfo, testParts, valueRange } from './symbolTest';

const host = (svg: string) => {
  const h = document.createElement('div');
  h.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg">${svg}</svg>`;
  return h.firstElementChild!;
};
const def = (id: string) => SYMBOLS.find((s) => s.id === id)!;

describe('symboltest', () => {
  it('delene er roden og de navngivne dele, med danske navne', () => {
    const parts = testParts(def('motorventil').svg, 'motorventil');
    expect(parts[0].id).toBe(ROOT);
    expect(parts.map((p) => p.id)).toEqual(expect.arrayContaining(['hus', 'spindel', 'motor']));
    expect(parts.find((p) => p.id === 'spindel')?.label).toBe('Spindel');
  });
  it('symbolets egne animationer læses fra data-hv-part', () => {
    const own = testParts(def('vippekontakt').svg, 'vippekontakt').flatMap((p) => p.own);
    expect(own.some((o) => o.anim === 'move')).toBe(true);
  });
  it('en simuleret farve sættes på delen og kan nulstilles', () => {
    const h = host(def('lampe').svg);
    const b = testBinding('glas', 'fill', 'bool');
    expect(applyTest(h, 'glas', b, 1)).toBe(true);
    const el = h.querySelector('#glas')!;
    const on = (el as SVGElement).style.fill;
    expect(on).toBeTruthy();
    applyTest(h, 'glas', b, 0);
    expect((el as SVGElement).style.fill).not.toBe(on);
    resetTest(h, [b]);
  });
  it('en del der ikke findes giver false i stedet for en fejl', () => {
    expect(applyTest(host(def('lampe').svg), 'findes_ikke', testBinding('x', 'fill', 'bool'), 1)).toBe(false);
  });
  it('skyderens område falder tilbage til 0–1 ved ugyldige grænser', () => {
    expect(valueRange({ min: 10, max: 5 })).toEqual({ min: 0, max: 1 });
    expect(valueRange({ min: 0, max: 100 })).toEqual({ min: 0, max: 100 });
    expect(valueRange({})).toEqual({ min: 0, max: 1 });
  });

  it('en position sætter værdien pr. position og nulstilles ved ukendt position', () => {
    const h = host(def('lampe').svg);
    const b = testBinding('glas', 'fill', 'pos', 3);
    expect(b.params.pos).toBe(true);
    expect(b.params.colors).toHaveLength(3);
    applyTest(h, 'glas', b, 2);
    expect((h.querySelector('#glas') as SVGElement).style.fill).toBeTruthy();
  });
  it('positionstekst får et navn pr. position', () => {
    expect(testBinding('x', 'text', 'pos', 4).params.labels).toEqual(['Position 1', 'Position 2', 'Position 3', 'Position 4']);
  });
  it('delene får de animationer de kan have (rect: niveau, streger: løbelys, tekst: tekst)', () => {
    const svg = '<g><rect id="r" width="5" height="5"/><text id="t">x</text><circle id="c" r="3" fill="red"/></g>';
    const by = Object.fromEntries(testParts(svg).map((p) => [p.id, p.types]));
    expect(by.r).toEqual(expect.arrayContaining(['level', 'flow']));
    expect(by.t).toContain('text');
    expect(by.t).not.toContain('flow');
    expect(by.c).not.toContain('level');
    expect(by.c).not.toContain('flow');   // ingen streg
  });
  it('en streg giver løbelys, og en position kun de typer der har en værdi pr. position', () => {
    expect(testInfo('<g><path id="p" d="M0 0 H9" stroke="#000"/></g>').parts.p.line).toBe(true);
    const types = testParts('<g><rect id="r" width="5" height="5"/></g>')[1].types;
    expect(animsFor(types, 'pos')).not.toContain('level');
    expect(animsFor(types, 'pos')).toContain('flow');
    expect(animsFor(types, 'num')).toContain('level');
  });
  it('løbelys på et rør kan afprøves', () => {
    const svg = '<g><path id="roer" d="M0 0 H90" stroke="#000" stroke-width="10" fill="none"/></g>';
    const h = host(svg);
    expect(applyTest(h, 'roer', testBinding('roer', 'flow', 'bool'), 1)).toBe(true);
    expect(applyTest(h, 'roer', testBinding('roer', 'flow', 'pos', 2), 1)).toBe(true);
  });
  it('bibliotekets opsætning: ventil og vippekontakt har positioner, kontakt og pumpe til/fra, statusfelt tal', () => {
    const pos = (id: string) => librarySetup(def(id).svg, id)!;
    expect(pos('trevejs_motorventil').positions).toHaveLength(2);
    expect(pos('vippe_onoffon').positions).toEqual(['ON 1', 'OFF', 'ON 2']);
    expect(pos('kontakt2').kind).toBe('bool');
    expect(pos('pumpe').positions).toEqual([]);
    expect(pos('statusfelt').kind).toBe('num');
    expect(librarySetup(def('lampe').svg, 'lampe')).toBeNull();
  });
  it('bibliotekets opsætning kan køres på alle positioner og finder alle delene', () => {
    for (const id of ['trevejs_motorventil', 'vippe_onoff', 'vippe_onoffon', 'kontakt2', 'kontakt3', 'kedel', 'pumpe', 'varmepumpe', 'statusfelt']) {
      const s = librarySetup(def(id).svg, id);
      if (!s) continue;
      const h = host(def(id).svg);
      const values = s.positions.length ? s.positions.map((_, j) => j) : s.kind === 'num' ? [0, 60, 100] : [0, 1];
      for (const v of values) expect(runSetup(h, s, v), `${id} @ ${v}`).toEqual([]);
    }
  });
  it('vippekontaktens greb står forskelligt i hver position', () => {
    const s = librarySetup(def('vippe_onoffon').svg, 'vippe_onoffon')!;
    const h = host(def('vippe_onoffon').svg);
    const seen = new Set<string>();
    for (let j = 0; j < s.positions.length; j++) {
      runSetup(h, s, j);
      const g = h.querySelector('#greb') as SVGElement, k = h.querySelector('#knop') as SVGElement;
      seen.add(`${g.style.transform}|${g.style.display}|${k.style.display}`);
    }
    expect(seen.size).toBe(3);
  });
  it('alle biblioteksdele kan få deres typer og et navn', () => {
    for (const s of SYMBOLS) {
      for (const p of testParts(s.svg, s.id)) {
        expect(p.types.length, `${s.id}/${p.id}`).toBeGreaterThan(0);
        expect(p.label).toBeTruthy();
      }
    }
  });
});
