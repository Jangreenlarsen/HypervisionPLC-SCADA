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
    expect(parseRef(formatRef('ventil_1', [0.123456, 1]))).toEqual({ id: 'ventil_1', local: [0.1235, 1], side: null });
    expect(parseRef(formatRef('ventil_1', [1, 0.5], 'r'))).toEqual({ id: 'ventil_1', local: [1, 0.5], side: 'r' });
  });
  it('brøkdel af boksen frem og tilbage; boks uden bredde giver midten', () => {
    const box = { x: 10, y: 20, w: 100, h: 50 };
    expect(toFrac([110, 45], box)).toEqual([1, 0.5]);
    expect(fromFrac([1, 0.5], { x: 0, y: 0, w: 40, h: 10 })).toEqual([40, 5]);
    expect(toFrac([5, 5], { x: 5, y: 0, w: 0, h: 10 })).toEqual([0.5, 0.5]);
  });
  it('id med @ og ugyldige', () => {
    expect(parseRef('a@b@1,2')).toEqual({ id: 'a@b', local: [1, 2], side: null });
    expect(parseRef('v@1,2,x')).toBeNull();
    expect(parseRef('ventil')).toBeNull();
    expect(parseRef('v@x,1')).toBeNull();
    expect(parseRef(null)).toBeNull();
  });
});

it('pathD afrunder', () => {
  expect(pathD([[0, 0], [10.126, 0]])).toBe('M0 0 L10.13 0');
});

describe('v3.1.0: stier, punkter, retning og radius', async () => {
  // @ts-expect-error — ren JS uden typer
  const m = await import('../../svgedit-host/pipes.js');
  type Q = [number, number];
  const ortho = (pts: Q[]) => pts.every((p, i) => i === 0 || m.axisOf(pts[i - 1], p) !== null);

  it('pathPoints forstår buer og relative kommandoer', () => {
    expect(m.pathPoints('M0 45 H25 A20 20 0 0 0 45 25 V0')).toEqual([[0, 45], [25, 45], [45, 25], [45, 0]]);
    expect(m.pathPoints('m10 10 l5 0 c1 1 2 2 3 3')).toEqual([[10, 10], [15, 10], [18, 13]]);
    expect(m.pathPoints('M0 0 X 5')).toEqual([]);
  });

  it('punkter fra stregerne: midten af kantpunkterne, ikke boksens midte', () => {
    // ventilhus (sommerfugl) 8..72 × 27..63; teksten "AB" længere nede tæller ikke med
    const v: Q[] = [[8, 27], [40, 45], [8, 63], [72, 27], [72, 63]];
    const ports = m.portsFromVertices(v);
    expect(ports).toContainEqual({ p: [8, 45], side: 'l' });
    expect(ports).toContainEqual({ p: [72, 45], side: 'r' });
  });

  it('retning: kant → vektor, drejes og spejles med symbolet', () => {
    expect(m.fracSide([0, 0.5])).toBe('l');
    expect(m.fracSide([0.5, 1])).toBe('b');
    const rot90 = { a: 0, b: 1, c: -1, d: 0, e: 0, f: 0 };   // 90° med uret (y nedad)
    expect(m.turnDir(m.sideDir('r'), rot90)).toEqual([0, 1]);
    expect(m.turnDir(m.sideDir('l'), { a: -1, b: 0, c: 0, d: 1, e: 0, f: 0 })).toEqual([1, 0]);
  });

  it('routeBetween går STUB lige ud af begge punkter', () => {
    const r = m.routeBetween([0, 0], [100, 50], [1, 0], [-1, 0]);
    expect(r[0]).toEqual([0, 0]);
    expect(r[1][1]).toBe(0);                 // første stykke vandret
    expect(r[r.length - 1]).toEqual([100, 50]);
    expect(r[r.length - 2][1]).toBe(50);     // sidste stykke vandret ind
    expect(ortho(r)).toBe(true);
  });

  it('routeBetween: punktet vender væk fra målet → røret går ud og rundt', () => {
    const r = m.routeBetween([0, 0], [100, 0], [-1, 0], [1, 0]);
    expect(r[1]).toEqual([-m.STUB, 0]);
    expect(r[r.length - 2]).toEqual([100 + m.STUB, 0]);
    expect(ortho(r)).toBe(true);
  });

  it('reroute: drejet symbol → røret går ind fra den nye side', () => {
    const route: Q[] = [[0, 0], [60, 0], [60, 40], [120, 40]];
    const r = m.reroute(route, 'end', [120, 40], [0, 1]);   // punktet vender nu nedad
    expect(r[r.length - 1]).toEqual([120, 40]);
    expect(r[r.length - 2]).toEqual([120, 40 + m.STUB]);   // ind nedefra
    expect(r[0]).toEqual([0, 0]);
    expect(ortho(r)).toBe(true);
  });

  it('pipePath: bløde bøjninger, og knækkene kan genfindes', () => {
    const pts: Q[] = [[0, 0], [100, 0], [100, 80], [200, 80]];
    const d = m.pipePath(pts, 15);
    expect(d).toContain('A15 15');
    expect(m.pipeCorners(d)).toEqual(pts);
    expect(m.pipePath(pts, 0)).toBe(m.pathD(pts));
    expect(m.pipeCorners(m.pathD(pts))).toEqual(pts);
  });

  it('pipePath: radius lig stub-længden — der bevares lige rør ved enden, og knækkene kan genfindes', () => {
    const pts: Q[] = [[0, 0], [0, 100], [200, 100], [200, 180], [220, 180]];
    const d = m.pipePath(pts, 20);
    expect(m.pipeCorners(d)).toEqual(pts);
    expect(d).toMatch(/L220 180$/);
    expect(d).toContain('A16 16');   // sidste stykke er 20 langt → højst 80 %
  });

  it('pipePath: radius begrænses af korte stykker', () => {
    expect(m.pipePath([[0, 0], [10, 0], [10, 6], [40, 6]], 50)).toContain('A3 3');
  });
});

