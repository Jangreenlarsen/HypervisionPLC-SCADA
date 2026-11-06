// Tegneredskaberne fra v3.33.0 (svgedit-host/shapes.js): former, streg, pile, gradient, skygge, oprydning og billeder.
import { describe, expect, it, vi } from 'vitest';
// @ts-expect-error — ren JS uden typer
import * as S from '../../../svgedit-host/shapes.js';

vi.mock('@svgedit/svgcanvas', () => ({ default: class {} }));
vi.mock('../../../svgedit-host/scada-core.js', () => ({ createScada: () => ({}) }));
const { shortcutFor } = await import('./engine');

const svgDoc = (inner = ''): SVGSVGElement => {
  const d = new DOMParser().parseFromString(`<svg xmlns="http://www.w3.org/2000/svg">${inner}</svg>`, 'image/svg+xml');
  return document.importNode(d.documentElement, true) as unknown as SVGSVGElement;
};

describe('former', () => {
  it('regulær polygon: n hjørner på radius, første opad', () => {
    const p = S.regularPoints(50, 50, 10, 6);
    expect(p).toHaveLength(6);
    expect(p[0]).toEqual([50, 40]);
    for (const [x, y] of p) expect(Math.hypot(x - 50, y - 50)).toBeCloseTo(10, 1);
    expect(S.regularPoints(0, 0, 1, 1)).toHaveLength(3);   // mindst 3
  });

  it('stjerne: 2n punkter, skiftevis ydre og indre radius', () => {
    const p = S.starPoints(0, 0, 10, 5, 0.4);
    expect(p).toHaveLength(10);
    expect(Math.hypot(...p[0])).toBeCloseTo(10, 1);
    expect(Math.hypot(...p[1])).toBeCloseTo(4, 1);
  });

  it('tegnes om med nye parametre og bevarer midte, størrelse og drejning', () => {
    const old = S.pointsAttr(S.starPoints(100, 80, 20, 5, 0.5, 30));
    const next = S.parsePoints(S.regenerate(old, { k: 'star', n: 5, ri: 0.5 }, { k: 'star', n: 8, ri: 0.3 }));
    expect(next).toHaveLength(16);
    expect(next[0][0]).toBeCloseTo(100 + 20 * Math.sin(Math.PI / 6), 1);
    expect(Math.hypot(next[1][0] - 100, next[1][1] - 80)).toBeCloseTo(6, 1);
    const hex = S.parsePoints(S.regenerate(S.pointsAttr(S.regularPoints(0, 0, 10, 6)), { k: 'regpoly', n: 6 }, { k: 'regpoly', n: 3 }));
    expect(hex).toHaveLength(3);
    expect(S.regenerate('1,1 2,2', { k: 'regpoly', n: 3 })).toBeNull();
  });

  it('formens parametre læses sikkert', () => {
    const el = document.createElementNS(S.NS, 'polygon');
    expect(S.shapeParams(el)).toBeNull();
    el.setAttribute('data-hv-shape', '{"k":"star","n":6,"ri":0.4}');
    expect(S.shapeParams(el)).toEqual({ k: 'star', n: 6, ri: 0.4 });
    el.setAttribute('data-hv-shape', '{ødelagt');
    expect(S.shapeParams(el)).toBeNull();
  });
});

describe('bue', () => {
  it('vinkel med uret fra op, med 15°-fang', () => {
    expect(S.angleTo(0, 0, 0, -5)).toBe(0);
    expect(S.angleTo(0, 0, 5, 0)).toBe(90);
    expect(S.angleTo(0, 0, -5, 0)).toBe(270);
    expect(S.angleTo(0, 0, 5, -4.5, 15)).toBe(45);
  });
  it('kvart og trekvart bue (large-arc)', () => {
    expect(S.arcPath(0, 0, 10, 0, 90)).toBe('M0,-10 A10,10 0 0 1 10,0');
    expect(S.arcPath(0, 0, 10, 90, 0)).toBe('M10,0 A10,10 0 1 1 0,-10');
    expect(S.arcPath(0, 0, 10, 30, 30)).toMatch(/ 0 1 1 /);   // samme vinkel → næsten hel cirkel
  });
});

