import { describe, expect, it } from 'vitest';
import { TOOL_HINTS, toolHint } from './toolHints';

describe('hjælpelinjen i Tegn (v0.92.0)', () => {
  it('alle værktøjer i venstre side har en dansk hjælp', () => {
    for (const mode of ['select', 'zoom', 'ext-panning', 'fhpath', 'line', 'path', 'rect', 'square', 'ellipse', 'circle', 'text', 'image', 'star', 'polygon', 'eyedropper', 'shapelib']) {
      expect(TOOL_HINTS[mode], mode).toBeDefined();
      expect(TOOL_HINTS[mode].how.length, mode).toBeGreaterThan(20);
    }
  });
  it('tegneværktøjer fortæller, hvordan man kommer tilbage', () => {
    for (const mode of ['line', 'path', 'rect', 'ellipse', 'text', 'star']) expect(toolHint(mode).how).toContain('Esc');
  });
  it('ukendt værktøj giver en generel tekst', () => {
    expect(toolHint('noget-nyt')).toEqual({ name: 'Værktøj', how: expect.stringContaining('Peg på et værktøj') });
  });
});
