import { describe, expect, it } from 'vitest';
import { applyBinding, colorFor, flowState, formatValue, fraction, textFor } from './animate';
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

describe('textFor', () => {
  const liter = { ...meta, unit: '', decimals: 0 };
  it('tekst før/efter værdien, mellemrum bevares', () =>
    expect(textFor(1002, liter, { prefix: 'Tank : ', suffix: ' liter' })).toBe('Tank : 1002 liter'));
  it('også rundt om — når værdien mangler', () =>
    expect(textFor(null, liter, { prefix: 'Tank : ', suffix: ' liter' })).toBe('Tank : — liter'));
  it('uden for/efter-tekst = som før', () => expect(textFor(21.456, meta)).toBe('21.5 °C'));
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

  it('text med tekst før/efter, også uden værdi', () => {
    const t = el('text');
    const p = { prefix: 'Tank : ', suffix: ' liter', show_unit: false, decimals: 0 };
    applyBinding(t, b('text', p), good(1002), meta);
    expect(t.textContent).toBe('Tank : 1002 liter');
    applyBinding(t, b('text', p), undefined, meta);
    expect(t.textContent).toBe('Tank : — liter');
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

  it('move forskyder efter værdien — 0 ved min, dx/dy ved max, begrænset til området', () => {
    const r = el('rect');
    const p = { min: 0, max: 100, dx: 200, dy: -40 };
    applyBinding(r, b('move', p), good(25));
    expect(r.getAttribute('transform')).toBe('translate(50 -10)');
    applyBinding(r, b('move', p), good(150));
    expect(r.getAttribute('transform')).toBe('translate(200 -40)');
    applyBinding(r, b('move', p), good(0));
    expect(r.getAttribute('transform')).toBe('translate(0 0)');
  });

  it('move og rotate på samme element overskriver ikke hinanden; original transform bevares', () => {
    const r = el('rect', { transform: 'scale(2)' });
    applyBinding(r, b('move', { min: 0, max: 10, dx: 10, dy: 0 }), good(10));
    applyBinding(r, b('rotate', { min: 0, max: 10, angle_min: 0, angle_max: 90 }), good(10));
    expect(r.getAttribute('transform')).toMatch(/^scale\(2\) translate\(10 0\) rotate\(90 /);
    applyBinding(r, b('move', { min: 0, max: 10, dx: 10, dy: 0 }), good(5));
    expect(r.getAttribute('transform')).toMatch(/^scale\(2\) translate\(5 0\) rotate\(90 /);
  });
});

describe('løbelys (flow)', () => {
  it('til/fra: kører ved til, står ved fra; omvendt og vendt retning', () => {
    expect(flowState(true)).toBe(1);
    expect(flowState(0)).toBe(0);
    expect(flowState(false, { invert: true })).toBe(1);
    expect(flowState(1, { reverse: true })).toBe(-1);
    expect(flowState(null)).toBe(0);
  });
  it('fortegn: over 0 frem, under 0 tilbage, 0 stop — reverse vender', () => {
    expect(flowState(12.5, { mode: 'signed' })).toBe(1);
    expect(flowState(-3, { mode: 'signed' })).toBe(-1);
    expect(flowState(0, { mode: 'signed' })).toBe(0);
    expect(flowState(-3, { mode: 'signed', reverse: true })).toBe(1);
    expect(flowState(0, { mode: 'signed', reverse: true })).toBe(0); // ikke -0
  });
  it('kode: 0 stop, 1 frem, 2 tilbage, alt andet stop', () => {
    expect(flowState(1, { mode: 'code' })).toBe(1);
    expect(flowState(2, { mode: 'code' })).toBe(-1);
    for (const v of [0, 3, -1, 1.5, null]) expect(flowState(v, { mode: 'code' }), String(v)).toBe(0);
  });

  const flowB = (params: Record<string, unknown> = {}): Binding => ({ element: 'r', tag: 'Pumpe', anim: 'flow', params });
  const svgWith = (child: Element) => { const svg = el('svg'); svg.appendChild(child); return svg; };

  it('et lige rør (rect) får en stiplet streg ad midterlinjen i farve 2 og selv farve 1', () => {
    const rect = el('rect', { x: '0', y: '0', width: '90', height: '10', fill: '#555' });
    const svg = svgWith(rect);
    applyBinding(rect, flowB({ base: '#123456', light: '#abcdef', dash: 8 }), good(true));
    const layer = svg.querySelector('.hv-flow')!;
    expect(layer).not.toBeNull();
    const line = layer.querySelector('line')!;
    expect([line.getAttribute('y1'), line.getAttribute('y2'), line.getAttribute('x2')]).toEqual(['5', '5', '90']);
    expect(line.getAttribute('stroke-width')).toBe('10');
    expect(line.getAttribute('stroke')).toBe('#abcdef');
    expect(line.getAttribute('stroke-dasharray')).toBe('8 8');
    expect((rect as SVGElement).style.fill).toBe('rgb(18, 52, 86)');
  });
  it('en gruppe med en stiplet kopi af hver streg; stop fjerner lyset og giver røret sin farve igen', () => {
    const g = el('g', { id: 'boejning' });
    const path = el('path', { id: 'p', d: 'M0 45 H25 A20 20 0 0 0 45 25 V0', fill: 'none', stroke: '#555', 'stroke-width': '10' });
    g.appendChild(path);
    svgWith(g);
    applyBinding(g, flowB(), good(1));
    const copy = g.querySelector('.hv-flow path')!;
    expect(copy.getAttribute('d')).toBe(path.getAttribute('d'));
    expect(copy.hasAttribute('id')).toBe(false); // ingen dublet-id'er i tegningen
    expect(copy.getAttribute('fill')).toBe('none');
    applyBinding(g, flowB(), good(0));
    expect(g.querySelector('.hv-flow')).toBeNull();
    expect((path as SVGElement).style.stroke).toBe('');
  });
  it('samme tilstand igen genskaber ikke lyset (animationen hopper ikke ved hver opdatering)', () => {
    const rect = el('rect', { width: '90', height: '10' });
    const svg = svgWith(rect);
    applyBinding(rect, flowB(), good(true));
    const first = svg.querySelector('.hv-flow');
    applyBinding(rect, flowB(), good(true));
    expect(svg.querySelector('.hv-flow')).toBe(first);
    applyBinding(rect, flowB({ mode: 'onoff', reverse: true }), good(true)); // ny retning → nyt lag
    expect(svg.querySelectorAll('.hv-flow').length).toBe(1);
    expect(svg.querySelector('.hv-flow')).not.toBe(first);
  });
  it('ukendt værdi (kommunikationsfejl) stopper lyset', () => {
    const rect = el('rect', { width: '90', height: '10' });
    const svg = svgWith(rect);
    applyBinding(rect, flowB(), good(true));
    applyBinding(rect, flowB(), { value: null, quality: 'bad', ts: 0, error: 'timeout' });
    expect(svg.querySelector('.hv-flow')).toBeNull();
  });
  it('element uden streg giver en advarsel i stedet for et tomt lag', () => {
    const c = el('circle', { r: '5', fill: '#555' });
    const svg = svgWith(c);
    applyBinding(c, flowB(), good(true));
    expect(svg.querySelector('.hv-flow')).toBeNull();
    expect(c.getAttribute('data-hv-warning')).toContain('løbelys');
  });
});
