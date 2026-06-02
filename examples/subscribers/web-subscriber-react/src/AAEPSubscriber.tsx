/**
 * AAEPSubscriber — the main React component.
 *
 * Renders two ARIA live regions (polite + assertive) for screen reader
 * announcements, plus optional UI for the visible event log and
 * confirmation/clarification dialogs.
 *
 * Designed to be drop-in: import the component, pass an endpoint URL,
 * and it Just Works for AT users.
 */

import * as React from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useAAEPEvents } from "./useAAEPEvents.js";
import type {
  AAEPClarificationEvent,
  AAEPConfirmationEvent,
  AAEPEvent,
  ConnectionStatus,
} from "./types.js";
import {
  isClarificationEvent,
  isConfirmationEvent,
  isCriticalEvent,
} from "./types.js";

export interface AAEPSubscriberProps {
  /** AAEP producer base URL (required) */
  endpoint: string;
  /** Language preference order (default: ["en"]) */
  preferredLanguages?: string[];
  /** Render the visible event log next to live regions (default: false) */
  showEventLog?: boolean;
  /** Maximum events to retain in the visible log (default: 50) */
  maxLogEntries?: number;
  /** Auto-connect on mount (default: true) */
  autoStart?: boolean;
  /** Callback for connection state changes */
  onConnectionStatus?: (status: ConnectionStatus) => void;
  /** Callback for every received event */
  onEvent?: (event: AAEPEvent) => void;
  /** Visual theme (default: "auto") */
  theme?: "light" | "dark" | "auto";
  /** ms before showing a timeout warning to the user (default: 30000) */
  replyTimeout?: number;
  /** Optional className for the root container */
  className?: string;
}

interface PendingReply {
  event: AAEPConfirmationEvent | AAEPClarificationEvent;
  type: "confirmation" | "clarification";
}

