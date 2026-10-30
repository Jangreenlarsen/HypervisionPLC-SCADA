// Rør-værktøjets beregninger (svgedit-host/pipes.js).
// @ts-expect-error — ren JS uden typer
import { axisOf, connect, formatRef, fromFrac, moveEnd, nearest, orthoLeg, parseRef, pathD, portsFrom, simplify, toFrac } from '../../svgedit-host/pipes.js';
import { describe, expect, it } from 'vitest';

type P = [number, number];
const orthogonal = (pts: P[]) => pts.every((p, i) => i === 0 || axisOf(pts[i - 1], p) !== null);

describe('orthoLeg', () => {
  it('lige når punkterne flugter', () => {
    expect(orthoLeg([0, 0], [50, 0])).toEqual([[0, 0], [50, 0]]);
    expect(orthoLeg([0, 0], [0, -20])).toEqual([[0, 0], [0, -20]]);
  });
  it('ét knæk, længste retning først', () => {
    expect(orthoLeg([0, 0], [100, 20])).toEqual([[0, 0], [100, 0], [100, 20]]);
    expect(orthoLeg([0, 0], [10, 80])).toEqual([[0, 0], [0, 80], [10, 80]]);
  });
  it('valgt retning først', () => {
    expect(orthoLeg([0, 0], [100, 20], 'v')).toEqual([[0, 0], [0, 20], [100, 20]]);
  });
});

describe('connect', () => {
  it('ud og ind vandret: to knæk midtvejs', () => {
    expect(connect([0, 0], [100, 40], 'h', 'h')).toEqual([[0, 0], [50, 0], [50, 40], [100, 40]]);
  });
  it('ud vandret, ind lodret: ét knæk', () => {
    expect(connect([0, 0], [100, 40], 'h', 'v')).toEqual([[0, 0], [100, 0], [100, 40]]);
  });
  it('kun ind-retning: sidste stykke langs den', () => {
    expect(connect([0, 0], [100, 40], undefined, 'h')).toEqual([[0, 0], [0, 40], [100, 40]]);
  });
  it('flugter og retningen passer: lige', () => {
    expect(connect([0, 0], [100, 0], 'h', 'h')).toEqual([[0, 0], [100, 0]]);
  });
  it('lige over hinanden men begge vandret: lige stykke (ingen plads til et S)', () => {
    expect(connect([0, 0], [0, 80], 'h', 'h')).toEqual([[0, 0], [0, 80]]);
  });
});

describe('simplify', () => {
  it('fjerner dubletter og punkter midt på et lige stykke', () => {
    expect(simplify([[0, 0], [0, 0], [10, 0], [20, 0], [20, 5]])).toEqual([[0, 0], [20, 0], [20, 5]]);
  });
});

describe('moveEnd', () => {
  const L: P[] = [[0, 0], [100, 0], [100, 50]];
  it('slutningen flyttes langs sit lodrette stykke; nabopunktet følger på tværs', () => {
    expect(moveEnd(L, 'end', [130, 60])).toEqual([[0, 0], [130, 0], [130, 60]]);
  });
  it('starten flyttes', () => {
    const out = moveEnd(L, 'start', [0, 10]);
    expect(out).toEqual([[0, 10], [100, 10], [100, 50]]);
  });
  it('et lige rør der ikke længere flugter får et S', () => {
    const out = moveEnd([[0, 0], [100, 0]], 'end', [100, 40]);
    expect(out).toEqual([[0, 0], [50, 0], [50, 40], [100, 40]]);
    expect(orthogonal(out)).toBe(true);
  });
  it('flugter det stadig, forbliver det lige', () => {
    expect(moveEnd([[0, 0], [100, 0]], 'end', [140, 0])).toEqual([[0, 0], [140, 0]]);
  });
  it('resultatet er altid vinkelret', () => {
    const route: P[] = [[0, 0], [60, 0], [60, 40], [120, 40]];
    for (const p of [[200, -30], [10, 90], [60, 40], [-50, 5]] as P[]) {
      expect(orthogonal(moveEnd(route, 'end', p))).toBe(true);
      expect(orthogonal(moveEnd(route, 'start', p))).toBe(true);
    }
  });
});

describe('portsFrom', () => {
  it('rørender på kanten + kantmidter, uden dubletter', () => {
    // bøjning 90°: ender i (0,45) og (45,0); boks 0..45
    const ports = portsFrom([[0, 45], [25, 45], [45, 25], [45, 0]], { x: 0, y: 0, w: 45, h: 50 });
    expect(ports).toContainEqual([0, 45]);
    expect(ports).toContainEqual([45, 0]);
    expect(ports).toContainEqual([0, 25]);   // venstre kants midte
    expect(ports.filter((p: P) => p[0] === 45 && p[1] === 25).length).toBe(1);   // højre midte = hjørnepunkt → én gang
  });
});

describe('nearest', () => {
  it('inden for tolerancen', () => {
    expect(nearest([[0, 0], [10, 10]], [9, 8], 5)).toEqual([10, 10]);
    expect(nearest([[0, 0]], [9, 8], 5)).toBeNull();
  });
});

describe('ref', () => {
  it('frem og tilbage', () => {
    expect(parseRef(formatRef('ventil_1', [0.123456, 1]))).toEqual({ id: 'ventil_1', local: [0.1235, 1] });
  });
  it('brøkdel af boksen frem og tilbage; boks uden bredde giver midten', () => {
    const box = { x: 10, y: 20, w: 100, h: 50 };
    expect(toFrac([110, 45], box)).toEqual([1, 0.5]);
    expect(fromFrac([1, 0.5], { x: 0, y: 0, w: 40, h: 10 })).toEqual([40, 5]);
    expect(toFrac([5, 5], { x: 5, y: 0, w: 0, h: 10 })).toEqual([0.5, 0.5]);
  });
  it('id med @ og ugyldige', () => {
    expect(parseRef('a@b@1,2')).toEqual({ id: 'a@b', local: [1, 2] });
    expect(parseRef('ventil')).toBeNull();
    expect(parseRef('v@x,1')).toBeNull();
    expect(parseRef(null)).toBeNull();
  });
});

it('pathD afrunder', () => {
  expect(pathD([[0, 0], [10.126, 0]])).toBe('M0 0 L10.13 0');
});
