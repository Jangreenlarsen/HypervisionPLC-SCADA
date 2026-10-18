import { get } from 'svelte/store';
import { describe, expect, it } from 'vitest';
import { ask, askQueue, askText } from './ask';

const first = () => get(askQueue)[0];

describe('spørgsmål på siden (i stedet for confirm/prompt)', () => {
  it('ja/nej: OK → true, Annullér → false; køen tømmes', async () => {
    const p = ask('Slet?', { ok: 'Slet', danger: true });
    expect(first()).toMatchObject({ text: 'Slet?', ok: 'Slet', cancel: 'Annullér', danger: true, input: null });
    first().resolve('');
    expect(await p).toBe(true);
    expect(get(askQueue)).toEqual([]);
    const q = ask('Igen?');
    first().resolve(null);
    expect(await q).toBe(false);
  });

  it('flere spørgsmål på én gang vises i rækkefølge', async () => {
    const a = ask('A'), b = ask('B');
    expect(get(askQueue).map((r) => r.text)).toEqual(['A', 'B']);
    first().resolve('');
    expect(first().text).toBe('B');
    first().resolve(null);
    expect([await a, await b]).toEqual([true, false]);
  });

  it('tekst: trimmes; tom, mellemrum eller Annullér giver null', async () => {
    for (const [given, want] of [['  hemmelig-kode-1 ', 'hemmelig-kode-1'], ['', null], ['   ', null], [null, null]] as const) {
      const p = askText('Ny kode', { placeholder: 'mindst 10 tegn' });
      expect(first().input).toEqual({ value: '', placeholder: 'mindst 10 tegn' });
      first().resolve(given);
      expect(await p).toBe(want);
    }
  });

  it('tekst med allowEmpty: tom og mellemrum giver "", kun Annullér giver null', async () => {
    for (const [given, want] of [['  Fremløb ', 'Fremløb'], ['', ''], ['   ', ''], [null, null]] as const) {
      const p = askText('Navn', { allowEmpty: true });
      first().resolve(given);
      expect(await p).toBe(want);
    }
  });
});
