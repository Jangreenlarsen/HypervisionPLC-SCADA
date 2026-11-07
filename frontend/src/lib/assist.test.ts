import { describe, expect, it } from 'vitest';
import { answerHtml, contextFromRoute, historyFor, parseSse, timingText, type Turn } from './assist';

describe('parseSse', () => {
  it('splits complete events and keeps the unfinished rest', () => {
    const buf = 'data: {"type":"sources","sources":[],"tools":[]}\n\n: venter\n\ndata: {"type":"delta","text":"Hej"}\n\ndata: {"type":"del';
    const { events, rest } = parseSse(buf);
    expect(events.map((e) => e.type)).toEqual(['sources', 'delta']);
    expect(rest).toBe('data: {"type":"del');
    const more = parseSse(rest + 'ta","text":" du"}\n\n');
    expect(more.events).toEqual([{ type: 'delta', text: ' du' }]);
    expect(more.rest).toBe('');
  });
  it('ignores invalid JSON and CRLF line endings work', () => {
    const { events } = parseSse('data: {ikke json}\r\n\r\ndata: {"type":"error","message":"x"}\r\n\r\n');
    expect(events).toEqual([{ type: 'error', message: 'x' }]);
  });
});

describe('context and history', () => {
  it('takes the drawing from the address on drawing pages only', () => {
    expect(contextFromRoute('overview/anlaeg-a', 'overview')).toEqual({ page: 'overview', drawing: 'anlaeg-a' });
    expect(contextFromRoute('draw/k%C3%A6lder', 'draw').drawing).toBe('kælder');
    expect(contextFromRoute('trends/abc', 'trends').drawing).toBeNull();
    expect(contextFromRoute('overview', 'overview').drawing).toBeNull();
  });
  it('sends only the last four real turns, without errors', () => {
    const turns: Turn[] = [
      { role: 'user', content: '1' }, { role: 'assistant', content: 'a' }, { role: 'user', content: '2' },
      { role: 'assistant', content: 'fejl', error: true }, { role: 'user', content: '3' }, { role: 'assistant', content: 'c' },
      { role: 'user', content: '4' }, { role: 'assistant', content: '' },
    ];
    expect(historyFor(turns)).toEqual([{ role: 'assistant', content: 'a' }, { role: 'user', content: '2' },
      { role: 'user', content: '3' }, { role: 'assistant', content: 'c' }, { role: 'user', content: '4' }].slice(-4));
  });
});

describe('answerHtml', () => {
  it('keeps formatting but never links, images or html from the model', () => {
    const html = answerHtml('**Tjek** pumpen:\n- tryk\n- [klik](http://x.dk) ![b](http://x.dk/a.png) <img src=x onerror=alert(1)>');
    expect(html).toContain('<strong>Tjek</strong>');
    expect(html).toContain('<li>tryk</li>');
    expect(html).not.toMatch(/<a |<img|href=/);
    expect(html).toContain('&lt;img');
    expect(html).toContain('klik');
  });
  it('formats timing in Danish', () => {
    expect(timingText({ ms: 41234, tokens_per_s: 3.2 })).toBe('41,2 s · 3,2 tokens/s');
    expect(timingText({ ms: 900, tokens_per_s: 0 })).toBe('0,9 s');
  });
});
