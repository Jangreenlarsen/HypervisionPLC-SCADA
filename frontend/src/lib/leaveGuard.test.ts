import { afterEach, describe, expect, it, vi } from 'vitest';
import { mayLeave, setLeaveGuard } from './leaveGuard';

let off: (() => void) | null = null;
afterEach(() => { off?.(); off = null; });

describe('leaveGuard', () => {
  it('uden vagt må man gå', async () => {
    expect(await mayLeave()).toBe(true);
  });
  it('vagten afgør (sync og async)', async () => {
    off = setLeaveGuard(() => false);
    expect(await mayLeave()).toBe(false);
    off();
    off = setLeaveGuard(async () => true);
    expect(await mayLeave()).toBe(true);
  });
  it('en fjernet vagt spørges ikke mere, og en gammel vagt fjerner ikke den nye', async () => {
    const first = setLeaveGuard(() => false);
    off = setLeaveGuard(() => false);
    first();                        // første er ikke længere aktiv → må ikke fjerne den nye
    expect(await mayLeave()).toBe(false);
    off();
    expect(await mayLeave()).toBe(true);
  });
  it('en vagt der kaster, blokerer ikke', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    off = setLeaveGuard(() => { throw new Error('x'); });
    expect(await mayLeave()).toBe(true);
  });
});
