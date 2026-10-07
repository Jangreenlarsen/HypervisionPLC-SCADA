import { describe, expect, it } from 'vitest';
import { applyBinding, colorFor, formatValue, fraction } from './animate';
import type { Binding, LiveValue } from './api';

const SVGNS = 'http://www.w3.org/2000/svg';
const meta = { unit: '°C', decimals: 1, description: '', plc: 'plc1' };
const good = (value: unknown): LiveValue => ({ value, quality: 'good', ts: 0, error: null });

function el(tag: string, attrs: Record<string, string> = {}): Element {
  const e = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
}

describe('formatValue', () => {
  it('bruger tag-decimaler og enhed', () => expect(formatValue(21.456, meta)).toBe('21.5 °C'));
  it('binding-decimaler vinder, også 0', () => expect(formatValue(21.6, meta, { decimals: 0 })).toBe('22 °C'));
  it('bool-tekster', () => {
    expect(formatValue(true, meta)).toBe('Til');
    expect(formatValue(false, meta, { false_text: 'Stop' })).toBe('Stop');
  });
  it('null/undefined giver tankestreg', () => {
    expect(formatValue(null, meta)).toBe('—');
    expect(formatValue(undefined, meta)).toBe('—');
  });
  it('heltal uden decimaler', () => expect(formatValue(7, { ...meta, decimals: null, unit: '' })).toBe('7'));
  it('skjul enhed', () => expect(formatValue(3, meta, { show_unit: false })).toBe('3.0'));
});

describe('colorFor', () => {
  it('bool on/off med standard', () => {
    expect(colorFor(true, {})).toBe('#2e7d32');
    expect(colorFor(false, {})).toBe('#9e9e9e');
  });
  it('tærskler, inkl. værdi 0', () => {
    const p = { off: 'grey', thresholds: [{ value: 0, color: 'blue' }, { value: 50, color: 'red' }] };
    expect(colorFor(-1, p)).toBe('grey');
    expect(colorFor(0, p)).toBe('blue');
    expect(colorFor(50, p)).toBe('red');
  });
});

describe('fraction', () => {
  it('klamper til 0..1', () => {
    expect(fraction(150, 0, 100)).toBe(1);
    expect(fraction(-5, 0, 100)).toBe(0);
    expect(fraction(25, 0, 50)).toBe(0.5);
  });
  it('ikke-tal giver 0', () => expect(fraction('x', 0, 10)).toBe(0));
});

describe('applyBinding', () => {
  const b = (anim: Binding['anim'], params: Record<string, any> = {}): Binding => ({ element: 'x', tag: 'T', anim, params });

  it('text skriver i første tspan og markerer kvalitet', () => {
    const t = el('text');
    const span = el('tspan');
    span.textContent = 'gammel';
    t.appendChild(span);
    applyBinding(t, b('text'), good(20), meta);
    expect(span.textContent).toBe('20.0 °C');
    expect(t.getAttribute('data-hv-quality')).toBe('good');
  });

  it('manglende værdi viser tankestreg og quality unknown', () => {
    const t = el('text');
    applyBinding(t, b('text'), undefined, meta);
    expect(t.textContent).toBe('—');
    expect(t.getAttribute('data-hv-quality')).toBe('unknown');
  });

  it('comm_error beholder sidste værdi men markeres', () => {
    const t = el('text');
    applyBinding(t, b('text'), { value: 5, quality: 'comm_error', ts: 0, error: 'PLC svarer ikke' }, meta);
    expect(t.textContent).toBe('5.0 °C');
    expect(t.getAttribute('data-hv-quality')).toBe('comm_error');
  });

  it('fill på gruppe farver alle figurer', () => {
    const g = el('g');
    const r = el('rect');
    const c = el('circle');
    g.append(r, c);
    applyBinding(g, b('fill', { on: 'green', off: 'grey' }), good(true));
    expect((r as SVGElement).style.fill).toBe('green');
    expect((c as SVGElement).style.fill).toBe('green');
  });

  it('level opad på rect bevarer originalmål', () => {
    const r = el('rect', { x: '10', y: '0', width: '20', height: '100' });
    const lb = b('level', { min: 0, max: 100, direction: 'up' });
    applyBinding(r, lb, good(25));
    expect(r.getAttribute('height')).toBe('25');
    expect(r.getAttribute('y')).toBe('75');
    applyBinding(r, lb, good(100));
    expect(r.getAttribute('height')).toBe('100');
    expect(r.getAttribute('y')).toBe('0');
  });

  it('level på andet end rect giver advarsel i stedet for at fejle', () => {
    const c = el('circle');
    applyBinding(c, b('level'), good(50));
    expect(c.getAttribute('data-hv-warning')).toContain('rect');
  });

  it('visible med invert', () => {
    const r = el('rect');
    const vb = b('visible', { invert: true });
    applyBinding(r, vb, good(true));
    expect((r as SVGElement).style.display).toBe('none');
    applyBinding(r, vb, good(false));
    expect((r as SVGElement).style.display).toBe('');
  });

  it('blink skifter klasse', () => {
    const r = el('rect');
    applyBinding(r, b('blink'), good(1));
    expect(r.classList.contains('hv-blink')).toBe(true);
    applyBinding(r, b('blink'), good(0));
    expect(r.classList.contains('hv-blink')).toBe(false);
  });

  it('rotate lægger rotation oven på original transform', () => {
    const r = el('rect', { transform: 'translate(5 5)' });
    applyBinding(r, b('rotate', { min: 0, max: 100, angle_min: 0, angle_max: 180 }), good(50));
    expect(r.getAttribute('transform')).toMatch(/^translate\(5 5\) rotate\(90 /);
  });
});
