import { describe, expect, it } from 'vitest';
import { NAV, NAV_ICON, groupOf, navFor, navHref, pageFor } from './nav';

const ids = (role: Parameters<typeof navFor>[0]) => navFor(role).map((g) => `${g.id}:${g.pages.map((p) => p.id).join(',')}`);

describe('hovedmenuen', () => {
  it('viser kun grupper og sider rollen må se', () => {
    expect(ids('viewer')).toEqual(['drift:overview,alarms,trends,energy', 'setup:drawings,tags']);
    expect(ids('operator')).toEqual(ids('viewer'));
    expect(ids('engineer')).toEqual([
      'drift:overview,alarms,trends,energy', 'setup:drawings,draw,editor,tags,schedules,plcs,symboltest', 'system:audit']);
    expect(ids('admin').at(-1)).toBe('system:audit,users,backup,update,config');
    expect(ids(undefined)).toEqual([]);
  });
  it('ruten giver siden — ukendt eller ikke tilladt side giver Overview', () => {
    expect(pageFor('editor/tegning1/V1', 'engineer').label).toBe('Bindinger');
    expect(pageFor('editor', 'operator').id).toBe('overview');
    expect(pageFor('findes-ikke', 'admin').id).toBe('overview');
    expect(groupOf('backup')?.label).toBe('System');
  });
  it('Manual er en side under Bruger for alle roller — ikke en gruppe-side', () => {
    expect(pageFor('manual', 'viewer').id).toBe('manual');
    expect(pageFor('manual/symboler/m-trin', 'admin').id).toBe('manual');
    expect(pageFor('manual', undefined).id).toBe('overview');          // ikke logget ind
    expect(groupOf('manual')?.label).toBe('Bruger');
    expect(ids('viewer').join()).not.toContain('manual');
    expect(NAV_ICON.manual).toBeTruthy();
  });
  it('hver side har et ikon og et unikt id', () => {
    const pages = NAV.flatMap((g) => g.pages);
    expect(new Set(pages.map((p) => p.id)).size).toBe(pages.length);
    for (const p of pages) expect(NAV_ICON[p.icon], p.id).toBeTruthy();
  });
});

describe('menulink (v0.79.0)', () => {
  it('Tegn og Bindinger åbner tegningen man står på i Overview', () => {
    expect(navHref('draw', 'overview/kedelrum')).toBe('#draw/kedelrum');
    expect(navHref('editor', 'overview/kedelrum')).toBe('#editor/kedelrum');
    expect(navHref('tags', 'overview/kedelrum')).toBe('#tags');
    expect(navHref('draw', 'overview')).toBe('#draw');
    expect(navHref('draw', 'overview/')).toBe('#draw');
    expect(navHref('draw', 'trends')).toBe('#draw');
    expect(navHref('draw', 'draw/kedelrum')).toBe('#draw');
  });
});
