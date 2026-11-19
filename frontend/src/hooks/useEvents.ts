import { useEffect, useRef } from "react";
import { api } from "../api/client";

export interface ServerEvent {
  type: string;
  data: Record<string, unknown>;
}

/**
 * Subscribe to server push events (import progress now; alerts/cases later).
 * Gets a single-use ticket over REST, then opens the WebSocket. Failure is silent by design:
 * pages also poll, so realtime is an enhancement, not a dependency.
 */
export function useEvents(onEvent: (e: ServerEvent) => void): void {
  const handler = useRef(onEvent);
  useEffect(() => {
    handler.current = onEvent;
  });
  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;
    api
      .post<{ ticket: string }>("/ws/ticket/")
      .then(({ ticket }) => {
        if (closed) return;
        const scheme = window.location.protocol === "https:" ? "wss" : "ws";
        ws = new WebSocket(
          `${scheme}://${window.location.host}/ws/events/?ticket=${encodeURIComponent(ticket)}`,
        );
        ws.onmessage = (m) => {
          try {
            handler.current(JSON.parse(m.data as string) as ServerEvent);
          } catch {
            /* ignore malformed frames */
          }
        };
      })
      .catch(() => undefined);
    return () => {
      closed = true;
      ws?.close();
    };
  }, []);
}
