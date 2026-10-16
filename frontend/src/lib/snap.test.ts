// Fang til objekter i Tegn: de rene beregninger (svgedit-host/snap.js).
import { describe, expect, it } from 'vitest';
// @ts-expect-error — ren JS-fil i værtsmappen til SVG-Edit (ingen typer)
import { isDrag, snapToObjects, unionBox } from '../../svgedit-host/snap.js';

const box = (x: number, y: number, w: number, h: number) => ({ x, y, w, h });

describe('unionBox', () => {
  it('rummer alle bokse; ingen bokse giver null', () => {
    expect(unionBox([box(0, 0, 10, 10), box(20, 5, 10, 10)])).toEqual(box(0, 0, 30, 15));
    expect(unionBox([null, box(1, 2, 3, 4)])).toEqual(box(1, 2, 3, 4));
    expect(unionBox([])).toBeNull();
  });
});

describe('snapToObjects', () => {
  const A = box(0, 0, 80, 50);

  it('lægger kant mod kant, når den er tæt nok', () => {
    const r = snapToObjects(box(84, 0, 60, 90), [A], 8);          // B's venstre kant 4 fra A's højre kant (80)
    expect(r).toMatchObject({ dx: -4, guideX: 80 });
  });

  it('fanger også midte mod midte og højre mod venstre', () => {
    expect(snapToObjects(box(26, 100, 30, 10), [A], 8).dx).toBe(-1);     // midten 41 → A's midte 40
    expect(snapToObjects(box(52, 100, 30, 10), [A], 8).dx).toBe(-2);     // højre kant 82 → A's højre 80
  });

  it('gør intet uden for fangafstanden', () => {
    expect(snapToObjects(box(100, 100, 20, 20), [A], 8)).toEqual({ dx: 0, dy: 0, guideX: null, guideY: null });
  });

  it('X og Y afgøres hver for sig', () => {
    const r = snapToObjects(box(83, 57, 20, 20), [A], 8);          // venstre 83→80 (dx −3), top 57→50 (dy −7)
    expect(r).toMatchObject({ dx: -3, dy: -7, guideX: 80, guideY: 50 });
    expect(snapToObjects(box(83, 200, 20, 20), [A], 8)).toMatchObject({ dx: -3, dy: 0, guideY: null });
  });

  it('vælger det nærmeste af flere objekter og ignorerer dem der er for langt væk', () => {
    const r = snapToObjects(box(84, 0, 10, 10), [box(200, 0, 10, 10), A, box(300, 300, 5, 5)], 8);
    expect(r.dx).toBe(-4);                                          // kun A er inden for afstanden
    const nearer = snapToObjects(box(84, 0, 10, 10), [A, box(86, 300, 5, 5)], 8);
    expect(nearer.dx).toBe(-0.5);                                   // det andet objekts midte (88,5) ligger tættere på vores midte (89) end A
  });

  it('uden andre objekter sker der ingenting', () => {
    expect(snapToObjects(box(1, 1, 5, 5), [], 8)).toEqual({ dx: 0, dy: 0, guideX: null, guideY: null });
  });
});

describe('isDrag', () => {
  it('en flytning med samme størrelse over flere pixel er et træk', () => {
    expect(isDrag(box(0, 0, 50, 50), box(40, 0, 50, 50))).toBe(true);
  });
  it('en piletast-justering (1–3 px) er ikke et træk — så fanger vi ikke tilbage', () => {
    expect(isDrag(box(0, 0, 50, 50), box(1, 0, 50, 50))).toBe(false);
    expect(isDrag(box(0, 0, 50, 50), box(0, 3, 50, 50))).toBe(false);
  });
  it('en ændring af størrelsen (skalering) er ikke en flytning', () => {
    expect(isDrag(box(0, 0, 50, 50), box(40, 0, 80, 50))).toBe(false);
  });
  it('mangler en boks, er det ikke et træk', () => {
    expect(isDrag(null, box(0, 0, 1, 1))).toBe(false);
  });
});
