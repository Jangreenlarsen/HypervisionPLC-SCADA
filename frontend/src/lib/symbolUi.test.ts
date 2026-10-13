import { describe, expect, it } from 'vitest';
import { clickAction, needsPin, operateLabel, pickAction, type SymbolView } from './symbolUi';

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
