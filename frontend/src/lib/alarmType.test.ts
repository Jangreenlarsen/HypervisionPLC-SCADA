import { describe, expect, it } from 'vitest';
import { alarmPriorityText, alarmTypeText } from './alarmType';

describe('alarmtype og prioritet som tekst (B1)', () => {
  it('niveauer på dansk', () => {
    expect(['HH', 'H', 'L', 'LL'].map(alarmTypeText)).toEqual(['HH', 'H', 'L', 'LL']);
    expect(alarmTypeText('ON')).toBe('Til');
    expect(alarmTypeText('COMM')).toBe('Kommunikation');
    expect(alarmTypeText('SYS')).toBe('System');
    expect(alarmTypeText('AFV')).toBe('Afvigelse');
  });

  it('ukendt vises rå, tomt som tankestreg', () => {
    expect(alarmTypeText('XYZ')).toBe('XYZ');
    expect(alarmTypeText('')).toBe('—');
    expect(alarmTypeText(undefined)).toBe('—');
  });

  it('prioritet', () => {
    expect(['high', 'medium', 'low'].map(alarmPriorityText)).toEqual(['Høj', 'Medium', 'Lav']);
    expect(alarmPriorityText('ukendt')).toBe('ukendt');
    expect(alarmPriorityText(null)).toBe('—');
  });
});
