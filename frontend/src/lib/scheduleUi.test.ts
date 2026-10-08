import { describe, expect, it } from 'vitest';
import { fmtValue, parseValue, toForm, toPayload, valueColor } from './scheduleUi';

const form = {
  name: ' Komfort ', tag: 'Setpunkt', enabled: true, default_value: '17',
  entries: [{ days: [3, 1, 2], start: '06:00', end: '22:00', value: '21,5' }],
  exceptions: [{ date_from: '2026-12-24', date_to: '', value: '', note: ' Jul ' }],
};

describe('toPayload', () => {
  it('tal med decimalkomma, sorterede dage, tom undtagelsesværdi = standard, tom til-dato = samme dag', () => {
    expect(toPayload(form, false)).toEqual({
      name: 'Komfort', tag: 'Setpunkt', enabled: true, default_value: 17,
      entries: [{ days: [1, 2, 3], start: '06:00', end: '22:00', value: 21.5 }],
      exceptions: [{ date_from: '2026-12-24', date_to: '2026-12-24', value: null, note: 'Jul' }],
    });
  });
  it('til/fra-tag giver true/false; tom standard = ingen', () => {
    const p = toPayload({ ...form, default_value: '', entries: [{ ...form.entries[0], value: '1' }] }, true);
    expect(p.default_value).toBeNull();
    expect((p.entries as { value: unknown }[])[0].value).toBe(true);
  });
  it('fejl nævner hvor', () => {
    expect(() => toPayload({ ...form, entries: [{ ...form.entries[0], value: '' }] }, false)).toThrow('Periode 1: angiv en værdi');
    expect(() => toPayload({ ...form, default_value: 'abc' }, false)).toThrow('Standardværdi');
  });
});

describe('toForm', () => {
  it('rundtur', () => {
    const f = toForm({ name: 'Komfort', tag: 'Setpunkt', enabled: false, default_value: null,
      entries: [{ days: [1], start: '06:00', end: '22:00', value: 21.5 }], exceptions: [] }, false);
    expect(f.default_value).toBe('');
    expect(f.entries[0].value).toBe('21,5');
  });
});

describe('visning', () => {
  it('fmtValue', () => {
    expect(fmtValue(1, true)).toBe('Til');
    expect(fmtValue(21.5, false, '°C')).toBe('21,5 °C');
    expect(fmtValue(null, false)).toBe('ingen');
  });
  it('valueColor: lav værdi lys, høj mørk; parseValue', () => {
    expect(valueColor(17, false, [17, 21])).toBe('#cfe1f5');
    expect(valueColor(21, false, [17, 21])).toBe('#1f5f99');
    expect(valueColor(null, false, [17])).toBe('transparent');
    expect(parseValue(' ')).toBeNull();
  });
});
