import { describe, expect, it } from 'vitest';
import { emptyTarget, fmtBytes, formFromTarget, needsPassword, scheduleText, targetBody, targetWhere, type Target } from './backupTargets';

describe('backupTargets', () => {
  it('kroppen indeholder kun metodens felter; tom adgangskode og port sendes ikke som værdi', () => {
    const b = targetBody({ ...emptyTarget(), name: ' NAS ', host: 'nas.local', username: 'u', path: 'scada' });
    expect(b).toMatchObject({ name: 'NAS', method: 'sftp', host: 'nas.local', port: null, auth: 'password', keep: 7 });
    expect('password' in b).toBe(false);
    expect('url' in b).toBe(false);
    expect(targetBody({ ...emptyTarget(), method: 'https', url: 'https://x', keep: 5, password: 't' })).toMatchObject({ keep: 0, password: 't', url: 'https://x' });
    expect(targetBody({ ...emptyTarget(), method: 'nfs', export: 'nas:/b' })).not.toHaveProperty('host');
    expect(() => targetBody({ ...emptyTarget(), port: '99999' })).toThrow('Porten');
  });
  it('adgangskode kræves ikke for SSH-nøgle, NFS og HTTPS uden login', () => {
    expect(needsPassword(emptyTarget())).toBe(true);
    expect(needsPassword({ ...emptyTarget(), auth: 'key' })).toBe(false);
    expect(needsPassword({ ...emptyTarget(), method: 'nfs' })).toBe(false);
    expect(needsPassword({ ...emptyTarget(), method: 'https' })).toBe(false);
  });
  it('formularen fra en destination skjuler standardporten og har altid tom adgangskode', () => {
    const t = { ...emptyTarget(), id: 'a', port: 22, host_key: null, has_password: true, public_key: null, last: null, fails: 0,
      uploads: { ok: 0, error: 0 }, mount: null } as unknown as Target;
    expect(formFromTarget(t)).toMatchObject({ port: '', password: '' });
    expect(formFromTarget({ ...t, port: 2222 }).port).toBe('2222');
  });
  it('tekster', () => {
    expect(scheduleText({ mode: 'off', every_h: 24, time: '02:30', days: [] })).toBe('Slået fra');
    expect(scheduleText({ mode: 'interval', every_h: 6, time: '', days: [] })).toBe('Hver 6. time');
    expect(scheduleText({ mode: 'daily', every_h: 24, time: '02:30', days: [] })).toBe('Dagligt kl. 02:30');
    expect(scheduleText({ mode: 'weekly', every_h: 24, time: '01:00', days: [0, 4] })).toBe('man, fre kl. 01:00');
    const base = { host: 'nas', port: 22, path: 'a/b', url: '', share: 'backup', export: 'nas:/v', username: 'u' };
    expect(targetWhere({ ...base, method: 'sftp' })).toBe('sftp://u@nas/a/b');
    expect(targetWhere({ ...base, method: 'sftp', port: 2222 })).toBe('sftp://u@nas:2222/a/b');
    expect(targetWhere({ ...base, method: 'smb', port: 445 })).toBe('\\\\nas\\backup\\a\\b');
    expect(targetWhere({ ...base, method: 'nfs' })).toBe('nas:/v/a/b');
    expect(fmtBytes(2 * 1024 * 1024)).toBe('2,0 MB');
  });
});
