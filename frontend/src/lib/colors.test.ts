// Farver på valgte symboler i Tegn: de rene funktioner (svgedit-host/colors.js).
import { describe, expect, it } from 'vitest';
// @ts-expect-error — ren JS-fil i værtsmappen til SVG-Edit (ingen typer)
import { collectColors, colorsOf, normColor, recolorAttrs } from '../../svgedit-host/colors.js';

describe('farver i Tegn', () => {
  it('normaliserer farver og kender "ingen farve"', () => {
    expect(normColor('#555')).toBe('#555555');
    expect(normColor(' #9E9E9E ')).toBe('#9e9e9e');
    expect(normColor('rgb(255, 0, 16)')).toBe('#ff0010');
    expect(normColor('White')).toBe('#ffffff');
    for (const v of ['none', 'transparent', 'url(#g1)', 'currentColor', '', '   ', null, undefined, 'blåfarve']) expect(normColor(v)).toBeNull();
  });

  it('samler farver fra attributter og style, mest brugte først', () => {
    expect(colorsOf({ fill: '#555', stroke: 'none', style: 'stroke:#fff; opacity:.5' })).toEqual(['#555555', '#ffffff']);
    expect(collectColors([{ fill: '#555' }, { stroke: '#555555' }, { fill: '#fff' }, { fill: 'none' }]))
      .toEqual([{ color: '#555555', uses: 2 }, { color: '#ffffff', uses: 1 }]);
    expect(collectColors([])).toEqual([]);
  });

  it('skifter kun den valgte farve og bevarer resten af style', () => {
    expect(recolorAttrs({ fill: '#555', stroke: '#555555' }, '#555555', '#1e88e5')).toEqual({ fill: '#1e88e5', stroke: '#1e88e5' });
    expect(recolorAttrs({ fill: '#fff', stroke: '#555' }, '#555', '#ff0000')).toEqual({ stroke: '#ff0000' });
    expect(recolorAttrs({ style: 'fill:#555;opacity:0.5;stroke:none' }, '#555', '#00ff00')).toEqual({ style: 'fill:#00ff00;opacity:0.5;stroke:none' });
    expect(recolorAttrs({ fill: '#fff' }, '#555', '#000')).toBeNull();
    expect(recolorAttrs({ fill: '#555' }, '#555', 'none')).toBeNull();   // ugyldig ny farve
  });
});
