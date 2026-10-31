// Genvej mellem Tegn og symbol-editoren (symbolRoute.ts).
import { describe, expect, it } from 'vitest';
import { drawHref, parseSymbolRoute, symbolsHref } from './symbolRoute';

describe('symbolRoute', () => {
  it('frem og tilbage', () => {
    expect(symbolsHref('kedel rum', 'pumpe')).toBe('#symbols/kedel%20rum/pumpe');
    expect(parseSymbolRoute(symbolsHref('kedel rum', 'pumpe').slice(1))).toEqual({ drawing: 'kedel rum', type: 'pumpe', fromDraw: true });
  });
  it('ny tegning og uden symbol', () => {
    expect(symbolsHref(null, null)).toBe('#symbols/ny');
    expect(parseSymbolRoute('symbols/ny')).toEqual({ drawing: null, type: null, fromDraw: true });
    expect(parseSymbolRoute('symbols/ny/ventil')).toEqual({ drawing: null, type: 'ventil', fromDraw: true });
  });
  it('direkte fra menuen: ingen tilbage-knap', () => {
    expect(parseSymbolRoute('symbols')).toEqual({ drawing: null, type: null, fromDraw: false });
  });
  it('ødelagt kodning giver null i stedet for en fejl', () => {
    expect(parseSymbolRoute('symbols/%E0%A4%A/x').drawing).toBeNull();
  });
  it('drawHref', () => {
    expect(drawHref('a b')).toBe('#draw/a%20b');
    expect(drawHref(null)).toBe('#draw');
  });
});
