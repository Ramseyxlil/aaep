/**
 * useAAEPEvents — React hook for subscribing to an AAEP producer.
 *
 * Wraps the browser's EventSource API to consume the /events SSE endpoint,
 * manages connection state, exposes received events to consuming components,
 * and provides a function for POSTing replies back to /messages.
 *
 * Designed to be the lowest layer of any web-based AAEP subscriber — the
 * AAEPSubscriber component uses this hook, but other components could too.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  AAEPEvent,
  ConnectionStatus,
  ReplyResult,
} from "./types.js";

const RECONNECT_DELAYS_MS = [1_000, 2_000, 4_000, 8_000, 16_000, 32_000, 60_000];
const RECONNECT_DELAY_CAP_MS = 60_000;

export interface UseAAEPEventsOptions {
  endpoint: string;
  autoStart?: boolean;
  onConnectionStatus?: (status: ConnectionStatus) => void;
  onEvent?: (event: AAEPEvent) => void;
  onError?: (error: Error) => void;
}

export interface UseAAEPEventsResult {
  events: AAEPEvent[];
  latestEvent: AAEPEvent | null;
  status: ConnectionStatus;
  start: () => void;
  stop: () => void;
  clearEvents: () => void;
  sendReply: (
    replyToken: string,
    messageType: string,
    payload: Record<string, unknown>,
  ) => Promise<ReplyResult>;
}

/**
 * Subscribe to an AAEP producer's events.
 *
 * The hook owns one EventSource at a time. It reconnects with exponential
 * backoff on transient failures. Consumer components re-render only when
 * new events arrive (via `events` and `latestEvent`) or status changes.
 */
export function useAAEPEvents(
  options: UseAAEPEventsOptions,
): UseAAEPEventsResult {
  const {
    endpoint,
    autoStart = true,
    onConnectionStatus,
    onEvent,
    onError,
  } = options;

  const [events, setEvents] = useState<AAEPEvent[]>([]);
  const [latestEvent, setLatestEvent] = useState<AAEPEvent | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("idle");

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptRef = useRef<number>(0);
  const reconnectTimerRef = useRef<number | null>(null);
  const stoppedRef = useRef<boolean>(false);
  const optionsRef = useRef({ onConnectionStatus, onEvent, onError });

  // Keep callback refs current without forcing reconnects on re-render
  useEffect(() => {
    optionsRef.current = { onConnectionStatus, onEvent, onError };
  }, [onConnectionStatus, onEvent, onError]);

  const updateStatus = useCallback((next: ConnectionStatus) => {
    setStatus(next);
    optionsRef.current.onConnectionStatus?.(next);
  }, []);

  const closeEventSource = useCallback(() => {
    if (eventSourceRef.current !== null) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (stoppedRef.current) return;
    const attempt = Math.min(
      reconnectAttemptRef.current,
      RECONNECT_DELAYS_MS.length - 1,
    );
    const delay = Math.min(
      RECONNECT_DELAYS_MS[attempt] ?? RECONNECT_DELAY_CAP_MS,
      RECONNECT_DELAY_CAP_MS,
    );
    reconnectAttemptRef.current += 1;
    updateStatus("reconnecting");
    reconnectTimerRef.current = window.setTimeout(() => {
      reconnectTimerRef.current = null;
      connect();
    }, delay);
  }, [updateStatus]);

  const connect = useCallback(() => {
    if (stoppedRef.current) return;
    closeEventSource();
    updateStatus("connecting");

    const url = `${endpoint.replace(/\/$/, "")}/events`;
    let source: EventSource;
    try {
      source = new EventSource(url);
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      optionsRef.current.onError?.(error);
      updateStatus("error");
      scheduleReconnect();
      return;
    }
    eventSourceRef.current = source;

    source.onopen = () => {
      reconnectAttemptRef.current = 0;
      updateStatus("connected");
    };

    source.onmessage = (msgEvent) => {
      try {
        const parsed: unknown = JSON.parse(msgEvent.data);
        if (typeof parsed !== "object" || parsed === null) return;
        const event = parsed as AAEPEvent;
        setLatestEvent(event);
        setEvents((prev) => [...prev, event]);
        optionsRef.current.onEvent?.(event);
      } catch (err) {
        const error = err instanceof Error ? err : new Error(String(err));
        optionsRef.current.onError?.(error);
      }
    };

    source.onerror = () => {
      // EventSource auto-reconnects but we want our own backoff strategy
      // to surface status changes consistently.
      updateStatus("disconnected");
      closeEventSource();
      scheduleReconnect();
    };
  }, [endpoint, updateStatus, closeEventSource, scheduleReconnect]);

  const start = useCallback(() => {
    stoppedRef.current = false;
    reconnectAttemptRef.current = 0;
    connect();
  }, [connect]);

  const stop = useCallback(() => {
    stoppedRef.current = true;
    closeEventSource();
    updateStatus("idle");
  }, [closeEventSource, updateStatus]);

  const clearEvents = useCallback(() => {
    setEvents([]);
    setLatestEvent(null);
  }, []);

  const sendReply = useCallback(
    async (
      replyToken: string,
      messageType: string,
      payload: Record<string, unknown>,
    ): Promise<ReplyResult> => {
      const url = `${endpoint.replace(/\/$/, "")}/messages`;
      const body = {
        type: messageType,
        reply_token: replyToken,
        timestamp: new Date().toISOString(),
        ...payload,
      };
      try {
        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!response.ok) {
          return {
            success: false,
            error: `HTTP ${response.status}`,
          };
        }
        return { success: true };
      } catch (err) {
        const error = err instanceof Error ? err.message : String(err);
        return { success: false, error };
      }
    },
    [endpoint],
  );

  // Auto-start on mount, clean up on unmount
  useEffect(() => {
    if (autoStart) {
      start();
    }
    return () => {
      stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endpoint, autoStart]);

  return {
    events,
    latestEvent,
    status,
    start,
    stop,
    clearEvents,
    sendReply,
  };
}
