import { describe, expect, it } from 'vitest';
import { NAV, NAV_ICON, groupOf, navFor, pageFor } from './nav';

const ids = (role: Parameters<typeof navFor>[0]) => navFor(role).map((g) => `${g.id}:${g.pages.map((p) => p.id).join(',')}`);

describe('hovedmenuen', () => {
  it('viser kun grupper og sider rollen må se', () => {
    expect(ids('viewer')).toEqual(['drift:overview,alarms,trends,energy', 'setup:drawings,tags']);
    expect(ids('operator')).toEqual(ids('viewer'));
    expect(ids('engineer')).toEqual([
      'drift:overview,alarms,trends,energy', 'setup:drawings,draw,editor,tags,schedules,plcs', 'system:audit']);
    expect(ids('admin').at(-1)).toBe('system:audit,users,backup');
    expect(ids(undefined)).toEqual([]);
  });
  it('ruten giver siden — ukendt eller ikke tilladt side giver Overview', () => {
    expect(pageFor('editor/tegning1/V1', 'engineer').label).toBe('Bindinger');
    expect(pageFor('editor', 'operator').id).toBe('overview');
    expect(pageFor('findes-ikke', 'admin').id).toBe('overview');
    expect(groupOf('backup')?.label).toBe('System');
  });
  it('hver side har et ikon og et unikt id', () => {
    const pages = NAV.flatMap((g) => g.pages);
    expect(new Set(pages.map((p) => p.id)).size).toBe(pages.length);
    for (const p of pages) expect(NAV_ICON[p.icon], p.id).toBeTruthy();
  });
});
