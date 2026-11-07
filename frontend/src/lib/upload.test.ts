import { describe, expect, it } from 'vitest';
import { formatBytes } from './upload';

describe('formatBytes', () => {
  it('GB med dansk komma, MB/kB afrundet', () => {
    expect(formatBytes(2740937888)).toBe('2,7 GB');
    expect(formatBytes(23047838)).toBe('23 MB');
    expect(formatBytes(1500)).toBe('2 kB');
    expect(formatBytes(12)).toBe('12 B');
  });
});
