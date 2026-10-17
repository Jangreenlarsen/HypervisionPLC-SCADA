import { describe, expect, it } from 'vitest';
import versionFile from '../../../version.json';
import { BUNDLE, isStale } from './staleCheck';

describe('forældet side efter opdatering', () => {
  it('versionen er bygget ind fra version.json', () => {
    expect(BUNDLE).toEqual({ version: versionFile.version, build: versionFile.build });
  });
  it('sammenligner version og build; ukendt eller tom serverversion er ikke forældet', () => {
    const b = { version: '0.63.0', build: '0091' };
    expect(isStale(b, { version: '0.63.0', build: '0091' })).toBe(false);
    expect(isStale(b, { version: '0.63.1', build: '0092' })).toBe(true);
    expect(isStale(b, { version: '0.63.0', build: '0092' })).toBe(true);
    expect(isStale(b, null)).toBe(false);
    expect(isStale(b, { version: '', build: '0092' })).toBe(false);
    expect(isStale(b, { version: '  ', build: '  ' })).toBe(false);
  });
});
