import { describe, expect, it } from 'vitest';
import { clampView, MAX_ZOOM, panBy, pickDrawing, zoomAt, zoomLevel } from './viewport';

const FULL = { x: 0, y: 0, w: 1000, h: 500 };

describe('pickDrawing', () => {
  const list = [{ id: 'a' }, { id: 'b', start: true }, { id: 'c' }];
  it('adressen vinder, så sidst viste, så start-tegningen, så den første', () => {
    expect(pickDrawing(list, 'c', 'a')).toBe('c');
    expect(pickDrawing(list, undefined, 'a')).toBe('a');
    expect(pickDrawing(list, undefined, null)).toBe('b');
    expect(pickDrawing([{ id: 'a' }, { id: 'c' }], undefined, null)).toBe('a');
  });
  it('ukendte/ikke-tilladte id-er springes over', () => {
    expect(pickDrawing(list, 'x', 'y')).toBe('b');
    expect(pickDrawing([], 'a', 'a')).toBe('');
  });
});

describe('zoom og panorering', () => {
  it('zoom om et punkt lader punktet stå stille', () => {
    const v = zoomAt(FULL, FULL, 2, 250, 100);
    expect(v).toEqual({ x: 125, y: 50, w: 500, h: 250 });
    expect(zoomLevel(v, FULL)).toBe(2);
  });
  it('kan ikke zoome ud forbi hele tegningen eller ind forbi MAX_ZOOM', () => {
    expect(zoomAt(FULL, FULL, 0.5, 500, 250)).toEqual(FULL);
    expect(zoomLevel(zoomAt(FULL, FULL, 1000, 500, 250), FULL)).toBe(MAX_ZOOM);
  });
  it('panorering holdes inden for tegningen', () => {
    const v = { x: 100, y: 100, w: 500, h: 250 };
    expect(panBy(v, FULL, -1000, 0).x).toBe(0);
    expect(panBy(v, FULL, 1000, 1000)).toEqual({ x: 500, y: 250, w: 500, h: 250 });
  });
  it('clampView bevarer tegningens proportioner', () => {
    const v = clampView({ x: 0, y: 0, w: 400, h: 999 }, FULL);
    expect(v.h).toBe(200);
  });
});