describe('v3.2.0: T-stykker', async () => {
  it('reroute: et gammelt knæk bag det nye punkt giver ikke en sløjfe (T-stykke flyttet)', async () => {
    // @ts-expect-error — ren JS uden typer
    const mm = await import('../../svgedit-host/pipes.js');
    const route: [number, number][] = [[100, 30], [120, 30], [120, 0], [300, 0]];   // starter i T-stykket, går til højre
    const r = mm.reroute(route, 'start', [160, 70], [1, 0]);
    const len = r.reduce((n: number, q: number[], i: number) => (i ? n + Math.hypot(q[0] - r[i - 1][0], q[1] - r[i - 1][1]) : 0), 0);
    expect(r[0]).toEqual([160, 70]);
    expect(r[r.length - 1]).toEqual([300, 0]);
    expect(len).toBeLessThanOrEqual(230);
    expect(r.every((q: number[]) => q[0] >= 160)).toBe(true);   // går aldrig tilbage til venstre for punktet
  });

  // @ts-expect-error — ren JS uden typer
  const m = await import('../../svgedit-host/pipes.js');
  type Q = [number, number];
  const route: Q[] = [[0, 0], [100, 0], [100, 80]];

  it('nearestOnRoute projicerer ind på nærmeste stykke', () => {
    expect(m.nearestOnRoute(route, [40, 7])).toEqual({ q: [40, 0], k: 0, dist: 7 });
    expect(m.nearestOnRoute(route, [104, 50])).toEqual({ q: [100, 50], k: 1, dist: 4 });
  });

  it('rørets egne ender giver ikke et T', () => {
    expect(m.nearestOnRoute(route, [-5, 0])).toBeNull();
    expect(m.nearestOnRoute(route, [100, 90])).toBeNull();
  });

  it('splitRoute deler i punktet — også i et knæk', () => {
    expect(m.splitRoute(route, 0, [40, 0])).toEqual([[[0, 0], [40, 0]], [[40, 0], [100, 0], [100, 80]]]);
    expect(m.splitRoute(route, 1, [100, 50])).toEqual([[[0, 0], [100, 0], [100, 50]], [[100, 50], [100, 80]]]);
  });

  it('sideToward og branchSide', () => {
    expect(m.sideToward([40, 0], [0, 0])).toBe('l');
    expect(m.sideToward([40, 0], [100, 0])).toBe('r');
    expect(m.sideToward([100, 50], [100, 0])).toBe('t');
    expect(m.branchSide(['l', 'r'], [40, 0], [60, 90])).toBe('b');
    expect(m.branchSide(['l', 'r'], [40, 0], [60, -90])).toBe('t');
    expect(m.branchSide(['t', 'b'], [100, 50], [10, 40])).toBe('l');
    expect(m.branchSide(['l', 'r', 'b'], [40, 0], [60, 90])).toBe('t');   // kryds: sidste ledige side
    expect(m.branchSide(['l', 'r', 't', 'b'], [40, 0], [60, 90])).toBeNull();
  });
});
