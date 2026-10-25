import { describe, expect, it } from 'vitest';
import { pruneAcked, splitProblems } from './plcAck';

const plcs = { a: { state: 'error', message: 'tabt' }, b: { state: 'ok' }, c: { state: 'error' } };

describe('kvittering af PLC-fejl', () => {
  it('deler fejl i ukvitterede og kvitterede', () => {
    const r = splitProblems(plcs, new Set(['a', 'b']));
    expect(r.open.map(([k]) => k)).toEqual(['c']);
    expect(r.acked.map(([k]) => k)).toEqual(['a']);   // b er ikke i fejl, så en gammel kvittering for den tæller ikke
  });
  it('uden kvitteringer vises alle fejl', () => {
    expect(splitProblems(plcs, new Set()).open.map(([k]) => k)).toEqual(['a', 'c']);
  });
  it('en kvittering bortfalder, når PLC\'en er i orden igen — så vises en ny fejl igen', () => {
    expect([...pruneAcked(new Set(['a', 'b', 'x']), plcs)]).toEqual(['a']);
    const recovered = { ...plcs, a: { state: 'ok' } };
    expect(pruneAcked(new Set(['a']), recovered).size).toBe(0);
    expect(splitProblems({ ...recovered, a: { state: 'error' } }, pruneAcked(new Set(['a']), recovered)).open.map(([k]) => k)).toContain('a');
  });
});