describe('streg', () => {
  it('stregtypen skaleres med tykkelsen og kan læses tilbage', () => {
    expect(S.dashArray('solid', 3)).toBeNull();
    expect(S.dashArray('dash', 3)).toBe('12 6');
    expect(S.dashArray('dashdot', 0)).toBe('4 2 1 2');   // tykkelse 0 → mønster for 1
    for (const k of ['dash', 'dot', 'dashdot']) expect(S.dashKind(S.dashArray(k, 2.5), 2.5)).toBe(k);
    expect(S.dashKind(null, 2)).toBe('solid');
    expect(S.dashKind('7 3', 2)).toBe('custom');
  });
});

describe('defs: pile, gradienter, skygge og oprydning', () => {
  it('pilen genbruges pr. farve', () => {
    const svg = svgDoc();
    const a = S.ensureArrow(svg, '#ff0000');
    expect(S.ensureArrow(svg, '#ff0000')).toBe(a);
    expect(S.ensureArrow(svg, '#00ff00')).not.toBe(a);
    expect(svg.querySelectorAll('marker')).toHaveLength(2);
    expect(svg.querySelector(`#${a} path`)?.getAttribute('fill')).toBe('#ff0000');
  });

  it('gradient laves, rettes, skifter type og læses tilbage', () => {
    const svg = svgDoc();
    const id = S.ensureGradient(svg, 'r1', 'linear', '#fff', '#000', 90);
    expect(S.gradientOf(svg, `url(#${id})`)).toMatchObject({ kind: 'linear', c1: '#fff', c2: '#000', angle: 90 });
    S.ensureGradient(svg, 'r1', 'linear', '#111', '#222', 0);
    expect(S.gradientOf(svg, `url(#${id})`)).toMatchObject({ c1: '#111', angle: 0 });
    S.ensureGradient(svg, 'r1', 'radial', '#111', '#222');
    expect(svg.querySelectorAll('linearGradient')).toHaveLength(0);
    expect(S.gradientOf(svg, `url(#${id})`)?.kind).toBe('radial');
    expect(S.gradientOf(svg, '#ff0000')).toBeNull();
  });

  it('skygge: værdier holdes inden for grænser', () => {
    const svg = svgDoc();
    const id = S.ensureShadow(svg, 'r1', { dx: 500, dy: -2, blur: 99, color: '#333' });
    expect(S.shadowOf(svg, `url(#${id})`)).toEqual({ dx: 50, dy: -2, blur: 30, color: '#333' });
    expect(S.shadowOf(svg, null)).toBeNull();
  });

  it('kun Tegns egne, ubrugte defs ryddes op', () => {
    const svg = svgDoc('<defs><linearGradient id="egen"/></defs><rect id="r1"/><line id="l1"/>');
    const g = S.ensureGradient(svg, 'r1', 'linear', '#fff', '#000');
    const p = S.ensureArrow(svg, '#000');
    S.ensureShadow(svg, 'r1');
    svg.querySelector('#r1')!.setAttribute('fill', `url(#${g})`);
    svg.querySelector('#l1')!.setAttribute('marker-end', `url(#${p})`);
    expect(S.cleanupDefs(svg)).toBe(1);   // kun skyggen
    expect(svg.querySelector('#egen')).not.toBeNull();
    svg.querySelector('#l1')!.removeAttribute('marker-end');
    expect(S.cleanupDefs(svg)).toBe(1);
    expect(svg.querySelector(`#${g}`)).not.toBeNull();
  });
});

describe('billede', () => {
  it('skaleres ned til højst 60 % af tegningen', () => {
    expect(S.fitImage(100, 50, 1200, 700)).toEqual({ w: 100, h: 50 });
    expect(S.fitImage(2400, 1200, 1200, 700)).toEqual({ w: 720, h: 360 });
  });
  it('type og størrelse kontrolleres', () => {
    expect(S.imageProblem({ name: 'a.png', type: 'image/png', size: 1000 })).toBe('');
    expect(S.imageProblem({ name: 'a.svg', type: 'image/svg+xml', size: 1000 })).toMatch(/kun PNG/);
    expect(S.imageProblem({ name: 'a.jpg', type: 'image/jpeg', size: 3e6 })).toMatch(/2 MB/);
  });
});

describe('genveje', () => {
  const k = (key: string, ctrl = false) => shortcutFor({ key, ctrlKey: ctrl, metaKey: false, shiftKey: false, altKey: false });
  it('nye værktøjer og trinvis rækkefølge', () => {
    expect(k('y')).toBe('tool:polygon');
    expect(k('s')).toBe('tool:star');
    expect(k('n')).toBe('tool:regpoly');
    expect(k('b')).toBe('tool:arc');
    expect(k(']', true)).toBe('raise');
    expect(k('[', true)).toBe('lower');
  });
});
