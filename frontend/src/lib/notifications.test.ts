import { describe, expect, it } from 'vitest';
import { buildBody, formFrom, parseRecipients, type NotifyConfig } from './notifications';

const cfg: NotifyConfig = {
  enabled: true, min_priority: 'high', on_clear: true, batch_s: 20,
  webhook: { enabled: true, has_url: true, host: 'hooks.example.test', has_token: true },
  email: { enabled: false, host: 'smtp.laces.dk', port: 587, security: 'starttls', username: 'jan', sender: 's@laces.dk', recipients: ['a@b.dk', 'c@d.dk'], has_password: true, provider: 'smtp', has_resend_key: false },
};

describe('notifications', () => {
  it('modtagere: komma, semikolon, mellemrum og linjeskift', () => {
    expect(parseRecipients('a@b.dk, c@d.dk;e@f.dk\ng@h.dk')).toEqual(['a@b.dk', 'c@d.dk', 'e@f.dk', 'g@h.dk']);
    expect(parseRecipients('  \n ')).toEqual([]);
  });
  it('formularen viser aldrig hemmeligheder: adresse, token og adgangskode står tomme', () => {
    const f = formFrom(cfg);
    expect([f.wh_url, f.wh_token, f.em_password]).toEqual(['', '', '']);
    expect(f.em_recipients).toBe('a@b.dk\nc@d.dk');
  });
  it('uændrede hemmeligheder sendes ikke med', () => {
    const body = buildBody(formFrom(cfg)) as any;
    expect(body.webhook).toEqual({ enabled: true });
    expect('password' in body.email).toBe(false);
    expect(body.email.recipients).toEqual(['a@b.dk', 'c@d.dk']);
    expect(body.email.port).toBe(587);
  });
  it('udfyldte hemmeligheder og fjern-valg sendes', () => {
    const f = formFrom(cfg);
    f.wh_url = '  https://x.dk/hook  '; f.wh_token = 'tokentoken123'; f.em_password = 'pw'; f.clear_token = true;
    const body = buildBody(f) as any;
    expect(body.webhook).toEqual({ enabled: true, url: 'https://x.dk/hook', token: 'tokentoken123', clear_token: true });
    expect(body.email.password).toBe('pw');
  });
  it('0 og false er gyldige værdier (batch, til/fra)', () => {
    const f = formFrom({ ...cfg, enabled: false, on_clear: false });
    const body = buildBody(f) as any;
    expect(body.enabled).toBe(false);
    expect(body.on_clear).toBe(false);
  });
  it('Resend: nøglen står tom, udbyderen sendes, og nøglen sendes kun når den er udfyldt', () => {
    const f = formFrom({ ...cfg, email: { ...cfg.email, provider: 'resend', has_resend_key: true } });
    expect(f.em_provider).toBe('resend');
    expect(f.em_resend_key).toBe('');
    let body = buildBody(f) as any;
    expect(body.email.provider).toBe('resend');
    expect('resend_key' in body.email).toBe(false);
    f.em_resend_key = '  re_abcdefghijklmnop1234  ';
    body = buildBody(f) as any;
    expect(body.email.resend_key).toBe('re_abcdefghijklmnop1234');
    f.clear_resend_key = true;
    expect((buildBody(f) as any).email.clear_resend_key).toBe(true);
  });
});
