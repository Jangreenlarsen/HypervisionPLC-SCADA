// Genvej mellem Tegn og symbol-editoren (symbolRoute.ts).
import { describe, expect, it } from 'vitest';
import { drawHref, parseSymbolRoute, symbolsHref } from './symbolRoute';

describe('symbolRoute', () => {
  it('frem og tilbage', () => {
    expect(symbolsHref('kedel rum', 'pumpe')).toBe('#symbols/kedel%20rum/pumpe');
    expect(parseSymbolRoute(symbolsHref('kedel rum', 'pumpe').slice(1))).toEqual({ drawing: 'kedel rum', type: 'pumpe', fromDraw: true, tab: null });
  });
  it('ny tegning og uden symbol', () => {
    expect(symbolsHref(null, null)).toBe('#symbols/ny');
    expect(parseSymbolRoute('symbols/ny')).toEqual({ drawing: null, type: null, fromDraw: true, tab: null });
    expect(parseSymbolRoute('symbols/ny/ventil')).toEqual({ drawing: null, type: 'ventil', fromDraw: true, tab: null });
  });
  it('direkte fra menuen: ingen tilbage-knap', () => {
    expect(parseSymbolRoute('symbols')).toEqual({ drawing: null, type: null, fromDraw: false, tab: null });
  });
  it('ødelagt kodning giver null i stedet for en fejl', () => {
    expect(parseSymbolRoute('symbols/%E0%A4%A/x').drawing).toBeNull();
  });
  it('drawHref', () => {
    expect(drawHref('a b')).toBe('#draw/a%20b');
    expect(drawHref(null)).toBe('#draw');
  });
});

describe('symbolet i centrum (v6.11.0)', () => {
  it('fanen står som fjerde led, og "-" betyder ikke åbnet fra Tegn', async () => {
    const { panelHref } = await import('./symbolRoute');
    expect(parseSymbolRoute('symbols/kedel/pumpe/veje')).toEqual({ drawing: 'kedel', type: 'pumpe', fromDraw: true, tab: 'veje' });
    expect(parseSymbolRoute('symbols/-/pumpe/punkter')).toEqual({ drawing: null, type: 'pumpe', fromDraw: false, tab: 'punkter' });
    expect(parseSymbolRoute('symbols/-/pumpe/noget')).toMatchObject({ tab: null });
    expect(parseSymbolRoute('symbols/organiser')).toEqual({ drawing: null, type: null, fromDraw: false, tab: null });   // ikke en tegning
    expect(symbolsHref('kedel', 'pumpe', 'veje')).toBe('#symbols/kedel/pumpe/veje');
    expect(panelHref(null, false, 'u_x y', 'punkter')).toBe('#symbols/-/u_x%20y/punkter');
    expect(panelHref(null, true, 'pumpe', 'veje')).toBe('#symbols/ny/pumpe/veje');
    expect(panelHref('kedel', true, 'pumpe', 'veje')).toBe('#symbols/kedel/pumpe/veje');
  });
});
