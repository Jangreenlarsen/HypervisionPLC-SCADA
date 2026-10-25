import { describe, expect, it, vi } from 'vitest';

vi.mock('./api', () => ({
  get: vi.fn(async () => ({ start: 0, end: 3600, series: { T: [[0, 1], [1800, 5], [3600, 3]] } })),
}));

import { mountChartIn } from './chartRender';
import { defaultChart } from './chartGraphic';

describe('trendgraf i en boks (v1.15.0 — også den store visning)', () => {
  it('tegner grafen i boksen, henter data og fjernes igen', async () => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg') as SVGSVGElement;
    document.body.appendChild(svg);
    const stop = mountChartIn(svg, { x: 0, y: 0, w: 1000, h: 560 }, { ...defaultChart(), tags: ['T'], title: 'Temp' }, { T: { unit: '°C' } }, 'stor');
    const g = svg.querySelector('g.hv-chart');
    expect(g).not.toBeNull();
    await vi.waitFor(() => expect(svg.querySelector('g.hv-chart polyline')).not.toBeNull());
    expect(g?.textContent).toContain('Temp');
    stop();
    expect(svg.querySelector('g.hv-chart')).toBeNull();
    svg.remove();
  });

  it('en større boks giver flere diagramlinjer (grafen strækkes ikke)', async () => {
    const lines = async (w: number, h: number) => {
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg') as SVGSVGElement;
      document.body.appendChild(svg);
      const stop = mountChartIn(svg, { x: 0, y: 0, w, h }, { ...defaultChart(), tags: ['T'] }, {});
      await vi.waitFor(() => expect(svg.querySelector('g.hv-chart polyline')).not.toBeNull());
      const n = svg.querySelectorAll('g.hv-chart line').length;
      stop();
      svg.remove();
      return n;
    };
    expect(await lines(1000, 560)).toBeGreaterThanOrEqual(await lines(200, 120));
  });
});
