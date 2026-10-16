// Tests for logikblokke (v0.44/0.45), tekst-beregning (v0.41) og sletning af tegning (v0.42).
import { afterEach, describe, expect, it, vi } from 'vitest';
import { compileExpression, evalExpression, expressionError } from './expression';
import { formatValue } from './animate';
import { deleteDrawingFlow, deleteWarning, type DrawingUsage } from './drawingDelete';
import {
  describeBlock, emptyConfig, evalLogic, isLogicRef, newBlock, removeBlock, type LogicBlock, type LogicInput,
} from './symbolConfig';

const inp = (src: string, extra: Partial<LogicInput> = {}): LogicInput => ({ src, neg: false, cmp: '', value: null, ...extra });
const blk = (id: string, op: 'and' | 'or', inputs: LogicInput[], invert = false): LogicBlock => ({ id, name: '', op, inputs, invert });
const vals = (m: Record<string, unknown>) => (t: string) => m[t];

describe('evalLogic (samme regler som serveren)', () => {
  it('AND/OR med NOT pr. indgang og på resultatet', () => {
    const v = vals({ Pumpe: true, Alarm: false });
    expect(evalLogic([blk('L1', 'and', [inp('Pumpe'), inp('Alarm', { neg: true })])], v).L1).toBe(true);
    expect(evalLogic([blk('L1', 'and', [inp('Pumpe'), inp('Alarm')], true)], v).L1).toBe(true);   // NAND
    expect(evalLogic([blk('L1', 'or', [inp('Pumpe'), inp('Alarm')], true)], v).L1).toBe(false);   // NOR
  });

  it('tal-tags sammenlignes; nul er Fra, ikke-nul er Til', () => {
    const v = vals({ T: 70, Nul: 0, Et: 1 });
    expect(evalLogic([blk('L1', 'and', [inp('T', { cmp: 'ge', value: 70 })])], v).L1).toBe(true);
    expect(evalLogic([blk('L1', 'and', [inp('T', { cmp: 'le', value: 69.9 })])], v).L1).toBe(false);
    expect(evalLogic([blk('L1', 'and', [inp('T', { cmp: 'eq', value: 70 })])], v).L1).toBe(true);
    expect(evalLogic([blk('L1', 'and', [inp('Nul')])], v).L1).toBe(false);
    expect(evalLogic([blk('L1', 'and', [inp('Et')])], v).L1).toBe(true);
  });

  it('ukendt: en afgørende indgang vinder, ellers ukendt (null)', () => {
    const v = vals({ A: true, B: false });   // X er ukendt (undefined)
    expect(evalLogic([blk('L1', 'and', [inp('X'), inp('B')])], v).L1).toBe(false);
    expect(evalLogic([blk('L1', 'or', [inp('X'), inp('A')])], v).L1).toBe(true);
    expect(evalLogic([blk('L1', 'and', [inp('X'), inp('A')])], v).L1).toBeNull();
    expect(evalLogic([blk('L1', 'or', [inp('X'), inp('B')])], v).L1).toBeNull();
    expect(evalLogic([blk('L1', 'and', [inp('X', { neg: true })])], v).L1).toBeNull();
    expect(evalLogic([blk('L1', 'and', [inp('Tekst')])], vals({ Tekst: 'hej' })).L1).toBeNull();
  });

  it('to niveauer og blokke i andre symboler', () => {
    const v = vals({ Pumpe: true, Ventil: true, Nød: false });
    const out = evalLogic([blk('L1', 'and', [inp('Pumpe'), inp('Ventil')]), blk('L2', 'or', [inp('@L1'), inp('Nød')]),
      blk('L3', 'and', [inp('@L2', { neg: true }), inp('Pumpe')])], v);
    expect(out).toEqual({ L1: true, L2: true, L3: false });
    const foreign = (ref: string) => (ref === '@pumpe:L1' ? true : null);
    expect(evalLogic([blk('L1', 'and', [inp('@pumpe:L1'), inp('Pumpe')])], v, foreign).L1).toBe(true);
    expect(evalLogic([blk('L1', 'and', [inp('@andet:L1')])], v, foreign).L1).toBeNull();
  });
});

describe('logik-hjælpere', () => {
  it('isLogicRef skelner blok fra position og tag', () => {
    expect(isLogicRef('@L1')).toBe(true);
    expect(isLogicRef('@pumpe:L1')).toBe(true);
    expect(isLogicRef('@pos')).toBe(false);
    expect(isLogicRef('Pumpe')).toBe(false);
  });

  it('newBlock tager første ledige id og har to tomme indgange', () => {
    const c = emptyConfig();
    expect(newBlock(c).id).toBe('L1');
    c.logic.push(blk('L1', 'and', []), blk('L3', 'and', []));
    const b = newBlock(c);
    expect(b.id).toBe('L2');
    expect(b.inputs).toHaveLength(2);
  });

  it('removeBlock tømmer henvisninger til blokken i indgange og animationer', () => {
    const c = emptyConfig();
    c.logic = [blk('L1', 'and', [inp('A')]), blk('L2', 'and', [inp('@L1'), inp('B')])];
    c.anims = [{ part: 'all', type: 'visible', src: '@L1', params: {}, only: null }, { part: 'all', type: 'blink', src: '@L2', params: {}, only: null }];
    removeBlock(c, 'L1');
    expect(c.logic.map((b) => b.id)).toEqual(['L2']);
    expect(c.logic[0].inputs[0].src).toBe('');
    expect(c.anims.map((a) => a.src)).toEqual(['', '@L2']);
  });

  it('describeBlock giver formlen', () => {
    expect(describeBlock(blk('L1', 'and', [inp('Pumpe'), inp('Alarm', { neg: true })]))).toBe('Pumpe AND NOT Alarm');
    expect(describeBlock(blk('L1', 'or', [inp('T', { cmp: 'ge', value: 80 }), inp('@L2')], true))).toBe('NOT (T ≥ 80 OR L2)');
    expect(describeBlock(blk('L1', 'and', [inp('')]))).toBe('?');
  });
});

