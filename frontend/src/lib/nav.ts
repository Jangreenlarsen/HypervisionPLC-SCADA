// Hovedmenuen: siderne grupperet efter hvad man er i gang med (Drift / Opsætning / System).
// En ny side tilføjes her i den gruppe den hører til — menuen bliver ikke bredere af det.
import { roleAtLeast, type Role } from './api';

export interface NavPage { id: string; label: string; role: Role; icon: string }
export interface NavGroup { id: string; label: string; pages: NavPage[] }

export const NAV: NavGroup[] = [
  { id: 'drift', label: 'Drift', pages: [
    { id: 'overview', label: 'Overview', role: 'viewer', icon: 'overview' },
    { id: 'alarms', label: 'Alarmer', role: 'viewer', icon: 'alarms' },
    { id: 'trends', label: 'Trends', role: 'viewer', icon: 'trends' },
    { id: 'energy', label: 'Energi', role: 'viewer', icon: 'energy' },
  ] },
  { id: 'setup', label: 'Opsætning', pages: [
    { id: 'drawings', label: 'Tegninger', role: 'viewer', icon: 'drawings' },
    { id: 'draw', label: 'Tegn', role: 'engineer', icon: 'draw' },
    { id: 'editor', label: 'Bindinger', role: 'engineer', icon: 'bindings' },
    { id: 'tags', label: 'Tags', role: 'viewer', icon: 'tags' },
    { id: 'schedules', label: 'Ugeprogrammer', role: 'engineer', icon: 'schedules' },
    { id: 'plcs', label: "PLC'er", role: 'engineer', icon: 'plcs' },
  ] },
  { id: 'system', label: 'System', pages: [
    { id: 'audit', label: 'Log', role: 'engineer', icon: 'audit' },
    { id: 'users', label: 'Brugere', role: 'admin', icon: 'users' },
    { id: 'backup', label: 'Backup', role: 'admin', icon: 'backup' },
    { id: 'update', label: 'Opdatering', role: 'admin', icon: 'update' },
  ] },
];

/** Grupperne med de sider rollen må se; grupper uden sider udelades. */
export function navFor(role: Role | undefined): NavGroup[] {
  return NAV.map((g) => ({ ...g, pages: g.pages.filter((p) => roleAtLeast(role, p.role)) })).filter((g) => g.pages.length);
}

/** Den side ruten peger på — en side rollen ikke må se (eller en ukendt rute) giver Overview. */
export function pageFor(route: string, role: Role | undefined): NavPage {
  const id = route.split('/')[0];
  const all = navFor(role).flatMap((g) => g.pages);
  return all.find((p) => p.id === id) ?? NAV[0].pages[0];
}

/** Gruppen siden hører til (til brødkrummen i topbjælken). */
export const groupOf = (pageId: string): NavGroup | undefined => NAV.find((g) => g.pages.some((p) => p.id === pageId));

/** Ikoner (24×24, streg) til menuen. */
export const NAV_ICON: Record<string, string> = {
  overview: '<rect x="3" y="4" width="18" height="14" rx="1"/><path d="M7 14l3-4 3 3 4-5"/>',
  alarms: '<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z"/><path d="M10 20a2 2 0 0 0 4 0"/>',
  trends: '<path d="M3 20h18"/><path d="M4 16l5-6 4 3 7-8"/>',
  energy: '<path d="M13 2L5 14h6l-1 8 8-12h-6z"/>',
  drawings: '<path d="M4 4h10l6 6v10H4z"/><path d="M14 4v6h6"/>',
  draw: '<path d="M4 20l4-1 11-11-3-3L5 16z"/>',
  bindings: '<circle cx="7" cy="12" r="3"/><circle cx="17" cy="12" r="3"/><path d="M10 12h4"/>',
  tags: '<path d="M3 12V4h8l10 10-8 8z"/><circle cx="7.5" cy="8.5" r="1.3"/>',
  schedules: '<rect x="3" y="5" width="18" height="16" rx="1"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  plcs: '<rect x="4" y="6" width="16" height="12" rx="1"/><path d="M8 10v4M12 10v4M16 10v4"/>',
  audit: '<path d="M5 4h14v16H5z"/><path d="M8 8h8M8 12h8M8 16h5"/>',
  users: '<circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><path d="M16 5a3 3 0 0 1 0 6M21 20c0-2.6-1.6-4.8-4-5.6"/>',
  backup: '<path d="M4 7c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3z"/><path d="M4 7v10c0 1.7 3.6 3 8 3s8-1.3 8-3V7"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
  update: '<path d="M12 3v12"/><path d="M7 10l5-5 5 5"/><path d="M4 15v4h16v-4"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M17 6l3 3"/>',
  logout: '<path d="M10 4H5v16h5"/><path d="M14 8l4 4-4 4M18 12H9"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"/>',
};
