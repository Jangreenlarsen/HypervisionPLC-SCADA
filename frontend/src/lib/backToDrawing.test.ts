import { describe, expect, it } from 'vitest';
import { backTarget } from './backToDrawing';

describe('tilbage til tegningen (v0.76.0)', () => {
  const list = [{ id: 'varme', name: 'Varme' }, { id: 'a b', name: 'Hal 2' }];
  it('den sidst viste tegning med navn; ellers Overview', () => {
    expect(backTarget('varme', list)).toEqual({ href: '#overview/varme', label: 'Tilbage til "Varme"' });
    expect(backTarget('a b', list).href).toBe('#overview/a%20b');
    expect(backTarget('slettet', list)).toEqual({ href: '#overview', label: 'Tilbage til tegningen' });
    expect(backTarget(null, list).href).toBe('#overview');
    expect(backTarget('varme', null).href).toBe('#overview');
  });
});
