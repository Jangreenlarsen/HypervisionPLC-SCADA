import { describe, expect, it } from 'vitest';
import { clickFor, parseSetpoint, rangeText, toggleQuestion } from './actions';
import type { Binding } from './api';
import { emptyForm, fromForm, toForm } from './bindingForm';

const meta = { unit: '°C', decimals: 1, description: 'Setpunkt', plc: 'plc1', min: 0, max: 80 };

describe('parseSetpoint', () => {
  it('accepterer grænserne selv, også 0', () => {
    expect(parseSetpoint('0', meta)).toBe(0);
    expect(parseSetpoint('80', meta)).toBe(80);
    expect(parseSetpoint('21,5', meta)).toBe(21.5);
  });
  it('afviser uden for grænser med enhed i teksten', () => {
    expect(() => parseSetpoint('-0.1', meta)).toThrow('mindst 0 °C');
    expect(() => parseSetpoint('81', meta)).toThrow('højst være 80 °C');
  });
  it('ingen grænser når min/max er null', () => {
    expect(parseSetpoint('-1000', { ...meta, min: null, max: null })).toBe(-1000);
  });
  it('tom tekst giver fejl', () => expect(() => parseSetpoint(' ', meta)).toThrow('udfyldes'));
});

describe('rangeText', () => {
  it('formaterer grænser', () => {
    expect(rangeText(meta)).toBe('0 – 80 °C');
    expect(rangeText({ ...meta, max: null })).toBe('mindst 0 °C');
    expect(rangeText({ ...meta, min: null, max: null })).toBe('ingen grænser');
  });
});

describe('clickFor', () => {
  it('finder klik-bindingen for et element', () => {
    const bs: Binding[] = [
      { element: 'P', tag: 'Motor', anim: 'fill', params: {} },
      { element: 'P', tag: 'Motor', anim: 'click:toggle', params: { confirm: true } },
    ];
    expect(clickFor(bs, 'P')?.anim).toBe('click:toggle');
    expect(clickFor(bs, 'X')).toBeNull();
  });
});

describe('toggleQuestion', () => {
  it('viser fra/til i klartekst', () => {
    const q = toggleQuestion('Motor', { value: false, quality: 'good', ts: 0, error: null }, { ...meta, unit: '', description: 'Motor 1' });
    expect(q).toBe('Skift "Motor 1" fra Fra til Til?');
  });
});

describe('klik-bindinger i formularen', () => {
  it('goto kræver tegning og har intet tag', () => {
    expect(() => fromForm(emptyForm('', 'click:goto'))).toThrow('Vælg den tegning');
    expect(fromForm({ ...emptyForm('', 'click:goto'), drawing: 'pumpestation' })).toEqual(
      { tag: '', anim: 'click:goto', params: { drawing: 'pumpestation' } });
  });
  it('puls validerer længde', () => {
    expect(fromForm({ ...emptyForm('M', 'click:pulse'), ms: '250' }).params).toEqual({ ms: 250, confirm: false });
    expect(() => fromForm({ ...emptyForm('M', 'click:pulse'), ms: '50' })).toThrow('100-10000');
  });
  it('toggle bekræftelse er standard og bevares rundt', () => {
    expect(emptyForm('M', 'click:toggle').confirm).toBe(true);
    const b = { tag: 'M', anim: 'click:toggle' as const, params: { confirm: false } };
    expect(fromForm(toForm(b))).toEqual(b);
  });
});
