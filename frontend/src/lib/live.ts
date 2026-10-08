// WebSocket-klient til /ws/live med automatisk genforbindelse.
import { notifyUnauthorized, type Alarm, type AlarmSummary, type LiveValue, type PlcSummary } from './api';

type Listener = (values: Record<string, LiveValue>) => void;
type StatusListener = (plcs: Record<string, PlcSummary>, connected: boolean) => void;

export class LiveClient {
  private ws: WebSocket | null = null;
  private tags: string[] = [];
  private closed = false;
  private retry = 1000;
  private timer: ReturnType<typeof setTimeout> | null = null;
  connected = false;
  plcs: Record<string, PlcSummary> = {};
  /** Kaldes når serveren sender en ny alarmliste (ved forbindelse og ved hver ændring). */
  onAlarms: ((summary: AlarmSummary, active: Alarm[]) => void) | null = null;

  constructor(private onValues: Listener, private onStatus: StatusListener = () => {}) {
    this.connect();
  }

  subscribe(tags: string[]): void {
    this.tags = [...new Set(tags)];
    this.send();
  }

  close(): void {
    this.closed = true;
    if (this.timer) clearTimeout(this.timer);
    this.ws?.close();
  }

  private send(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'subscribe', tags: this.tags }));
    }
  }

  private connect(): void {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${location.host}/ws/live`);
    this.ws = ws;
    ws.onopen = () => {
      this.connected = true;
      this.retry = 1000;
      this.onStatus(this.plcs, true);
      this.send();
    };
    ws.onmessage = (ev) => {
      let msg: any;
      try {
        msg = JSON.parse(ev.data);
      } catch {
        console.warn('Ugyldig besked fra /ws/live', ev.data);
        return;
      }
      if (msg.type === 'snapshot' || msg.type === 'delta') this.onValues(msg.values);
      else if (msg.type === 'plcs') {
        this.plcs = msg.plcs;
        this.onStatus(this.plcs, true);
      } else if (msg.type === 'alarms') this.onAlarms?.(msg.summary, msg.active);
      else if (msg.type === 'error') console.error('Live-fejl fra server:', msg.error);
    };
    ws.onclose = (ev) => {
      this.connected = false;
      if (ev.code === 4401) {
        // Sessionen er udløbet — app'en viser login; genforbind først når siden genindlæses.
        this.onStatus(this.plcs, false);
        notifyUnauthorized();
        return;
      }
      this.onStatus(this.plcs, false);
      if (this.closed) return;
      this.timer = setTimeout(() => this.connect(), this.retry);
      this.retry = Math.min(this.retry * 2, 15000);
    };
  }
}
