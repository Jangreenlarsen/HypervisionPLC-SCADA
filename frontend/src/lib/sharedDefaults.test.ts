// v6.9.2 (analysen 2026-11-13): frontendens kopier af standarderne skal være ens med backendens (shared/flow_defaults.json).
// Fejler testen: ret kopien, der nævnes — eller kør backend/.venv/Scripts/python.exe -m app.services.flow_defs --write-shared,
// hvis backendens standarder er ændret med vilje.
import { describe, expect, it } from 'vitest';
import shared from '../../../shared/flow_defaults.json';
import { FLOW_DEFAULTS, PIECE_TYPES } from './symbolFlow';
import graphSrc from './signalpath/graph.ts?raw';
import coreSrc from '../../svgedit-host/scada-core.js?raw';

/** Uden tomme felter og med hele tal som tal — så kun indholdet sammenlignes. */
function norm(x: unknown): unknown {
  if (Array.isArray(x)) return x.map(norm);
  if (x && typeof x === 'object') {
    return Object.fromEntries(Object.entries(x).filter(([, v]) => v !== null && v !== undefined && !(Array.isArray(v) && !v.length))
      .map(([k, v]) => [k, norm(v)]).sort(([a], [b]) => String(a).localeCompare(String(b))));
  }
  return x;
}
const listIn = (src: string, name: string): string[] => {
  const m = src.match(new RegExp(name + String.raw` = new Set\(\[([^\]]*)\]`));
  return m ? [...m[1].matchAll(/'([^']+)'/g)].map((x) => x[1]).sort() : [];
};

describe('frontendens kopier af standarderne (shared/flow_defaults.json)', () => {
  it('symbolFlow.FLOW_DEFAULTS', () => expect(norm(FLOW_DEFAULTS)).toEqual(norm(shared.flow_defaults)));
  it('symbolFlow.PIECE_TYPES', () => expect([...PIECE_TYPES].sort()).toEqual(shared.pipe_types));
  it('signalpath/graph.ts PIPE_TYPES', () => expect(listIn(graphSrc, 'PIPE_TYPES')).toEqual(shared.pipe_types));
  it('scada-core.js PIPE_SYMBOL_TYPES', () => expect(listIn(coreSrc, 'PIPE_SYMBOL_TYPES')).toEqual(shared.pipe_types));
});
