// Hjælpelinjer i Tegn (svgedit-host/guides.js).
import { describe, expect, it } from 'vitest';
// @ts-expect-error — ren JS uden typer
import { alignToGuide, formatGuides, guideLines, parseGuides, snapBoxToGuides, snapPointToGuides } from '../../svgedit-host/guides.js';

describe('parse/format', () => {
  it('frem og tilbage, sorteret og uden dubletter', () => {
    const g = parseGuides(formatGuides({ every: 100, v: [300, 120, 120], h: [50.123] }));
    expect(g).toEqual({ every: 100, v: [120, 300], h: [50.12] });
  });
  it('ingen linjer → null; ødelagt → tom', () => {
    expect(formatGuides({ every: 0, v: [], h: [] })).toBeNull();
    expect(parseGuides('{x')).toEqual({ every: 0, v: [], h: [] });
    expect(parseGuides(null)).toEqual({ every: 0, v: [], h: [] });
    expect(parseGuides('{"every":3,"v":["a",5]}')).toEqual({ every: 0, v: [5], h: [] });
  });
});

describe('guideLines', () => {
  it('fast inddeling + frie linjer inden for tegningen', () => {
    expect(guideLines({ every: 100, v: [150], h: [] }, 350, 220)).toEqual({ x: [100, 150, 200, 300], y: [100, 200] });
  });
});

describe('fang', () => {
  const lines = { x: [100, 300], y: [200] };
  it('kant eller midte til nærmeste linje', () => {
    expect(snapBoxToGuides({ x: 96, y: 10, w: 40, h: 20 }, lines, 8)).toEqual({ dx: 4, dy: null });
    // ingen kant/midte inden for 8 af x-linjerne (310 og 290 er begge 10 fra 300); y: midten 195 → 200
    expect(snapBoxToGuides({ x: 270, y: 185, w: 40, h: 20 }, lines, 8)).toEqual({ dx: null, dy: 5 });
  });
  it('punkt', () => {
    expect(snapPointToGuides([103, 197], lines, 8)).toEqual([100, 200]);
    expect(snapPointToGuides([150, 150], lines, 8)).toEqual([150, 150]);
  });
});

describe('alignToGuide', () => {
  const box = { x: 10, y: 20, w: 40, h: 10 };
  it('lodret linje: venstre, midte, højre', () => {
    expect(alignToGuide(box, 'l', 'v', 100)).toEqual({ dx: 90, dy: 0 });
    expect(alignToGuide(box, 'c', 'v', 100)).toEqual({ dx: 70, dy: 0 });
    expect(alignToGuide(box, 'r', 'v', 100)).toEqual({ dx: 50, dy: 0 });
  });
  it('vandret linje: top, midte, bund; forkert retning → null', () => {
    expect(alignToGuide(box, 'm', 'h', 100)).toEqual({ dx: 0, dy: 75 });
    expect(alignToGuide(box, 'l', 'h', 100)).toBeNull();
  });
});
