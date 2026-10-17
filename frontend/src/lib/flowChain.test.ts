import { describe, expect, it } from 'vitest';
import { chainPhases, dashOffset, type Piece } from './flowChain';

const P = (key: string, a: [number, number], b: [number, number], extra: Partial<Piece> = {}): Piece =>
  ({ key, a, b, len: Math.hypot(b[0] - a[0], b[1] - a[1]), group: 'g', dir: 1, ...extra });

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
    expect(ph.get('A')).toEqual({ g0: 0, orient: 1, flip: false });
    expect(ph.get('B')).toEqual({ g0: 100, orient: 1, flip: false });
    expectContinuous([P('A', [0, 0], [100, 0]), P('B', [100, 0], [250, 0])]);
  });

  it('et rør tegnet baglæns: koordinaten falder langs det, og det vendes så det følger naboen', () => {
    const pieces = [P('A', [0, 0], [100, 0]), P('B', [250, 0], [100, 0])];
    const ph = chainPhases(pieces, 1);
    expect(ph.get('B')).toEqual({ g0: 250, orient: -1, flip: true });
    expectContinuous(pieces);
  });

  it('rør → bøjning → rør (bue længere end afstanden mellem enderne) og vilkårlige ulige længder', () => {
    const bend = { ...P('B', [100.3, 0], [120, 20]), len: 31.42 };
    const pieces = [P('A', [0, 0], [100, 0]), bend, P('C', [120, 120], [120, 20.4]), P('D', [120, 120], [120, 333.3])];
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

  it('retningen: flertallet bestemmer; "Vend retning" på alle vender hele forløbet; T-stykkets ben vendes aldrig', () => {
    const chain = (dir: 1 | -1) => [P('A', [0, 0], [100, 0], { dir }), P('B', [100, 0], [200, 0], { dir }), P('C', [300, 0], [200, 0], { dir })];
    let ph = chainPhases(chain(1), 1);
    expect([...'ABC'].map((k) => ph.get(k)!.flip)).toEqual([false, false, true]);
    ph = chainPhases(chain(-1), 1);
    expect([...'ABC'].map((k) => ph.get(k)!.flip)).toEqual([false, false, true]);   // alle vendt: samme dele følger flertallet
    ph = chainPhases([P('A', [0, 0], [100, 0]), P('T1', [150, 0], [100, 0], { dir: 0 }), P('T2', [150, 0], [200, 0], { dir: 0 })], 1);
    expect(ph.get('T1')!.flip).toBe(false);
    expect(ph.get('T2')!.flip).toBe(false);
  });

  it('uafgjort: den første del bestemmer; en enkelt del er uændret', () => {
    const ph = chainPhases([P('A', [0, 0], [100, 0]), P('B', [200, 0], [100, 0])], 1);
    expect(ph.get('A')!.flip).toBe(false);
    expect(ph.get('B')!.flip).toBe(true);
    expect(chainPhases([P('X', [5, 5], [50, 5])], 1).get('X')).toEqual({ g0: 0, orient: 1, flip: false });
  });

  it('ugyldige dele (længde 0, NaN) får standardværdier og bryder ikke forløbet', () => {
    const ph = chainPhases([P('A', [0, 0], [100, 0]), { ...P('Z', [100, 0], [100, 0]), len: 0 }, P('N', [NaN, 0], [1, 1])], 1);
    expect(ph.get('Z')).toEqual({ g0: 0, orient: 1, flip: false });
    expect(ph.get('N')).toEqual({ g0: 0, orient: 1, flip: false });
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
});
