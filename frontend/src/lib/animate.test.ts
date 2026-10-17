import { describe, expect, it } from 'vitest';
import { activeFor, applyBinding, armFlowsOut, armName, colorFor, flowState, formatValue, fraction, junctionArms, lengthScale, segmentsOf, textFor, withDirection } from './animate';
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

describe('løbelys er uafhængigt af rørets skalering', () => {
  it('lengthScale: forstørrelse langs en retning — strækning på tværs og drejning påvirker ikke længden', () => {
    expect(lengthScale({ a: 3, b: 0, c: 0, d: 1 }, 1, 0)).toBeCloseTo(3);      // strakt 3× i x, målt langs x
    expect(lengthScale({ a: 3, b: 0, c: 0, d: 1 }, 0, 1)).toBeCloseTo(1);      // … men langs y er den uændret
    expect(lengthScale({ a: 1, b: 0, c: 0, d: 3 }, 1, 0)).toBeCloseTo(1);      // strakt på tværs af et vandret rør: ingen ændring
    expect(lengthScale({ a: 0, b: 3, c: -1, d: 0 }, 1, 0)).toBeCloseTo(3);     // drejet 90° og strakt 3× langs røret
    expect(lengthScale({ a: 2, b: 0, c: 0, d: 2 }, 5, 5)).toBeCloseTo(2);      // ensartet skalering
    expect(lengthScale({ a: 4, b: 0, c: 0, d: 1 }, 0, 0)).toBeCloseTo(2);      // ingen retning: geometrisk middel
  });

  // jsdom har ikke getCTM: vi leverer en matrix for den streg der tegnes (den samlede transform i tegningen)
  const withMatrix = (m: { a: number; b: number; c: number; d: number } | null, fn: () => void) => {
    const proto = (globalThis as any).SVGElement.prototype;
    const had = Object.getOwnPropertyDescriptor(proto, 'getCTM');
    const identity = { a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 };
    // linjen (lyset) har rørets samlede matrix; proben (en tom <g> under roden) har tegningens egen visning (identitet)
    proto.getCTM = function getCTM(this: Element) { return this.tagName === 'line' && m ? { ...identity, ...m } : this.tagName === 'line' ? null : identity; };
    try {
      fn();
    } finally {
      if (had) Object.defineProperty(proto, 'getCTM', had);
      else delete proto.getCTM;
    }
  };
  const dashOf = (rect: Element, svg: Element) => {
    applyBinding(rect, { element: 'r', tag: 'P', anim: 'flow', params: { dash: 12, speed: 40 } }, good(true));
    return svg.querySelector('.hv-flow line')!.getAttribute('stroke-dasharray');
  };
  const pipe = (w: string, h: string) => {
    const rect = el('rect', { x: '0', y: '0', width: w, height: h });
    const svg = el('svg');
    svg.appendChild(rect);
    return { rect, svg };
  };

  it('et rør strakt 3 gange i længden får samme lysstykke i tegningen (lokal længde 12/3)', () => {
    const { rect, svg } = pipe('90', '10');
    withMatrix({ a: 3, b: 0, c: 0, d: 1 }, () => expect(dashOf(rect, svg)).toBe('4 4'));
  });

  it('gælder også lodrette rør, drejede rør og symboler skaleret via en gruppe', () => {
    let { rect, svg } = pipe('10', '90');
    withMatrix({ a: 1, b: 0, c: 0, d: 2 }, () => expect(dashOf(rect, svg)).toBe('6 6'));
    ({ rect, svg } = pipe('90', '10'));
    withMatrix({ a: 0, b: 3, c: -1, d: 0 }, () => expect(dashOf(rect, svg)).toBe('4 4'));
  });

  it('tegningens egen visning (viewBox/zoom) tæller ikke med: den skalerer rør og lys ens', () => {
    const { rect, svg } = pipe('90', '10');
    const proto = (globalThis as any).SVGElement.prototype;
    const had = Object.getOwnPropertyDescriptor(proto, 'getCTM');
    // roden vises i halv størrelse (viewBox): både proben og linjen har 0,5 — rørets egen skalering er stadig 3
    proto.getCTM = function getCTM(this: Element) { return this.tagName === 'line' ? { a: 1.5, b: 0, c: 0, d: 0.5, e: 0, f: 0 } : { a: 0.5, b: 0, c: 0, d: 0.5, e: 0, f: 0 }; };
    try {
      expect(dashOf(rect, svg)).toBe('4 4');
    } finally {
      if (had) Object.defineProperty(proto, 'getCTM', had);
      else delete proto.getCTM;
    }
  });

  it('skalering på tværs af røret og uskaleret rør ændrer ikke lyset', () => {
    let { rect, svg } = pipe('90', '10');
    withMatrix({ a: 1, b: 0, c: 0, d: 3 }, () => expect(dashOf(rect, svg)).toBe('12 12'));
    ({ rect, svg } = pipe('90', '10'));
    withMatrix(null, () => expect(dashOf(rect, svg)).toBe('12 12'));     // intet at måle på: som før
  });
});

