// Den nye tegne-editors tastatur og zoomtrin (ren logik i engine.ts).
import { describe, expect, it, vi } from 'vitest';

vi.mock('@svgedit/svgcanvas', () => ({ default: class {} }));
vi.mock('../../../svgedit-host/scada-core.js', () => ({ createScada: () => ({}) }));
const { shortcutFor, zoomStep, clampZoom, ZOOM_MAX, ZOOM_MIN } = await import('./engine');

const key = (k: string, o: Partial<{ ctrlKey: boolean; metaKey: boolean; shiftKey: boolean; altKey: boolean }> = {}) =>
  shortcutFor({ key: k, ctrlKey: false, metaKey: false, shiftKey: false, altKey: false, ...o });

describe('shortcutFor', () => {
  it('fortryd/gentag inkl. Ctrl+Shift+Z og Mac-tasten', () => {
    expect(key('z', { ctrlKey: true })).toBe('undo');
    expect(key('Z', { ctrlKey: true, shiftKey: true })).toBe('redo');
    expect(key('y', { metaKey: true })).toBe('redo');
  });
  it('udklip, dupliker, gruppér', () => {
    expect(key('c', { ctrlKey: true })).toBe('copy');
    expect(key('v', { ctrlKey: true })).toBe('paste');
    expect(key('d', { ctrlKey: true })).toBe('duplicate');
    expect(key('g', { ctrlKey: true })).toBe('group');
    expect(key('G', { ctrlKey: true, shiftKey: true })).toBe('ungroup');
  });
  it('pile flytter 1, med Shift 10', () => {
    expect(key('ArrowLeft')).toBe('nudgeLeft1');
    expect(key('ArrowDown', { shiftKey: true })).toBe('nudgeDown10');
  });
  it('enkeltbogstaver vælger værktøj, men ikke med Alt/Shift', () => {
    expect(key('r')).toBe('tool:rect');
    expect(key('t')).toBe('tool:text');
    expect(key('r', { altKey: true })).toBeNull();
    expect(key('R', { shiftKey: true })).toBeNull();
    expect(key('q')).toBeNull();
  });
  it('slet og Escape', () => {
    expect(key('Delete')).toBe('delete');
    expect(key('Backspace')).toBe('delete');
    expect(key('Escape')).toBe('escape');
  });
});

describe('zoom', () => {
  it('trin op og ned fra 100 %', () => {
    expect(zoomStep(1, 1)).toBe(1.25);
    expect(zoomStep(1, -1)).toBe(0.75);
  });
  it('trin fra en skæv zoom (efter Tilpas) går til nærmeste runde', () => {
    expect(zoomStep(0.83, 1)).toBe(1);
    expect(zoomStep(0.83, -1)).toBe(0.75);
  });
  it('grænser', () => {
    expect(zoomStep(ZOOM_MAX, 1)).toBe(ZOOM_MAX);
    expect(zoomStep(ZOOM_MIN, -1)).toBe(ZOOM_MIN);
    expect(clampZoom(100)).toBe(ZOOM_MAX);
    expect(clampZoom(0)).toBe(ZOOM_MIN);
  });
});
