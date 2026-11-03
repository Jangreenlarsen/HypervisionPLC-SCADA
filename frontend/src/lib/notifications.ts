// System › Notifikationer (v3.19.0): typer og hjælpefunktioner til formularen. Adresse, token og adgangskode er skriv-kun: serveren
// siger kun *om* de er sat, så felterne står tomme, og kun udfyldte felter sendes ved Gem.
export type Priority = 'high' | 'medium' | 'low';
export type Security = 'starttls' | 'ssl' | 'none';
export type Provider = 'smtp' | 'resend';

export interface NotifyConfig {
  enabled: boolean; min_priority: Priority; on_clear: boolean; batch_s: number;
  webhook: { enabled: boolean; has_url: boolean; host: string; has_token: boolean };
  email: { enabled: boolean; provider: Provider; has_resend_key: boolean; host: string; port: number; security: Security; username: string; sender: string; recipients: string[]; has_password: boolean };
}
export interface Delivery { ts: number; channel: 'webhook' | 'email'; ok: boolean; attempts: number; alarms: number; error: string; test: boolean }
export interface NotifyState {
  config: NotifyConfig; deliveries: Delivery[]; queued: number; sent: Record<string, number>; failed: Record<string, number>;
  dropped: number; failing: Record<string, string>;
}
export interface TestResults { results: Record<string, { ok: boolean; attempts: number; error: string }> }

export interface Form {
  enabled: boolean; min_priority: Priority; on_clear: boolean; batch_s: number;
  wh_enabled: boolean; wh_url: string; wh_token: string; clear_url: boolean; clear_token: boolean;
  em_enabled: boolean; em_provider: Provider; em_resend_key: string; clear_resend_key: boolean; em_host: string; em_port: number; em_security: Security; em_username: string; em_sender: string;
  em_recipients: string; em_password: string; clear_password: boolean;
}

export const PRIORITY_TEXT: Record<Priority, string> = { high: 'Kun høj prioritet', medium: 'Medium og højere', low: 'Alle alarmer' };
export const SECURITY_TEXT: Record<Security, string> = { starttls: 'STARTTLS (port 587)', ssl: 'SSL/TLS (port 465)', none: 'Ingen (kun lokalt netværk)' };

/** "a@b.dk, c@d.dk; e@f.dk" eller én pr. linje → liste (tomme udelades). */
export function parseRecipients(text: string): string[] {
  return text.split(/[\s,;]+/).map((s) => s.trim()).filter(Boolean);
}

export function formFrom(c: NotifyConfig): Form {
  return {
    enabled: c.enabled, min_priority: c.min_priority, on_clear: c.on_clear, batch_s: c.batch_s,
    wh_enabled: c.webhook.enabled, wh_url: '', wh_token: '', clear_url: false, clear_token: false,
    em_enabled: c.email.enabled, em_provider: c.email.provider, em_resend_key: '', clear_resend_key: false, em_host: c.email.host, em_port: c.email.port, em_security: c.email.security,
    em_username: c.email.username, em_sender: c.email.sender, em_recipients: c.email.recipients.join('\n'),
    em_password: '', clear_password: false,
  };
}

/** PUT-kroppen: alle almindelige felter; hemmeligheder kun når de er udfyldt (eller eksplicit fjernes). */
export function buildBody(f: Form): Record<string, unknown> {
  const webhook: Record<string, unknown> = { enabled: f.wh_enabled };
  if (f.wh_url.trim()) webhook.url = f.wh_url.trim();
  if (f.wh_token.trim()) webhook.token = f.wh_token.trim();
  if (f.clear_url) webhook.clear_url = true;
  if (f.clear_token) webhook.clear_token = true;
  const email: Record<string, unknown> = {
    enabled: f.em_enabled, provider: f.em_provider, host: f.em_host.trim(), port: Number(f.em_port), security: f.em_security,
    username: f.em_username.trim(), sender: f.em_sender.trim(), recipients: parseRecipients(f.em_recipients),
  };
  if (f.em_password) email.password = f.em_password;
  if (f.clear_password) email.clear_password = true;
  if (f.em_resend_key.trim()) email.resend_key = f.em_resend_key.trim();
  if (f.clear_resend_key) email.clear_resend_key = true;
  return { enabled: f.enabled, min_priority: f.min_priority, on_clear: f.on_clear, batch_s: Number(f.batch_s), webhook, email };
}

export const PROVIDER_TEXT: Record<Provider, string> = { smtp: 'SMTP-server', resend: 'Resend (API)' };
export const CHANNEL_TEXT: Record<string, string> = { webhook: 'Webhook', email: 'E-mail' };