describe('løbelys i T-stykke og kryds', () => {
  const pipeG = (d: string) => { const g = el('g'); g.appendChild(el('path', { d, fill: 'none', stroke: '#555', 'stroke-width': '10' })); return g; };
  const flowB = (params: Record<string, unknown> = {}): Binding => ({ element: 'r', tag: 'P', anim: 'flow', params });
  const dirs = (g: Element) => Object.fromEntries([...g.querySelectorAll('.hv-flow line')].map((l) =>
    [armName(Number(l.getAttribute('x2')) - 45, Number(l.getAttribute('y2')) - 45), l.getAttribute('data-hv-dir')]));
  const mount = (g: Element) => { el('svg').appendChild(g); return g; };

  it('finder krydspunktet og rørene: 4 i et kryds, 3 i et T-stykke', () => {
    const k = junctionArms(segmentsOf(el('path', { d: 'M0 45 H90 M45 0 V90' }))!)!;
    expect([k.cx, k.cy, k.arms.length]).toEqual([45, 45, 4]);
    const t = junctionArms(segmentsOf(el('path', { d: 'M0 45 H90 M45 45 V0' }))!)!;
    expect([t.cx, t.cy, t.arms.length]).toEqual([45, 45, 3]);
    expect(t.arms.map(([x, y]) => armName(x - 45, y - 45)).sort()).toEqual(['left', 'right', 'up']);
  });
  it('relative path-kommandoer og linjer i en gruppe virker også; buer giver null', () => {
    expect(segmentsOf(el('path', { d: 'm0 45 h90 m-45 -45 v90' }))).toEqual([[0, 45, 90, 45], [45, 0, 45, 90]]);
    expect(segmentsOf(el('path', { d: 'M0 45 H25 A20 20 0 0 0 45 25 V0' }))).toBeNull();
    expect(junctionArms([[0, 45, 90, 45], [10, 0, 80, 0]])).toBeNull(); // parallelle rør er ikke et kryds
  });
  it('rørets retning følger skærmen: et symbol roteret 90° har "op" der hvor det tegnede "højre" er', () => {
    expect(armName(45, 0)).toBe('right');
    expect(armName(45, 0, { a: 0, b: -1, c: 1, d: 0 })).toBe('up'); // rotate(-90)
    expect(armName(45, 0, { a: -1, b: 0, c: 0, d: 1 })).toBe('left'); // spejlet vandret
  });
  it('valgt rør ind → de øvrige ud; ud → de øvrige ind; "tilbage" vender det hele', () => {
    expect([armFlowsOut(true, 'in', 1), armFlowsOut(false, 'in', 1)]).toEqual([false, true]);
    expect([armFlowsOut(true, 'out', 1), armFlowsOut(false, 'out', 1)]).toEqual([true, false]);
    expect([armFlowsOut(true, 'in', -1), armFlowsOut(false, 'in', -1)]).toEqual([true, false]);
  });
  it('kryds: venstre rør ind → højre, op og ned løber ud', () => {
    const g = mount(pipeG('M0 45 H90 M45 0 V90'));
    applyBinding(g, flowB({ arm: 'left', arm_flow: 'in' }), good(true));
    expect(dirs(g)).toEqual({ left: 'in', right: 'out', up: 'out', down: 'out' });
  });
  it('T-stykke: afgreningen op løber ud → venstre og højre løber ind; kode 2 (tilbage) vender', () => {
    const g = mount(pipeG('M0 45 H90 M45 45 V0'));
    applyBinding(g, flowB({ arm: 'up', arm_flow: 'out', mode: 'code' }), good(1));
    expect(dirs(g)).toEqual({ left: 'in', right: 'in', up: 'out' });
    applyBinding(g, flowB({ arm: 'up', arm_flow: 'out', mode: 'code' }), good(2));
    expect(dirs(g)).toEqual({ left: 'out', right: 'out', up: 'in' });
    expect(g.querySelectorAll('.hv-flow').length).toBe(1);
  });
  it('valgt rør der ikke findes (ned i et T-stykke): advarsel, og lyset følger tegneretningen', () => {
    const g = mount(pipeG('M0 45 H90 M45 45 V0'));
    applyBinding(g, flowB({ arm: 'down' }), good(true));
    expect(g.getAttribute('data-hv-warning')).toContain('findes ikke');
    expect(g.querySelector('.hv-flow path')).not.toBeNull(); // kopi af stregen i stedet for rør-linjer
  });
});

