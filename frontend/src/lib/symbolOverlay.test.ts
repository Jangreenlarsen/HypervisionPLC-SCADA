import { describe, expect, it } from 'vitest';
import { lockedTexts } from './symbolOverlay';

const NS = 'http://www.w3.org/2000/svg';
function symbol(...texts: string[]): SVGGElement {
  const g = document.createElementNS(NS, 'g');
  for (const t of texts) {
    const e = document.createElementNS(NS, 'text');
    e.textContent = t;
    g.appendChild(e);
  }
  return g;
}

describe('lockedTexts', () => {
  it('finder teksterne med de låste positioners navne', () => {
    const found = lockedTexts(symbol('Hånd', ' 0 ', 'Auto'), ['0', 'Auto']);
    expect(found.map((t) => t.textContent?.trim())).toEqual(['0', 'Auto']);
  });
  it('ingen låste positioner eller ingen tekst med navnet → intet', () => {
    expect(lockedTexts(symbol('Hånd', 'Auto'), [])).toEqual([]);
    expect(lockedTexts(symbol('Hånd', 'Auto'), ['Service'])).toEqual([]);
    expect(lockedTexts(symbol('Auto'), [' '])).toEqual([]);
  });
});

describe('markPassive', () => {
  it('tilføjer tooltip og mærke på symbolet, men kun én gang', async () => {
    const { markPassive } = await import('./symbolOverlay');
    const root = document.createElementNS(NS, 'svg') as SVGSVGElement;
    const g = document.createElementNS(NS, 'g');
    g.setAttribute('id', 'omsk');
    const t = document.createElementNS(NS, 'title');
    t.textContent = 'Omskifter';
    g.appendChild(t);
    root.appendChild(g);
    markPassive(root, 'omsk');
    markPassive(root, 'omsk');
    expect(g.querySelector('title')?.textContent).toBe('Omskifter — Kun visning — kan ikke betjenes');
    expect(g.hasAttribute('data-hv-passive')).toBe(true);
  });
  it('uden eksisterende tooltip oprettes en', async () => {
    const { markPassive } = await import('./symbolOverlay');
    const root = document.createElementNS(NS, 'svg') as SVGSVGElement;
    const g = document.createElementNS(NS, 'g');
    g.setAttribute('id', 'x');
    root.appendChild(g);
    markPassive(root, 'x');
    expect(g.querySelector('title')?.textContent).toBe('Kun visning — kan ikke betjenes');
  });
});
