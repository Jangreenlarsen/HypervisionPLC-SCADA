// Fang til objekter i Tegn: de rene beregninger (svgedit-host/snap.js).
import { describe, expect, it } from 'vitest';
// @ts-expect-error — ren JS-fil i værtsmappen til SVG-Edit (ingen typer)
import { axisAngle, centroid, directionAngle, gridCorrection, identityMatrix, invertMatrix, isDrag, multiplyMatrix, pathVertices, snapToObjects, transformBox, triangleApex, turnAxis, turnTo, unionBox } from '../../svgedit-host/snap.js';

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

describe('gridCorrection (absolut fang til gitter)', () => {
  it('lægger øverste venstre hjørne på nærmeste gitterpunkt', () => {
    expect(gridCorrection(box(543, 207, 10, 10), 10)).toEqual({ dx: -3, dy: 3 });
    expect(gridCorrection(box(546, 204, 10, 10), 10)).toEqual({ dx: 4, dy: -4 });
  });
  it('et objekt der allerede ligger på gitteret flyttes ikke (heller ikke -0)', () => {
    const r = gridCorrection(box(550, 200, 10, 10), 10);
    expect(Object.is(r.dx, 0) && Object.is(r.dy, 0)).toBe(true);
  });
  it('en kopi, der lægges ved siden af, havner på samme gitterpunkter som originalen', () => {
    const original = box(543, 207, 90, 10);
    const copy = box(543 + 20, 207 + 20, 90, 10);                          // indsat med forskydning 20,20
    const place = (b: ReturnType<typeof box>) => { const c = gridCorrection(b, 10); return { x: b.x + c.dx, y: b.y + c.dy }; };
    const a = place(original), b = place(copy);
    expect(a).toEqual({ x: 540, y: 210 });
    expect(b).toEqual({ x: 560, y: 230 });
    for (const v of [a.x, a.y, b.x, b.y]) expect(v % 10).toBe(0);
  });
  it('virker med andre trin og negative placeringer; trin 0 gør intet', () => {
    expect(gridCorrection(box(-7, 12, 5, 5), 5)).toEqual({ dx: 2, dy: -2 });
    expect(gridCorrection(box(37, 38, 5, 5), 25)).toEqual({ dx: -12, dy: 12 });
    expect(gridCorrection(box(3, 3, 1, 1), 0)).toEqual({ dx: 0, dy: 0 });
  });
});

describe('matricer', () => {
  it('multiply og invert er hinandens modsætninger; transformBox følger skalering og drejning', () => {
    const m = { a: 2, b: 0, c: 0, d: 3, e: 10, f: 20 };
    const inv = invertMatrix(m)!;
    const id = multiplyMatrix(inv, m);
    for (const k of ['a', 'b', 'c', 'd', 'e', 'f'] as const) expect(id[k]).toBeCloseTo(identityMatrix()[k]);
    expect(transformBox(box(0, 0, 10, 10), m)).toEqual(box(10, 20, 20, 30));
    expect(transformBox(box(0, 0, 10, 4), { a: 0, b: 1, c: -1, d: 0, e: 0, f: 0 })).toEqual(box(-4, 0, 4, 10));   // drejet 90°
    expect(invertMatrix({ a: 0, b: 0, c: 0, d: 0, e: 0, f: 0 })).toBeNull();
  });
});

describe('retning af en trekant (pumpens trekant)', () => {
  // Stierne er hentet fra pumperne i "varme"-tegningen
  const PUMP_D = 'm1341.3,591.13l25.64,-37.44l25.64,37.44l-51.28,0l0,0z';

  it('pathVertices læser relative linjer og fjerner degenererede/lukkende hjørner', () => {
    const v = pathVertices(PUMP_D)!;
    expect(v).toHaveLength(3);
    expect(v[0]).toEqual([1341.3, 591.13]);
    expect(v[1][0]).toBeCloseTo(1366.94);
    expect(v[1][1]).toBeCloseTo(553.69);
  });

  it('pathVertices: store bogstaver, H/V og lukkede stier; kurver giver null', () => {
    expect(pathVertices('M0 0 L10 0 L5 10 Z')).toEqual([[0, 0], [10, 0], [5, 10]]);
    expect(pathVertices('M0 0 H10 V10 H0 Z')).toEqual([[0, 0], [10, 0], [10, 10], [0, 10]]);
    expect(pathVertices('M0 0 C 5 5 10 5 10 0')).toBeNull();
    expect(pathVertices('')).toBeNull();
  });

  it('triangleApex: toppen er hjørnet med to lige lange sider; vektoren går fra grundlinjens midte til toppen', () => {
    const t = triangleApex(pathVertices(PUMP_D))!;
    expect(t.apex[1]).toBeCloseTo(553.69);                        // toppen ligger øverst (y mindst)
    expect(t.vector[0]).toBeCloseTo(0);
    expect(t.vector[1]).toBeCloseTo(-37.44);
    expect(triangleApex([[0, 0], [10, 0], [5, 8.66]])).toBeNull(); // ligesidet: ingen entydig retning
    expect(triangleApex([[0, 0], [1, 1]])).toBeNull();
  });

  it('directionAngle følger matricen: op = −90°, og drejning 180° vender den', () => {
    const t = triangleApex(pathVertices(PUMP_D))!;
    expect(directionAngle(t.vector, identityMatrix())).toBe(-90);                                            // peger opad
    expect(directionAngle(t.vector, { a: -1, b: 0, c: 0, d: -1, e: 0, f: 0 })).toBe(90);                    // rotate(180) → nedad
    expect(directionAngle(t.vector, { a: 0, b: 1, c: -1, d: 0, e: 0, f: 0 })).toBe(0);                      // rotate(90) → mod højre
    expect(directionAngle([25, 0], identityMatrix())).toBe(0);
  });

  it('turnTo: symbolets drejning så dets retning (native) rammer målet — i området −180…180', () => {
    expect(turnTo(-90, 0)).toBe(-90);       // et symbol der peger mod højre skal drejes −90° for at pege opad
    expect(turnTo(90, 0)).toBe(90);
    expect(turnTo(0, 0)).toBe(0);
    expect(turnTo(180, 0)).toBe(180);
    expect(turnTo(-180, 0)).toBe(180);
    expect(turnTo(10, 350)).toBe(20);
  });
});

describe('ventilens akse (to trekanter)', () => {
  it('centroid og axisAngle: lodret og vandret akse, uden retning', () => {
    expect(centroid([[0, 0], [6, 0], [3, 9]])).toEqual([3, 3]);
    expect(axisAngle([0, 0], [10, 0])).toBe(0);
    expect(axisAngle([10, 0], [0, 0])).toBe(0);         // samme akse uanset rækkefølge
    expect(axisAngle([0, 0], [0, 10])).toBe(90);
    expect(axisAngle([0, 10], [0, 0])).toBe(90);
    expect(axisAngle([0, 0], [10, 10])).toBe(45);
  });
  it('turnAxis: korteste drejning så symbolets akse ligger langs målaksen', () => {
    expect(turnAxis(90, 0)).toBe(90);
    expect(turnAxis(0, 0)).toBe(0);
    expect(turnAxis(135, 0)).toBe(-45);
    expect(turnAxis(0, 90)).toBe(90);
  });
});