describe('løbelys med eget retnings-tag', () => {
  const live = (value: unknown): LiveValue => ({ value, quality: 'good', ts: 0, error: null });
  it('Fra = som valgt, Til = modsat; uden retnings-tag uændret', () => {
    expect(withDirection(1, { dir_tag: 'Retning' }, live(false))).toBe(1);
    expect(withDirection(1, { dir_tag: 'Retning' }, live(true))).toBe(-1);
    expect(withDirection(-1, { dir_tag: 'Retning' }, live(1))).toBe(1); // også sammen med kode/fortegn
    expect(withDirection(1, {}, live(true))).toBe(1);
  });
  it('ukendt retning stopper; stop forbliver stop', () => {
    expect(withDirection(1, { dir_tag: 'Retning' }, undefined)).toBe(0);
    expect(withDirection(1, { dir_tag: 'Retning' }, live(null))).toBe(0);
    expect(withDirection(0, { dir_tag: 'Retning' }, live(true))).toBe(0);
  });
  it('i DOM: start/stop-tag til og retnings-tag til → lyset løber baglæns', () => {
    const rect = el('rect', { width: '90', height: '10' });
    const svg = el('svg'); svg.appendChild(rect);
    const b: Binding = { element: 'r', tag: 'Pumpe', anim: 'flow', params: { dir_tag: 'Retning' } };
    applyBinding(rect, b, live(true), undefined, live(true));
    expect(svg.querySelector('.hv-flow line')!.getAttribute('data-hv-dir')).toBe('in');
    applyBinding(rect, b, live(true), undefined, live(false));
    expect(svg.querySelector('.hv-flow line')!.getAttribute('data-hv-dir')).toBe('out');
    applyBinding(rect, b, live(true), undefined, undefined);
    expect(svg.querySelector('.hv-flow')).toBeNull();
  });
});

