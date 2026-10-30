// Tilslutningspunkter på symboler — de rene dele (svgedit-host/symbolPorts.js).
import { describe, expect, it } from 'vitest';
// @ts-expect-error — ren JS uden typer
import { formatPorts, parsePorts, portAxis, symbolType } from '../../svgedit-host/symbolPorts.js';

describe('parsePorts / formatPorts', () => {
  it('frem og tilbage', () => {
    expect(parsePorts(formatPorts([[0, 0.5], [1, 0.123456]]))).toEqual([[0, 0.5], [1, 0.1235]]);
  });
  it('ugyldige punkter springes over; intet gyldigt giver null', () => {
    expect(parsePorts('0,0.5;x,1;2,0;1,1')).toEqual([[0, 0.5], [1, 1]]);
    expect(parsePorts('')).toBeNull();
    expect(parsePorts('a;b')).toBeNull();
    expect(parsePorts(null)).toBeNull();
  });
});

describe('portAxis', () => {
  it('sidekant vandret, top/bund lodret, ellers nærmeste kant', () => {
    expect(portAxis([0, 0.5])).toBe('h');
    expect(portAxis([1, 0.3])).toBe('h');
    expect(portAxis([0.5, 0])).toBe('v');
    expect(portAxis([0.4, 1])).toBe('v');
    expect(portAxis([0.45, 0.1])).toBe('v');
  });
});

describe('symbolType', () => {
  it('som data-hv-type ved indsættelse', () => {
    expect(symbolType('boejning90')).toBe('boejning90');
    expect(symbolType('Ventil-3vejs')).toBe('ventil_3vejs');
    expect(symbolType('x'.repeat(50))).toHaveLength(40);
  });
});
