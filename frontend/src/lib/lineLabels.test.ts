import { describe, expect, it } from 'vitest';
import { LABEL_GAP, lastVisible, needsArrow, spreadLabels } from './lineLabels';

describe('spreadLabels', () => {
  it('navne langt fra hinanden bliver stående ud for deres kurve', () => {
    expect(spreadLabels([20, 100, 200], 0, 300)).toEqual([20, 100, 200]);
  });
  it('tætte kurver spredes med mindst mellemrummet, og rækkefølgen bevares', () => {
    const out = spreadLabels([100, 101, 102], 0, 300);
    expect(out[1] - out[0]).toBeGreaterThanOrEqual(LABEL_GAP);
    expect(out[2] - out[1]).toBeGreaterThanOrEqual(LABEL_GAP);
    expect(out[0]).toBeLessThan(out[1]);
  });
  it('resultatet følger inputrækkefølgen, også når kurverne står omvendt', () => {
    const out = spreadLabels([102, 100, 101], 0, 300);
    expect(out[1]).toBeLessThan(out[2]);
    expect(out[2]).toBeLessThan(out[0]);
  });
  it('en gruppe nederst skubbes opad, så ingen navne forlader grafen', () => {
    const out = spreadLabels([298, 299, 300], 0, 300);
    expect(Math.max(...out)).toBeLessThanOrEqual(300);
    expect(out[1] - out[0]).toBeGreaterThanOrEqual(LABEL_GAP);
  });
  it('ikke plads nok: navnene overlapper aldrig og starter ikke over toppen', () => {
    const out = spreadLabels([5, 5, 5, 5], 0, 20);
    const sorted = [...out].sort((a, b) => a - b);
    for (let i = 1; i < sorted.length; i++) expect(sorted[i] - sorted[i - 1]).toBeGreaterThanOrEqual(LABEL_GAP);
    expect(sorted[0]).toBeGreaterThanOrEqual(0);
  });
  it('ingen kurver giver ingen navne', () => {
    expect(spreadLabels([], 0, 100)).toEqual([]);
  });
});

describe('lastVisible', () => {
  const xs = [0, 10, 20, 30, 40];
  it('sidste punkt med værdi', () => {
    expect(lastVisible(xs, [1, 2, 3, 4, 5], 0, 40)).toBe(4);
    expect(lastVisible(xs, [1, 2, 3, null, undefined], 0, 40)).toBe(2);
  });
  it('kun punkter inden for det zoomede vindue', () => {
    expect(lastVisible(xs, [1, 2, 3, 4, 5], 0, 25)).toBe(2);
  });
  it('0 er en værdi, og ingen værdier giver -1', () => {
    expect(lastVisible(xs, [0, 0, 0, 0, 0], 0, 40)).toBe(4);
    expect(lastVisible(xs, [null, null, null, null, null], 0, 40)).toBe(-1);
  });
});

describe('needsArrow', () => {
  it('kun et navn der er flyttet væk fra kurven får pil', () => {
    expect(needsArrow(100, 101)).toBe(false);
    expect(needsArrow(100, 120)).toBe(true);
  });
});
