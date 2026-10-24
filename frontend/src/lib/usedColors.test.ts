import { describe, expect, it } from 'vitest';
import { mergePalette, paramColors, svgColors } from './usedColors';

const SVG = `<svg xmlns="http://www.w3.org/2000/svg">
  <g id="pumpe"><rect fill="#808080" stroke="#000"/><circle fill="#808080" style="stroke:red"/><path fill="none" stroke="url(#g)"/></g>
  <g id="anden"><rect fill="#00ff00"/></g></svg>`;

describe('brugte farver', () => {
  it('finder farver i animationernes parametre, også i lister og indlejrede objekter', () => {
    const anims = [
      { params: { on: '#2E7D32', off: '#9e9e9e', thresholds: [{ value: 5, color: '#b26a00' }], palette: ['#ff3b00', '#ff3b00'], speed: 3, name: 'x' } },
      { params: { base: '#abc', light: 'rød', colors: { a: '#123456' } } },
    ];
    expect(paramColors(anims)).toEqual(['#2e7d32', '#9e9e9e', '#b26a00', '#ff3b00', '#ff3b00', '#aabbcc', '#123456']);
    expect(paramColors([{}, { params: {} }])).toEqual([]);
  });

  it('finder symbolets egne farver (mest brugte først) eller hele tegningens', () => {
    expect(svgColors(SVG, 'pumpe')).toEqual(['#808080', '#000000', '#ff0000']);   // none/url(...) tæller ikke
    expect(svgColors(SVG)).toContain('#00ff00');
    expect(svgColors(SVG, 'findes-ikke')).toEqual([]);
    expect(svgColors('', 'pumpe')).toEqual([]);
  });

  it('samler en liste: første har forrang, ingen dubletter, højst max', () => {
    expect(mergePalette([['#FF0000', '#00ff00'], ['#ff0000', '#0000ff'], ['rød?', 'blue']])).toEqual(['#ff0000', '#00ff00', '#0000ff']);
    expect(mergePalette([Array.from({ length: 30 }, (_, i) => '#' + (i + 10).toString(16).padStart(2, '0').repeat(3))], 4)).toHaveLength(4);
  });
});
