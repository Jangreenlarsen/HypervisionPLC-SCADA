// Panelets beregninger i den nye tegne-editor (svgedit-host/edit.js).
// @ts-expect-error — ren JS uden typer
import { boxMapping, distribute, editBox, round2 } from '../../svgedit-host/edit.js';
import { describe, expect, it } from 'vitest';

const apply = (m: { a: number; d: number; e: number; f: number }, x: number, y: number) => [m.a * x + m.e, m.d * y + m.f];

describe('boxMapping', () => {
  it('afbilder hjørnerne', () => {
    const m = boxMapping({ x: 10, y: 20, w: 100, h: 50 }, { x: 30, y: 40, w: 200, h: 25 });
    expect(apply(m, 10, 20)).toEqual([30, 40]);
    expect(apply(m, 110, 70)).toEqual([230, 65]);
  });
  it('ren flytning er skala 1', () => {
    const m = boxMapping({ x: 0, y: 0, w: 5, h: 5 }, { x: 7, y: -3, w: 5, h: 5 });
    expect(m).toMatchObject({ a: 1, d: 1, e: 7, f: -3 });
  });
  it('en boks uden bredde/højde skaleres ikke (ingen division med 0)', () => {
    const m = boxMapping({ x: 0, y: 0, w: 0, h: 10 }, { x: 0, y: 0, w: 50, h: 20 });
    expect(m.a).toBe(1);
    expect(m.d).toBe(2);
  });
});

describe('editBox', () => {
  const box = { x: 10, y: 10, w: 100, h: 50 };
  it('x og y flytter', () => {
    expect(editBox(box, 'x', '25')).toEqual({ ...box, x: 25 });
    expect(editBox(box, 'y', -5)).toEqual({ ...box, y: -5 });
  });
  it('0 er en gyldig placering', () => {
    expect(editBox(box, 'x', 0)).toEqual({ ...box, x: 0 });
  });
  it('bredde med og uden fast forhold', () => {
    expect(editBox(box, 'w', 200)).toEqual({ ...box, w: 200 });
    expect(editBox(box, 'w', 200, true)).toEqual({ ...box, w: 200, h: 100 });
    expect(editBox(box, 'h', 25, true)).toEqual({ ...box, w: 50, h: 25 });
  });
  it('afviser ugyldigt og for lille', () => {
    expect(editBox(box, 'w', 'abc')).toBeNull();
    expect(editBox(box, 'w', 0)).toBeNull();
    expect(editBox(box, 'h', 0.5)).toBeNull();
    expect(editBox(box, 'z', 5)).toBeNull();
  });
});

describe('distribute', () => {
  it('lige store mellemrum, yderste bliver stående', () => {
    const boxes = [{ x: 0, y: 0, w: 10, h: 10 }, { x: 15, y: 0, w: 10, h: 10 }, { x: 90, y: 0, w: 10, h: 10 }];
    expect(distribute(boxes, 'x')).toEqual([0, 30, 0]);
  });
  it('rækkefølgen i input er ligegyldig', () => {
    const boxes = [{ x: 90, y: 0, w: 10, h: 10 }, { x: 0, y: 0, w: 10, h: 10 }, { x: 15, y: 0, w: 10, h: 10 }];
    expect(distribute(boxes, 'x')).toEqual([0, 0, 30]);
  });
  it('lodret og forskellige størrelser', () => {
    const boxes = [{ x: 0, y: 0, w: 1, h: 20 }, { x: 0, y: 30, w: 1, h: 10 }, { x: 0, y: 100, w: 1, h: 40 }];
    // samlet 140, brugt 70 → mellemrum 35: 0..20, 55..65, 100..140
    expect(distribute(boxes, 'y')).toEqual([0, 25, 0]);
  });
  it('under 3 elementer flyttes intet', () => {
    expect(distribute([{ x: 0, y: 0, w: 1, h: 1 }, { x: 9, y: 0, w: 1, h: 1 }], 'x')).toEqual([0, 0]);
  });
});

it('round2', () => {
  expect(round2(1.23456)).toBe(1.23);
  expect(round2(-0.005)).toBe(-0);
});

describe('textLines (tekst fra panelet)', async () => {
  // @ts-expect-error — ren JS uden typer
  const { textLines } = await import('../../svgedit-host/edit.js');
  it('linjer, Windows-linjeskift, tomme linjer fylder en linje', () => {
    expect(textLines('Pumpe 1')).toEqual(['Pumpe 1']);
    expect(textLines('Kedel\r\nrum\n\nB')).toEqual(['Kedel', 'rum', ' ', 'B']);
    expect(textLines(null)).toEqual([' ']);
  });
});