export function AAEPSubscriber(props: AAEPSubscriberProps): React.ReactElement {
  const {
    endpoint,
    preferredLanguages = ["en"],
    showEventLog = false,
    maxLogEntries = 50,
    autoStart = true,
    onConnectionStatus,
    onEvent,
    theme = "auto",
    replyTimeout = 30_000,
    className = "",
  } = props;

  const [politeText, setPoliteText] = useState("");
  const [assertiveText, setAssertiveText] = useState("");
  const [pendingReply, setPendingReply] = useState<PendingReply | null>(null);
  const acceptButtonRef = useRef<HTMLButtonElement | null>(null);

  const handleEvent = useCallback(
    (event: AAEPEvent) => {
      onEvent?.(event);
      const text = selectSummary(event, preferredLanguages);

      if (isConfirmationEvent(event)) {
        setPendingReply({ event, type: "confirmation" });
        setAssertiveText(
          `${text} Press A to accept, R to reject. ` +
          `Action: ${event.action}. ${event.consequence ?? ""}`,
        );
        return;
      }

      if (isClarificationEvent(event)) {
        setPendingReply({ event, type: "clarification" });
        const optionsText = (event.options ?? [])
          .map((opt, i) => `${i + 1}: ${opt}`)
          .join(", ");
        setAssertiveText(
          optionsText
            ? `${event.question} Options: ${optionsText}.`
            : event.question,
        );
        return;
      }

      // Normal events go to polite; critical (errors, handoff) to assertive
      if (text) {
        if (isCriticalEvent(event)) {
          setAssertiveText(text);
        } else {
          setPoliteText(text);
        }
      }
    },
    [preferredLanguages, onEvent],
  );

  const {
    events,
    status,
    sendReply,
    clearEvents,
  } = useAAEPEvents({
    endpoint,
    autoStart,
    onConnectionStatus,
    onEvent: handleEvent,
  });

  // Focus the Accept button when a confirmation arrives
  useEffect(() => {
    if (pendingReply !== null && pendingReply.type === "confirmation") {
      acceptButtonRef.current?.focus();
    }
  }, [pendingReply]);

  const handleAccept = useCallback(async () => {
    if (pendingReply === null || pendingReply.type !== "confirmation") return;
    const event = pendingReply.event as AAEPConfirmationEvent;
    setPendingReply(null);
    setAssertiveText("Accepted.");
    await sendReply(event.reply_token, "confirmation.reply", {
      decision: "accept",
    });
  }, [pendingReply, sendReply]);

  const handleReject = useCallback(async () => {
    if (pendingReply === null || pendingReply.type !== "confirmation") return;
    const event = pendingReply.event as AAEPConfirmationEvent;
    setPendingReply(null);
    setAssertiveText("Rejected.");
    await sendReply(event.reply_token, "confirmation.reply", {
      decision: "reject",
    });
  }, [pendingReply, sendReply]);

  const handleClarificationOption = useCallback(
    async (option: string) => {
      if (pendingReply === null || pendingReply.type !== "clarification") return;
      const event = pendingReply.event as AAEPClarificationEvent;
      setPendingReply(null);
      setAssertiveText(`Selected: ${option}`);
      await sendReply(event.reply_token, "clarification.reply", {
        response: option,
      });
    },
    [pendingReply, sendReply],
  );

  // Keyboard shortcuts: A = accept, R = reject (only while confirmation pending)
  useEffect(() => {
    if (pendingReply === null || pendingReply.type !== "confirmation") {
      return undefined;
    }
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement
          || e.target instanceof HTMLTextAreaElement) {
        return; // don't intercept typing into other inputs
      }
      const key = e.key.toLowerCase();
      if (key === "a") {
        e.preventDefault();
        void handleAccept();
      } else if (key === "r") {
        e.preventDefault();
        void handleReject();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [pendingReply, handleAccept, handleReject]);

  const rootClasses = [
    "aaep-subscriber",
    `aaep-theme-${theme}`,
    className,
  ].filter(Boolean).join(" ");

  return (
    <div className={rootClasses}>
      {/* === ARIA live regions === */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="aaep-live-region aaep-live-polite"
        id="aaep-polite-region"
      >
        {politeText}
      </div>
      <div
        role="status"
        aria-live="assertive"
        aria-atomic="true"
        className="aaep-live-region aaep-live-assertive"
        id="aaep-assertive-region"
      >
        {assertiveText}
      </div>

      {/* === Confirmation UI === */}
      {pendingReply !== null && pendingReply.type === "confirmation" && (
        <ConfirmationDialog
          event={pendingReply.event as AAEPConfirmationEvent}
          onAccept={handleAccept}
          onReject={handleReject}
          acceptButtonRef={acceptButtonRef}
          timeoutMs={replyTimeout}
        />
      )}

      {/* === Clarification UI === */}
      {pendingReply !== null && pendingReply.type === "clarification" && (
        <ClarificationDialog
          event={pendingReply.event as AAEPClarificationEvent}
          onSelect={handleClarificationOption}
        />
      )}

      {/* === Optional event log === */}
      {showEventLog && (
        <EventLog
          events={events.slice(-maxLogEntries)}
          status={status}
          onClear={clearEvents}
        />
      )}
    </div>
  );
}


function ConfirmationDialog({
  event,
  onAccept,
  onReject,
  acceptButtonRef,
  timeoutMs,
}: {
  event: AAEPConfirmationEvent;
  onAccept: () => void;
  onReject: () => void;
  acceptButtonRef: React.RefObject<HTMLButtonElement | null>;
  timeoutMs: number;
}): React.ReactElement {
  const [remaining, setRemaining] = useState<number>(
    Math.min(timeoutMs / 1000, event.timeout_seconds ?? 300),
  );

  useEffect(() => {
    const interval = window.setInterval(() => {
      setRemaining((r) => Math.max(0, r - 1));
    }, 1000);
    return () => window.clearInterval(interval);
  }, []);

  const minutes = Math.floor(remaining / 60);
  const seconds = Math.floor(remaining % 60);
  const timeText = `${minutes}:${seconds.toString().padStart(2, "0")}`;

  return (
    <div
      className="aaep-dialog aaep-confirmation"
      role="dialog"
      aria-modal="true"
      aria-labelledby="aaep-confirmation-title"
      aria-describedby="aaep-confirmation-description"
    >
      <h2 id="aaep-confirmation-title" className="aaep-dialog-title">
        Confirm: {event.action}
      </h2>
      <p id="aaep-confirmation-description" className="aaep-dialog-body">
        {event.consequence ?? "This action will be performed."}
      </p>
      <div className="aaep-dialog-actions">
        <button
          ref={acceptButtonRef}
          onClick={onAccept}
          className="aaep-button aaep-button-accept"
          aria-label="Accept this action"
        >
          Accept (A)
        </button>
        <button
          onClick={onReject}
          className="aaep-button aaep-button-reject"
          aria-label="Reject this action"
        >
          Reject (R)
        </button>
      </div>
      <p className="aaep-dialog-timeout" aria-live="polite">
        Auto-rejects in {timeText}
      </p>
    </div>
  );
}


function ClarificationDialog({
  event,
  onSelect,
}: {
  event: AAEPClarificationEvent;
  onSelect: (option: string) => void;
}): React.ReactElement {
  return (
    <div
      className="aaep-dialog aaep-clarification"
      role="dialog"
      aria-modal="true"
      aria-labelledby="aaep-clarification-title"
    >
      <h2 id="aaep-clarification-title" className="aaep-dialog-title">
        {event.question}
      </h2>
      {(event.options ?? []).length > 0 ? (
        <ul className="aaep-options-list">
          {(event.options ?? []).map((option, i) => (
            <li key={i}>
              <button
                onClick={() => onSelect(option)}
                className="aaep-button aaep-button-option"
                aria-label={`Option ${i + 1}: ${option}`}
              >
                {i + 1}. {option}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p>(Awaiting clarification — free-form input not yet implemented in v0.1)</p>
      )}
    </div>
  );
}


function EventLog({
  events,
  status,
  onClear,
}: {
  events: AAEPEvent[];
  status: ConnectionStatus;
  onClear: () => void;
}): React.ReactElement {
  return (
    <details className="aaep-event-log">
      <summary>
        AAEP Event Log ({events.length}, status: {status})
        <button
          onClick={onClear}
          aria-label="Clear event log"
          className="aaep-log-clear"
        >
          Clear
        </button>
      </summary>
      <ul className="aaep-log-list">
        {events.map((event, i) => (
          <li key={i} className={`aaep-log-entry aaep-log-${event.urgency ?? "normal"}`}>
            <code className="aaep-log-type">{event.type}</code>
            <span className="aaep-log-summary">
              {event.summary_normal ?? ""}
            </span>
          </li>
        ))}
      </ul>
    </details>
  );
}


// Helpers

function selectSummary(event: AAEPEvent, preferredLanguages: string[]): string {
  const eventLang = typeof event.language === "string" ? event.language : "en";
  if (preferredLanguages.includes(eventLang) && event.summary_normal) {
    return event.summary_normal;
  }
  // Note: translation lookup would happen on the producer side; in the
  // browser we just render what's provided. See README for the full design.
  return event.summary_normal ?? "";
}
