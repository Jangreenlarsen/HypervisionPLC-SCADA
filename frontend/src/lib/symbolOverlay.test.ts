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

describe('tilstandsmærket kan fravælges (v2.12.0)', () => {
  it('uden mærke tegnes intet mærke, men skyggen ved afvigelse står stadig', async () => {
    const { drawOverlay } = await import('./symbolOverlay');
    const root = document.createElementNS(NS, 'svg') as SVGSVGElement;
    const g = document.createElementNS(NS, 'g');
    g.setAttribute('id', 's');
    root.appendChild(g);
    // jsdom har ingen getBBox/getScreenCTM: giv elementet en kasse
    (g as any).getBBox = () => ({ x: 0, y: 0, width: 40, height: 40 });
    const m = { inverse: () => m, multiply: () => m };
    (root as any).getScreenCTM = () => m;
    (g as any).getScreenCTM = () => m;
    (globalThis as any).DOMPoint ??= class { constructor(public x: number, public y: number) {} matrixTransform() { return this; } };
    drawOverlay(root, 's', { state: 'mismatch', remoteLabel: 'Fra', locked: false, badge: false });
    expect(root.querySelector('.hv-badge')).toBeNull();
    expect(root.querySelector('.hv-ghost')).not.toBeNull();
    drawOverlay(root, 's', { state: 'confirmed', remoteLabel: null, locked: false });
    expect(root.querySelector('.hv-badge')).not.toBeNull();   // standard: vises
  });
});
