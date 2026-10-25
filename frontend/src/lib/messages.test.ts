import { describe, expect, it } from 'vitest';
import { headline, oneLine, sortMessages, type Msg } from './messages';

const m = (id: string, kind: Msg['kind']): Msg => ({ id, kind, text: id });

describe('meddelelser på Overview', () => {
  it('sorterer alvorligste først og bevarer rækkefølgen inden for samme alvor', () => {
    const sorted = sortMessages([m('i', 'info'), m('w1', 'warn'), m('e1', 'error'), m('ok', 'ok'), m('w2', 'warn'), m('e2', 'error')]);
    expect(sorted.map((x) => x.id)).toEqual(['e1', 'e2', 'w1', 'w2', 'ok', 'i']);
  });
  it('overskriften er den alvorligste, med antal af de øvrige', () => {
    expect(headline([])).toBeNull();
    expect(headline([m('w', 'warn'), m('e', 'error'), m('i', 'info')])).toMatchObject({ first: { id: 'e' }, more: 2 });
    expect(headline([m('i', 'info')])).toMatchObject({ first: { id: 'i' }, more: 0 });
  });
  it('gør teksten til én linje', () => {
    expect(oneLine('Bindinger  til\n elementer\t der …')).toBe('Bindinger til elementer der …');
  });
});
