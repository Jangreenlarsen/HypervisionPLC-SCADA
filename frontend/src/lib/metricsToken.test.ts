import { describe, expect, it } from 'vitest';
import { generateToken, scrapeConfig } from './metricsToken';

describe('metricsToken', () => {
  it('genererer 43 URL-sikre tegn, og to tokens er forskellige', () => {
    const a = generateToken();
    const b = generateToken();
    expect(a).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(a).not.toBe(b);
  });
  it('bruger den givne tilfældighedskilde (bytes 0xFB 0xFF → URL-sikre tegn, ingen +, / eller =)', () => {
    const t = generateToken((a) => a.fill(0xfb));
    expect(t).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(t).toBe(generateToken((a) => a.fill(0xfb)));
  });
  it('scrape-konfigurationen indeholder vært og token', () => {
    const c = scrapeConfig('10.1.1.31', 'TOKEN123');
    expect(c).toContain("targets: ['10.1.1.31']");
    expect(c).toContain('credentials: TOKEN123');
    expect(c).toContain('scheme: https');
  });
});