describe('beregning på tekst (expression)', () => {
  it.each([
    ['x / 10', 128, 12.8], ['parameter / 10', 128, 12.8], ['x * 1,8 + 32', 100, 212], ['round(x / 10)', 125, 13],
    ['round(x / 10)', -125, -13], ['abs(x)', -4, 4], ['min(x; 5)', 9, 5], ['max(x; 5)', 9, 9], ['sqrt(x)', 16, 4],
    ['floor(x / 3)', 10, 3], ['ceil(x / 3)', 10, 4], ['x % 5', 12, 2], ['-x + 1', 3, -2], ['(x + 2) * 3', 1, 9],
  ])('%s med x=%s giver %s', (src, x, expected) => {
    expect(evalExpression(src, x)).toBeCloseTo(expected, 9);
  });

  it('division med 0 og sqrt af negativt giver ingen værdi', () => {
    expect(evalExpression('x / 0', 5)).toBeNull();
    expect(evalExpression('x % 0', 5)).toBeNull();
    expect(evalExpression('sqrt(x)', -1)).toBeNull();
  });

  it.each([
    ['x +', 'slutter for tidligt'], ['foo', 'Ukendt navn'], ['bar(x)', 'Ukendt funktion'], ['(x', 'Manglende'],
    ['x $ 2', 'Uventet tegn'], ['x x', 'regnetegn'], ['min(x)', 'tager 2-8'], ['', 'Tomt'],
  ])('ugyldigt udtryk "%s" giver en dansk fejl', (src, part) => {
    expect(() => compileExpression(src)).toThrow(part);
  });

  it('expressionError: tom er ok, ugyldig giver tekst, for langt afvises', () => {
    expect(expressionError('')).toBe('');
    expect(expressionError('   ')).toBe('');
    expect(expressionError('x / 10')).toBe('');
    expect(expressionError('x +')).toContain('slutter');
    expect(expressionError('x + '.repeat(30) + '1')).toContain('For langt');
  });

  it('formatValue: beregning før decimaler og enhed; ugyldig/ikke-endelig = tankestreg', () => {
    const meta = { unit: '°C' } as never;
    expect(formatValue(128, meta, { expression: 'x / 10', decimals: 1 })).toBe('12.8 °C');
    expect(formatValue(128, meta, { expression: 'x / 10', decimals: 0 })).toBe('13 °C');
    expect(formatValue(5, meta, { expression: 'x / 0' })).toBe('—');
    expect(formatValue(128, meta, { expression: '' , decimals: 0 })).toBe('128 °C');
  });
});

describe('slet tegning', () => {
  const usage = (over: Partial<DrawingUsage> = {}): DrawingUsage => ({
    id: 'd', name: 'Anlæg', versions: 3, bindings: 12, goto_from: [], start: false, users: [], ...over,
  });

  it('bekræftelsen nævner kun det der rammes', () => {
    const plain = deleteWarning(usage());
    expect(plain).toContain('Slet tegningen "Anlæg"?');
    expect(plain).toContain('3 versioner og 12 bindinger');
    expect(plain).not.toContain('start-tegning');
    expect(plain).not.toContain('gå til');
    const full = deleteWarning(usage({ versions: 1, bindings: 1, goto_from: ['Oversigt'], start: true, users: ['olsen'] }));
    expect(full).toContain('1 version og 1 binding ');
    expect(full).toContain('Oversigt');
    expect(full).toContain('start-tegning');
    expect(full).toContain('olsen');
  });

  describe('flow', () => {
    afterEach(() => vi.unstubAllGlobals());

    it('sletter kun efter bekræftelse', async () => {
      const calls: string[] = [];
      vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
        calls.push(`${init?.method ?? 'GET'} ${url}`);
        return init?.method === 'DELETE' ? new Response(null, { status: 204 }) : new Response(JSON.stringify(usage()), { status: 200 });
      }));
      expect(await deleteDrawingFlow('d', () => false)).toBe(false);
      expect(calls).toEqual(['GET /api/drawings/d/usage']);
      expect(await deleteDrawingFlow('d', () => true)).toBe(true);
      expect(calls.at(-1)).toBe('DELETE /api/drawings/d');
    });

    it('fejl fra serveren sendes videre med serverens tekst', async () => {
      vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ error: 'Tegningen findes ikke' }), { status: 404 })));
      await expect(deleteDrawingFlow('d', () => true)).rejects.toThrow('Tegningen findes ikke');
    });
  });
});
