import { describe, expect, it } from 'vitest';
import { chainPhases, dashOffset, fits, splitSubpaths, trimInnerEnds, type Piece } from './flowChain';

const P = (key: string, a: [number, number], b: [number, number], extra: Partial<Piece> = {}): Piece =>
  ({ key, a, b, len: Math.hypot(b[0] - a[0], b[1] - a[1]), group: 'g', dir: 1, dash: 12, speed: 40, ...extra });

/** Lys (true) eller mørk i et punkt s (tegningens enheder) langs delens egen tegneretning — som browseren tegner stiplingen. */
const litLocal = (off: number, s: number, dash: number) => ((((s + off) % (2 * dash)) + 2 * dash) % (2 * dash)) < dash;
/** Det fælles mønster langs forløbet. */
const litGlobal = (g: number, dash: number) => (((g % (2 * dash)) + 2 * dash) % (2 * dash)) < dash;

/** Stiplingen i hver del skal være det fælles mønster: tjek mange punkter (lidt væk fra skiftene). */
function expectContinuous(pieces: Piece[], dash = 12): void {
  const ph = chainPhases(pieces, 1);
  for (const p of pieces) {
    const f = ph.get(p.key)!;
    const off = dashOffset(f, dash);
    for (let s = 0.3; s < p.len; s += 1.7) {
      const g = f.orient === 1 ? f.g0 + s : f.g0 - s;
      const edge = ((g % dash) + dash) % dash;
      if (edge < 0.05 || edge > dash - 0.05) continue;
      expect(litLocal(off, s, dash), `${p.key} s=${s.toFixed(1)}`).toBe(litGlobal(g, dash));
    }
  }
}

