// System › Backup › Tidsplan og destinationer (v3.23.0). Adgangskoder/tokens sendes kun, når de er udfyldt (skriv-kun): et tomt felt
// betyder "behold den gemte".

export type Method = 'sftp' | 'scp' | 'ftp' | 'ftps' | 'https' | 'smb' | 'nfs';
export interface Schedule {
  mode: 'off' | 'interval' | 'daily' | 'weekly'; every_h: number; time: string; days: number[];
  next_run?: number | null; last_run?: number | null; running?: boolean; expected_interval_h?: number;
}
export interface TargetResult { at: number; ok: boolean; error: string; files: string[]; bytes: number; duration_s: number; pruned?: number }
export interface Target {
  id: string; name: string; method: Method; enabled: boolean; host: string; port: number | null; path: string; username: string;
  url: string; share: string; export: string; auth: 'password' | 'key'; verify_tls: boolean; send_config: boolean; send_trends: boolean;
  keep: number; http_auth: 'none' | 'basic' | 'bearer'; host_key: string | null; has_password: boolean; public_key: string | null;
  last: TargetResult | null; fails: number; uploads: { ok: number; error: number }; mount: { ok: boolean; error: string } | null;
}
export type TargetForm = Omit<Target, 'id' | 'host_key' | 'has_password' | 'public_key' | 'last' | 'fails' | 'uploads' | 'mount' | 'port'> & {
  port: string; password: string;
};

export const METHODS: { id: Method; label: string; hint: string }[] = [
  { id: 'sftp', label: 'SFTP', hint: 'SSH-filoverførsel (Linux-server, NAS, Raspberry Pi). Anbefalet.' },
  { id: 'scp', label: 'SCP', hint: 'SSH-kopiering til servere uden SFTP.' },
  { id: 'ftps', label: 'FTPS', hint: 'FTP med kryptering (TLS).' },
  { id: 'ftp', label: 'FTP', hint: 'Ukrypteret — adgangskode og filer kan aflyttes på netværket.' },
  { id: 'https', label: 'HTTPS', hint: 'PUT til en adresse (WebDAV, Nextcloud, egen modtager). Kan ikke rydde op.' },
  { id: 'smb', label: 'SMB', hint: 'Windows-share eller NAS (\\\\server\\share).' },
  { id: 'nfs', label: 'NFS', hint: 'NFS-share på NAS/Linux; monteres af Pi\'en selv (kræver nfs-common).' },
];
export const DEFAULT_PORTS: Partial<Record<Method, number>> = { sftp: 22, scp: 22, ftp: 21, ftps: 21, smb: 445 };
export const DAYS = ['man', 'tir', 'ons', 'tor', 'fre', 'lør', 'søn'];

export const emptyTarget = (): TargetForm => ({
  name: '', method: 'sftp', enabled: true, host: '', port: '', path: '', username: '', url: '', share: '', export: '', auth: 'password',
  verify_tls: true, send_config: true, send_trends: true, keep: 7, http_auth: 'none', password: '',
});

export function formFromTarget(t: Target): TargetForm {
  const { id: _i, host_key: _h, has_password: _p, public_key: _k, last: _l, fails: _f, uploads: _u, mount: _m, port, ...rest } = t;
  return { ...rest, port: port === null || port === DEFAULT_PORTS[t.method] ? '' : String(port), password: '' };
}

/** Felter der hører til metoden (resten sendes ikke). Tom port → standardporten. Tom adgangskode → behold den gemte. */
export function targetBody(f: TargetForm): Record<string, unknown> {
  const b: Record<string, unknown> = {
    name: f.name.trim(), method: f.method, enabled: f.enabled, path: f.path.trim(), send_config: f.send_config, send_trends: f.send_trends,
    keep: f.method === 'https' ? 0 : Number(f.keep),
  };
  if (['sftp', 'scp', 'ftp', 'ftps', 'smb'].includes(f.method)) {
    b.host = f.host.trim();
    b.username = f.username.trim();
    if (f.port.trim()) {
      const p = Number(f.port);
      if (!Number.isInteger(p) || p < 1 || p > 65535) throw new Error('Porten skal være et heltal 1-65535');
      b.port = p;
    } else b.port = null;
  }
  if (f.method === 'sftp' || f.method === 'scp') b.auth = f.auth;
  if (f.method === 'ftps' || f.method === 'https') b.verify_tls = f.verify_tls;
  if (f.method === 'https') { b.url = f.url.trim(); b.http_auth = f.http_auth; if (f.http_auth === 'basic') b.username = f.username.trim(); }
  if (f.method === 'smb') b.share = f.share.trim();
  if (f.method === 'nfs') b.export = f.export.trim();
  if (f.password) b.password = f.password;
  return b;
}

export const needsPassword = (f: TargetForm): boolean =>
  f.method === 'https' ? f.http_auth !== 'none' : f.method !== 'nfs' && !((f.method === 'sftp' || f.method === 'scp') && f.auth === 'key');

/** "Hver 24. time" / "Dagligt kl. 02:30" / "man, fre kl. 01:00" / "Slået fra". */
export function scheduleText(s: Schedule): string {
  if (s.mode === 'off') return 'Slået fra';
  if (s.mode === 'interval') return s.every_h === 1 ? 'Hver time' : `Hver ${s.every_h}. time`;
  if (s.mode === 'daily') return `Dagligt kl. ${s.time}`;
  return `${s.days.map((d) => DAYS[d]).join(', ')} kl. ${s.time}`;
}

/** Adressen som én læsbar linje (til tabellen). */
export function targetWhere(t: Pick<Target, 'method' | 'host' | 'port' | 'path' | 'url' | 'share' | 'export' | 'username'>): string {
  const p = t.path ? `/${t.path.replace(/^\/+/, '')}` : '';
  switch (t.method) {
    case 'https': return t.url;
    case 'nfs': return t.export + p;
    case 'smb': return `\\\\${t.host}\\${t.share}${p.replace(/\//g, '\\')}`;
    default: return `${t.method}://${t.username ? t.username + '@' : ''}${t.host}${t.port && t.port !== DEFAULT_PORTS[t.method] ? ':' + t.port : ''}${p}`;
  }
}

export function fmtBytes(n: number): string {
  if (n >= 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1).replace('.', ',')} MB`;
  return `${Math.max(1, Math.round(n / 1024))} KB`;
}
