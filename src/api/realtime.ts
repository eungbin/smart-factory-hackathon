import type { DashboardResponse } from './dashboard';
import type { SimulationTickResponse } from './simulation';

export type DashboardRealtimeEvent = {
  type: 'dashboard_updated';
  generatedAt: string;
  includedPredictions: boolean;
  tick: SimulationTickResponse['data'];
  dashboard: DashboardResponse['data'];
};

export type RealtimeEvent = DashboardRealtimeEvent;

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000';
const RECONNECT_DELAY_MS = 2000;

function getRealtimeUrl() {
  const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, '');
  const url = new URL('/api/v1/realtime', baseUrl);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  return url.toString();
}

export function subscribeRealtime(
  onEvent: (event: RealtimeEvent) => void,
  onConnectionChange?: (isConnected: boolean) => void,
): () => void {
  let socket: WebSocket | null = null;
  let reconnectTimer: number | undefined;
  let closed = false;

  function connect() {
    socket = new WebSocket(getRealtimeUrl());

    socket.onopen = () => {
      onConnectionChange?.(true);
    };

    socket.onmessage = message => {
      const event = JSON.parse(message.data) as RealtimeEvent;
      if (event.type === 'dashboard_updated') {
        onEvent(event);
      }
    };

    socket.onerror = () => {
      onConnectionChange?.(false);
      socket?.close();
    };

    socket.onclose = () => {
      onConnectionChange?.(false);
      if (!closed) {
        reconnectTimer = window.setTimeout(connect, RECONNECT_DELAY_MS);
      }
    };
  }

  connect();

  return () => {
    closed = true;
    if (reconnectTimer !== undefined) {
      window.clearTimeout(reconnectTimer);
    }
    socket?.close();
  };
}
