import { describe, expect, it } from 'vitest';
import { SOURCE_LABEL, sourceKind } from './tagSource';

describe('sourceKind', () => {
  it('intern, RS485-slave og expansion board', () => {
    expect(sourceKind('plc1:hr:60:real')).toBe('intern');
    expect(sourceKind('plc1:logic:1:x')).toBe('intern');
    expect(sourceKind('plc1:rtu:90:hr:0')).toBe('rtu');
    expect(sourceKind('plc1:MBX:1:D:1:coil:0')).toBe('mbx');
    expect(SOURCE_LABEL[sourceKind('plc1:mbx:1:D:1:coil:0')]).toBe('Expansion board');
  });
});