describe('symbol-animationer (kilde = position, gælder i positionerne, blinkfrekvens, roterer, glidning)', () => {
  const live = (value: unknown): LiveValue => ({ value, quality: 'good', ts: 0, error: null });
  const sym = (anim: Binding['anim'], params: Record<string, unknown>): Binding =>
    ({ element: 'p', tag: 'sym:d:V1:pos', anim, params: { pos: true, ...params }, source: 'symbol' });

  it('farve pr. position; ukendt position = delens egen farve', () => {
    const r = el('rect');
    const b = sym('fill', { colors: ['#111111', '#222222', '#333333'] });
    applyBinding(r, b, live(2));
    expect((r as SVGElement).style.fill).toBe('rgb(51, 51, 51)');
    applyBinding(r, b, live(null));
    expect((r as SVGElement).style.fill).toBe('');
  });
  it('værdi viser positionens navn', () => {
    const t = el('text');
    t.textContent = '0';
    applyBinding(t, sym('text', { labels: ['Hand', '0', 'Auto'] }), live(2));
    expect(t.textContent).toBe('Auto');
  });
  it('gælder i positionerne: udenfor vises delen som tegnet; ukendt position slår ikke fra', () => {
    const r = el('rect');
    const b: Binding = { element: 'p', tag: 'Lys', anim: 'fill', params: { on: '#00ff00', off: '#cccccc', only: [false, true], pos_tag: 'sym:d:V1:pos' } };
    applyBinding(r, b, live(true), undefined, undefined, live(1));
    expect((r as SVGElement).style.fill).toBe('rgb(0, 255, 0)');
    applyBinding(r, b, live(true), undefined, undefined, live(0));
    expect((r as SVGElement).style.fill).toBe('');
    applyBinding(r, b, live(true), undefined, undefined, live(null));
    expect((r as SVGElement).style.fill).toBe('rgb(0, 255, 0)');
  });
  it('blinkfrekvens som klasse; fasen sættes kun når blinket starter', () => {
    const r = el('rect');
    const b: Binding = { element: 'p', tag: 'Alarm', anim: 'blink', params: { speed: 'fast' } };
    applyBinding(r, b, live(true));
    expect([...r.classList]).toEqual(['hv-blink', 'hv-blink-fast']);
    const delay = (r as SVGElement).style.animationDelay;
    expect(delay).toMatch(/^-\d+ms$/);
    (r as SVGElement).style.animationDelay = '-1ms';
    applyBinding(r, b, live(true));
    expect((r as SVGElement).style.animationDelay).toBe('-1ms');   // ikke flyttet ved en ny opdatering
    applyBinding(r, b, live(false));
    expect(r.classList.contains('hv-blink')).toBe(false);
  });
  it('roterer, "når ≥ X" og pr. position', () => {
    expect(activeFor(55, { at_least: 50 })).toBe(true);
    expect(activeFor(49.9, { at_least: 50 })).toBe(false);
    expect(activeFor(2, { pos: true, set: [false, false, true] })).toBe(true);
    const r = el('g');
    applyBinding(r, { element: 'p', tag: 'Drift', anim: 'spin', params: {} }, live(true));
    expect(r.classList.contains('hv-spin')).toBe(true);
  });
  it('blafrer (v0.69.0): farves og blafrer ved drift; slukket = som tegnet; pr. position og "når ≥"', () => {
    const f = el('path');
    const b = { element: 'f', tag: 'Brænder', anim: 'flicker' as const, params: { color: '#ff8c1a' } };
    applyBinding(f, b, live(true));
    expect(f.classList.contains('hv-flicker')).toBe(true);
    expect((f as SVGElement).style.fill).toBe('rgb(255, 140, 26)');
    applyBinding(f, b, live(false));
    expect(f.classList.contains('hv-flicker')).toBe(false);
    expect((f as SVGElement).style.fill).toBe('');
    applyBinding(f, { ...b, params: { at_least: 50 } }, live(60));
    expect((f as SVGElement).style.fill).toBe('rgb(255, 140, 26)');   // standardfarven
    applyBinding(f, { ...b, params: { pos: true, set: [false, true], color: '#ff0000' } }, live(0));
    expect(f.classList.contains('hv-flicker')).toBe(false);
  });
  it('Drej/Flyt pr. position glider som CSS-transform; del med egen transform beholder attributten', () => {
    const r = el('rect');
    applyBinding(r, sym('rotate', { angles: [-45, 0, 45] }), live(2));
    expect((r as SVGElement).style.transform).toBe('rotate(45deg)');
    expect(r.classList.contains('hv-glide')).toBe(true);
    applyBinding(r, sym('move', { dxs: [0, 32], dys: [0, 0] }), live(1));
    expect((r as SVGElement).style.transform).toBe('translate(32px, 0px) rotate(45deg)');
    const t = el('rect', { transform: 'translate(5 5)' });
    applyBinding(t, sym('move', { dxs: [0, 32], dys: [0, 0] }), live(1));
    expect(t.getAttribute('transform')).toBe('translate(5 5) translate(32 0)');
    expect((t as SVGElement).style.transform).toBe('');
  });
  it('løbelys pr. position', () => {
    const rect = el('rect', { width: '90', height: '10' });
    const svg = el('svg'); svg.appendChild(rect);
    applyBinding(rect, sym('flow', { dirs: [0, 1, -1] }), live(2));
    expect(svg.querySelector('.hv-flow line')!.getAttribute('data-hv-dir')).toBe('in');
    applyBinding(rect, sym('flow', { dirs: [0, 1, -1] }), live(0));
    expect(svg.querySelector('.hv-flow')).toBeNull();
  });
});