describe('sammenhængende løbelys', () => {
  it('to rør i forlængelse: det andet fortsætter, hvor det første slap', () => {
    const ph = chainPhases([P('A', [0, 0], [100, 0]), P('B', [100, 0], [250, 0])], 1);
    expect(ph.get('A')).toMatchObject({ g0: 0, orient: 1 });
    expect(ph.get('B')).toMatchObject({ g0: 100, orient: 1 });
    expectContinuous([P('A', [0, 0], [100, 0]), P('B', [100, 0], [250, 0])]);
  });

  it('et rør tegnet baglæns MED "Vend retning": retningerne passer, så det kobles, og mønstret fortsætter', () => {
    const pieces = [P('A', [0, 0], [100, 0]), P('B', [250, 0], [100, 0], { dir: -1 })];
    const ph = chainPhases(pieces, 1);
    expect(ph.get('B')).toMatchObject({ g0: 250, orient: -1 });
    expectContinuous(pieces);
  });

  it('et rør tegnet baglæns UDEN "Vend retning": lyset løber mod hinanden — den indstillede retning gælder, ingen kobling', () => {
    const ph = chainPhases([P('A', [0, 0], [100, 0]), P('B', [250, 0], [100, 0])], 1);
    expect(ph.get('B')).toMatchObject({ g0: 0, orient: 1 });
  });

  it('rør → bøjning → rør (bue længere end afstanden mellem enderne) og vilkårlige ulige længder', () => {
    const bend = { ...P('B', [100.3, 0], [120, 20]), len: 31.42 };
    const pieces = [P('A', [0, 0], [100, 0]), bend, P('C', [120, 120], [120, 20.4], { dir: -1 }), P('D', [120, 120], [120, 333.3])];
    const ph = chainPhases(pieces, 1);
    expect(ph.get('B')!.g0).toBeCloseTo(100);
    expect(ph.get('C')).toMatchObject({ orient: -1 });
    expect(ph.get('C')!.g0).toBeCloseTo(231.02);   // 131,42 + rør C's længde 99,6
    expect(ph.get('D')!.g0).toBeCloseTo(231.02);   // 131,42 + rør C's længde 99,6
    expectContinuous(pieces);
  });

  it('kun dele i samme gruppe og inden for tolerancen hænger sammen', () => {
    const ph = chainPhases([P('A', [0, 0], [100, 0]), P('B', [100, 0], [200, 0], { group: 'andet tag' }), P('C', [103, 0], [200, 0])], 1);
    expect(ph.get('B')!.g0).toBe(0);
    expect(ph.get('C')!.g0).toBe(0);
  });

  it('fits: lyset skal løbe ind i samlingen fra den ene del og ud i den anden', () => {
    expect(fits({ dir: 1 }, 'b', { dir: 1 }, 'a')).toBe(true);     // → →
    expect(fits({ dir: 1 }, 'b', { dir: 1 }, 'b')).toBe(false);    // → ← (mod hinanden)
    expect(fits({ dir: -1 }, 'a', { dir: -1 }, 'b')).toBe(true);   // ← ←
    expect(fits({ dir: -1 }, 'a', { dir: 1 }, 'a')).toBe(true);    // p løber ind mod sin a, q væk fra sin a: én strøm
    expect(fits({ dir: 1 }, 'a', { dir: 1 }, 'a')).toBe(false);    // begge løber væk fra samlingen
    expect(fits({ dir: 1 }, 'a', { dir: 1 }, 'b')).toBe(true);     // lyset løber fra q ind i p
    expect(fits({ dir: 0 }, 'b', { dir: 1 }, 'b')).toBe(true);     // ukendt retning: kobles
  });

  it('et forløb brydes, hvor retningerne ikke passer — delene før og efter kører hver for sig', () => {
    // A → B → | ← C | D →   (C er tegnet 300→200 uden "Vend retning": løber mod B; D er tegnet 300→400: løber væk fra C)
    const ph = chainPhases([P('A', [0, 0], [100, 0]), P('B', [100, 0], [200, 0]), P('C', [300, 0], [200, 0]), P('D', [300, 0], [400, 0])], 1);
    expect(ph.get('B')!.g0).toBe(100);                          // A–B passer
    expect(ph.get('C')).toMatchObject({ g0: 0, orient: 1 });   // B–C mod hinanden: C starter sit eget forløb
    expect(ph.get('D')).toMatchObject({ g0: 0, orient: 1 });   // C–D væk fra hinanden: D kører for sig
  });

  it('ugyldige dele (længde 0, NaN) får standardværdier og bryder ikke forløbet', () => {
    const ph = chainPhases([P('A', [0, 0], [100, 0]), { ...P('Z', [100, 0], [100, 0]), len: 0 }, P('N', [NaN, 0], [1, 1])], 1);
    expect(ph.get('Z')).toMatchObject({ g0: 0, orient: 1 });
    expect(ph.get('N')).toMatchObject({ g0: 0, orient: 1 });
  });

  it('forskydningen ligger altid i [0, 2·dash)', () => {
    for (const g0 of [-500, -13, 0, 7, 24, 999.5]) {
      for (const orient of [1, -1] as const) {
        const o = dashOffset({ g0, orient }, 12);
        expect(o).toBeGreaterThanOrEqual(0);
        expect(o).toBeLessThan(24);
      }
    }
  });

  it('forløbet bruger den lyslængde og fart, flest dele har; en enkelt del beholder sin egen', () => {
    const ph = chainPhases([P('A', [0, 0], [100, 0], { dash: 40 }), P('B', [100, 0], [200, 0]), P('C', [200, 0], [300, 0]), P('X', [0, 50], [9, 50], { dash: 7, speed: 3 })], 1);
    expect([...'ABC'].map((k) => [ph.get(k)!.dash, ph.get(k)!.speed])).toEqual([[12, 40], [12, 40], [12, 40]]);
    expect(ph.get('X')).toMatchObject({ dash: 7, speed: 3 });
  });
});

