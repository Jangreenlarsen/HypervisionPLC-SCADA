import { describe, expect, it } from 'vitest';
import {
  createBody, dateFromExpiry, emptyForm, examples, expiryFromDate, formFrom, generateKey, keyStatus, parseList, patchBody, scopeBody, scopeText,
  type ApiKey,
} from './integration';

const key: ApiKey = {
  id: 'k_1', name: 'Node-RED', prefix: 'hv_abcdefgh', scope: { all: false, tags: ['a', 'b'], prefixes: ['kedel_'] }, ip_allow: ['10.0.0.0/8'],
  expires_at: null, disabled: false, created_at: 1, created_by: 'admin', last_used_at: null, last_ip: '', expired: false,
  stats: { requests: 0, errors: 0, rate_limited: 0 },
};

describe('integration', () => {
  it('nøglen er hv_ + 43 URL-sikre tegn og er forskellig hver gang', () => {
    const a = generateKey();
    expect(a).toMatch(/^hv_[A-Za-z0-9_-]{43}$/);
    expect(a).not.toBe(generateKey());
    expect(generateKey((x) => x.fill(0xfb))).toMatch(/^hv_[A-Za-z0-9_-]{43}$/);
  });
  it('lister kan adskilles med komma, semikolon, mellemrum og linjeskift', () => {
    expect(parseList('a, b;c\nd  e')).toEqual(['a', 'b', 'c', 'd', 'e']);
    expect(parseList(' ')).toEqual([]);
  });
  it('udløbsdato: slutningen af dagen, tom = aldrig, ugyldig afvises', () => {
    const ts = expiryFromDate('2030-06-15')!;
    const d = new Date(ts * 1000);
    expect([d.getFullYear(), d.getMonth(), d.getDate(), d.getHours(), d.getMinutes()]).toEqual([2030, 5, 15, 23, 59]);
    expect(dateFromExpiry(ts)).toBe('2030-06-15');
    expect(expiryFromDate('')).toBeNull();
    expect(dateFromExpiry(null)).toBe('');
    expect(() => expiryFromDate('15-06-2030')).toThrow('ÅÅÅÅ-MM-DD');
  });
  it('afgrænsning: alle, eller valgte tags/præfikser', () => {
    expect(scopeBody({ ...emptyForm(), scopeMode: 'all', tags: 'ignoreres' })).toEqual({ all: true, tags: [], prefixes: [] });
    expect(scopeBody({ ...emptyForm(), tags: 'a\nb', prefixes: 'kedel_' })).toEqual({ all: false, tags: ['a', 'b'], prefixes: ['kedel_'] });
  });
  it('opret- og ændre-krop; nøglen sendes kun ved oprettelse', () => {
    const f = { ...emptyForm(), name: '  Min nøgle ', tags: 't1', ips: '10.0.0.0/8, 192.168.1.5', expires: '2030-01-01' };
    const body = createBody(f, 'hv_x') as any;
    expect(body.key).toBe('hv_x');
    expect(body.name).toBe('Min nøgle');
    expect(body.ip_allow).toEqual(['10.0.0.0/8', '192.168.1.5']);
    expect(typeof body.expires_at).toBe('number');
    expect('key' in (patchBody(f, key) as object)).toBe(false);
  });
  it('ændre-krop indeholder kun ændrede felter (en udløbet nøgle kan omdøbes)', () => {
    const expired = { ...key, expired: true, expires_at: 1000 };
    const f = formFrom(expired);
    expect(patchBody(f, expired)).toEqual({});
    f.name = 'Nyt navn';
    expect(patchBody(f, expired)).toEqual({ name: 'Nyt navn' });
    f.scopeMode = 'all';
    f.ips = '';
    expect(patchBody(f, expired)).toEqual({ name: 'Nyt navn', scope: { all: true, tags: [], prefixes: [] }, ip_allow: [] });
    f.expires = '';
    expect((patchBody(f, expired) as any).expires_at).toBeNull();
  });
  it('formularen fra en eksisterende nøgle', () => {
    const f = formFrom(key);
    expect(f).toMatchObject({ name: 'Node-RED', scopeMode: 'selected', tags: 'a\nb', prefixes: 'kedel_', ips: '10.0.0.0/8', expires: '' });
    expect(formFrom({ ...key, scope: { all: true, tags: [], prefixes: [] } }).scopeMode).toBe('all');
  });
  it('tekster og status', () => {
    expect(scopeText({ all: true, tags: [], prefixes: [] })).toBe('alle tags');
    expect(scopeText(key.scope)).toBe('2 tags + præfiks kedel_');
    expect(scopeText({ all: false, tags: ['a'], prefixes: [] })).toBe('1 tag');
    expect([keyStatus(key), keyStatus({ ...key, disabled: true }), keyStatus({ ...key, expired: true }), keyStatus({ ...key, disabled: true, expired: true })])
      .toEqual(['aktiv', 'deaktiveret', 'udløbet', 'deaktiveret']);
  });
  it('eksemplerne indeholder nøglen og adressen og bruger Bearer-header', () => {
    const e = examples('https://scada.laces.dk', 'hv_NØGLE');
    for (const text of Object.values(e)) {
      expect(text).toContain('hv_NØGLE');
      expect(text).toContain('https://scada.laces.dk/api/v1/integration/');
    }
    expect(e.curl).toContain('Authorization: Bearer hv_NØGLE');
    expect(e.homeassistant).toContain('value_template');
  });
});
