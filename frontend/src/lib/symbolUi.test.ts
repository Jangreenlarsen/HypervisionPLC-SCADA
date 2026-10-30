import { describe, expect, it } from 'vitest';
import { clickAction, clickSide, isOperable, needsPin, operateLabel, pickAction, stepTarget, type SymbolView } from './symbolUi';

const sym = (over: Partial<SymbolView> = {}): SymbolView => ({
  op: 'positions', labels: ['Stop', 'Start'], display: 'remote', confirm: true, lock_positions: [false, false],
  lock_leave: false, has_pin: false, fault: '', ...over,
});

describe('klik på et symbol (prototypens clickSymbol)', () => {
  it('2 positioner uden bekræftelse: skift straks til den anden', () => {
    expect(clickAction(sym({ confirm: false }), 0)).toEqual({ kind: 'operate', to: 1 });
    expect(clickAction(sym({ confirm: false }), 1)).toEqual({ kind: 'operate', to: 0 });
    expect(clickAction(sym({ confirm: false }), null)).toEqual({ kind: 'operate', to: 1 });
  });
  it('låst mål kræver koden — også uden bekræftelse', () => {
    expect(clickAction(sym({ confirm: false, lock_positions: [false, true] }), 0)).toEqual({ kind: 'dialog', pick: 1 });
  });
  it('med bekræftelse eller flere positioner: dialog', () => {
    expect(clickAction(sym(), 0)).toEqual({ kind: 'dialog', pick: null });
    expect(clickAction(sym({ confirm: false, labels: ['H', '0', 'A'], lock_positions: [false, false, false] }), 0))
      .toEqual({ kind: 'dialog', pick: null });
  });
  it('trykknap, setpunkt og visning', () => {
    expect(clickAction(sym({ op: 'pulse', confirm: false }), null)).toEqual({ kind: 'pulse' });
    expect(clickAction(sym({ op: 'pulse', confirm: true }), null)).toEqual({ kind: 'dialog', pick: null });
    expect(clickAction(sym({ op: 'entry' }), null)).toEqual({ kind: 'dialog', pick: null });
    expect(clickAction(sym({ op: 'view' }), null)).toEqual({ kind: 'none' });
  });
});

describe('nøglelås', () => {
  const s = sym({ labels: ['Hand', '0', 'Auto'], lock_positions: [true, false, false] });
  it('låst mål', () => {
    expect(needsPin(s, 1, 0)).toBe(true);
    expect(needsPin(s, 1, 2)).toBe(false);
  });
  it('"kode for at forlade" kun når den viste position er låst', () => {
    expect(needsPin({ ...s, lock_leave: true }, 0, 2)).toBe(true);
    expect(needsPin({ ...s, lock_leave: false }, 0, 2)).toBe(false);
    expect(needsPin({ ...s, lock_leave: true }, 1, 2)).toBe(false);
  });
  it('knaptekst og klik i dialogen uden bekræftelse', () => {
    expect(operateLabel(s, 1, 0)).toBe('Lås op og skift til Hand');
    expect(operateLabel(s, 1, 2)).toBe('Skift til Auto');
    expect(pickAction({ ...s, confirm: false }, 1, 2)).toBe('operate');
    expect(pickAction({ ...s, confirm: false }, 1, 0)).toBe('pick');
    expect(pickAction(s, 1, 2)).toBe('pick');
  });
});

describe('venstre/højre-betjening (v1.11.0)', () => {
  const sw = { op: 'positions', labels: ['0', '1', '2', '3', '4'], display: 'remote', confirm: false, lock_positions: [], lock_leave: false,
    has_pin: false, fault: '', click: 'step' } as SymbolView;
  it('venstre = forrige, højre = næste', () => {
    expect(stepTarget(sw, 2, -1)).toEqual({ kind: 'to', to: 1 });
    expect(stepTarget(sw, 2, 1)).toEqual({ kind: 'to', to: 3 });
  });
  it('stopper i enderne i stedet for at gå rundt', () => {
    expect(stepTarget(sw, 0, -1)).toEqual({ kind: 'limit', end: 'first' });
    expect(stepTarget(sw, 4, 1)).toEqual({ kind: 'limit', end: 'last' });
    expect(stepTarget(sw, 4, -1)).toEqual({ kind: 'to', to: 3 });
  });
  it('ukendt eller ugyldig position giver dialogen', () => {
    expect(stepTarget(sw, null, 1)).toEqual({ kind: 'dialog' });
    expect(stepTarget(sw, 9, 1)).toEqual({ kind: 'dialog' });
    expect(stepTarget(sw, -1, 1)).toEqual({ kind: 'dialog' });
  });
  it('klik på venstre eller højre halvdel af symbolet', () => {
    const rect = { left: 100, width: 80 };
    expect(clickSide(120, rect)).toBe(-1);
    expect(clickSide(139, rect)).toBe(-1);
    expect(clickSide(140, rect)).toBe(1);   // præcis midt = højre
    expect(clickSide(179, rect)).toBe(1);
  });
  it('bekræftelse eller kode åbner stadig dialogen med den valgte position', () => {
    expect(pickAction(sw, 2, 3)).toBe('operate');
    expect(pickAction({ ...sw, confirm: true }, 2, 3)).toBe('pick');
    expect(pickAction({ ...sw, lock_positions: [false, false, false, true, false], has_pin: true }, 2, 3)).toBe('pick');
  });
});

describe('kun passiv visning (v2.8.0)', () => {
  it('et passivt symbol kan ikke betjenes: intet klik, og det er ikke betjenbart', () => {
    const p = sym({ passive: true });
    expect(clickAction(p, 0)).toEqual({ kind: 'none' });
    expect(isOperable(p)).toBe(false);
    expect(isOperable(sym({ op: 'view' }))).toBe(false);
    expect(isOperable(sym())).toBe(true);
    expect(isOperable(sym({ op: 'pulse' }))).toBe(true);
  });
});
