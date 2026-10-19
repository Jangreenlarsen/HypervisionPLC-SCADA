import { describe, expect, it } from 'vitest';
import { SYMBOLS } from './symbols';
import { ROOT, applyTest, resetTest, testBinding, testParts, valueRange } from './symbolTest';

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
});