describe('nærmeste ender', () => {
  it('et kort rør mellem et T-stykke og en bøjning: enderne kobles til det korte rør, ikke hen over det', () => {
    // T-stykkets afgrening ender i x=1548,9, det korte rør går 1549,1 → 1540,4, bøjningen starter i 1541 (7,9 fra T-stykket)
    const pieces = [
      P('T', [1593.9, 478.6], [1548.9, 433.6]),
      P('kort', [1549.1, 433.6], [1540.4, 433.6]),
      { ...P('bøjning', [1541, 433.6], [1496, 477.5]), len: 63.6 },
    ];
    const ph = chainPhases(pieces, 8);
    const T = ph.get('T')!, K = ph.get('kort')!, B = ph.get('bøjning')!;
    const lenT = pieces[0].len;
    expect(K.g0).toBeCloseTo(T.g0 + lenT);           // det korte rør fortsætter, hvor T-stykket slap
    expect(B.g0).toBeCloseTo(K.g0 + 8.7);            // bøjningen fortsætter efter det korte rør
  });
  it('tre ender i samme punkt (kryds) kobles alle', () => {
    const ph = chainPhases([P('A', [0, 0], [100, 0]), P('B', [100, 0], [200, 0]), P('C', [100, 0], [100, 100])], 1);
    expect(ph.get('B')!.g0).toBe(100);
    expect(ph.get('C')!.g0).toBe(100);
  });
});

describe('delstier', () => {
  it('T-stykke: absolut og relativ (som SVG-Edit gemmer den)', () => {
    expect(splitSubpaths('M0 45 H90 M45 45 V0')).toEqual(['M0 45 H90', 'M45 45 V0']);
    expect(splitSubpaths('m0,45l90,0m-45,0l0,-45')).toEqual(['M0 45 l90 0', 'M45 45 l0 -45']);
  });
  it('buer, kurver, Z og implicitte linjer efter M', () => {
    expect(splitSubpaths('M0 0 A20 20 0 0 0 20 20 m10 0 c1 1 2 2 3 3 z m5 5 l1 1')).toEqual(['M0 0 A20 20 0 0 0 20 20', 'M30 20 c1 1 2 2 3 3 z', 'M35 25 l1 1']);
    expect(splitSubpaths('M0 0 10 0 20 0')).toEqual(['M0 0 L10 0 L20 0']);
    expect(splitSubpaths('M1 2 H5')).toEqual(['M1 2 H5']);
  });
  it('ulæselige stier → null', () => {
    expect(splitSubpaths('L5 5')).toBeNull();
    expect(splitSubpaths('M0 0 X5')).toBeNull();
    expect(splitSubpaths('M0 0 L5')).toBeNull();
  });
});

describe('T-stykkets afgrening starter ved gennemløbets kant', () => {
  it('bibliotekets T-stykke (absolut og relativt som SVG-Edit gemmer det)', () => {
    expect(trimInnerEnds(['M0 45 H90', 'M45 45 V0'], 10)).toEqual(['M0 45 H90', 'M45 40 L45 0']);
    expect(trimInnerEnds(splitSubpaths('m0,45l90,0m-45,0l0,-45')!, 10)).toEqual(['M0 45 l90 0', 'M45 40 L45 0']);
  });
  it('afgrening tegnet mod gennemløbet: slutningen trækkes tilbage', () => {
    expect(trimInnerEnds(['M0 45 H90', 'M45 0 V45'], 10)).toEqual(['M0 45 H90', 'M45 0 L45 40']);
  });
  it('kryds, ender der mødes og buer røres ikke', () => {
    expect(trimInnerEnds(['M0 45 H90', 'M45 0 V90'], 10)).toEqual(['M0 45 H90', 'M45 0 V90']);
    expect(trimInnerEnds(['M0 0 H50', 'M50 0 V50'], 10)).toEqual(['M0 0 H50', 'M50 0 V50']);
    expect(trimInnerEnds(['M0 45 H90', 'M45 45 A20 20 0 0 0 65 25'], 10)).toEqual(['M0 45 H90', 'M45 45 A20 20 0 0 0 65 25']);
  });
  it('for kort afgrening eller ulæselig sti: uændret', () => {
    expect(trimInnerEnds(['M0 45 H90', 'M45 45 V42'], 10)).toEqual(['M0 45 H90', 'M45 45 V42']);
    expect(trimInnerEnds(['M0 45 H90', 'L5 5'], 10)).toEqual(['M0 45 H90', 'L5 5']);
  });
});
