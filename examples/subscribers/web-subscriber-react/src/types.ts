/**
 * AAEP event type definitions.
 *
 * Mirrors the shape of events emitted by AAEP producers. This file is the
 * structural contract between this subscriber and any conforming producer.
 *
 * See the AAEP specification chapter 4 for the canonical event schemas:
 * https://aaep-protocol.org/spec/04-event-types
 */

export type AAEPUrgency = "normal" | "critical";

export type AAEPRiskLevel = "low" | "medium" | "high";

export type AAEPDefaultDecision = "accept" | "reject";

export type AAEPEventType =
  | "aaep:agent.session.started"
  | "aaep:agent.session.completed"
  | "aaep:agent.session.errored"
  | "aaep:agent.session.cancelled"
  | "aaep:agent.state.changed"
  | "aaep:agent.progress.updated"
  | "aaep:agent.tool.invoked"
  | "aaep:agent.tool.completed"
  | "aaep:agent.output.streaming"
  | "aaep:agent.awaiting.confirmation"
  | "aaep:agent.awaiting.clarification"
  | "aaep:agent.handoff.requested";

/**
 * Common envelope fields present on every AAEP event.
 */
export interface AAEPEventEnvelope {
  type: AAEPEventType;
  session_id: string;
  event_id?: string;
  timestamp: string;
  urgency?: AAEPUrgency;
  language?: string;
  summary_terse?: string;
  summary_normal?: string;
  summary_detailed?: string;
  reply_token?: string;
  producer?: {
    agent_id?: string;
    agent_name?: string;
    agent_version?: string;
    model?: string;
  };
}

/**
 * Structural type for any AAEP event. The envelope fields are guaranteed;
 * type-specific fields are optional and depend on the event type.
 */
export interface AAEPEvent extends AAEPEventEnvelope {
  [key: string]: unknown;
}

/**
 * Specifically-typed confirmation event for type-safe handlers.
 */
export interface AAEPConfirmationEvent extends AAEPEventEnvelope {
  type: "aaep:agent.awaiting.confirmation";
  reply_token: string;
  action: string;
  consequence?: string;
  risk_level?: AAEPRiskLevel;
  irreversible?: boolean;
  default_decision?: AAEPDefaultDecision;
  timeout_seconds?: number;
  [key: string]: unknown;
}

/**
 * Specifically-typed clarification event for type-safe handlers.
 */
export interface AAEPClarificationEvent extends AAEPEventEnvelope {
  type: "aaep:agent.awaiting.clarification";
  reply_token: string;
  question: string;
  options?: string[];
  multi_select?: boolean;
  free_form_allowed?: boolean;
  timeout_seconds?: number;
  [key: string]: unknown;
}

export type ConnectionStatus =
  | "idle"
  | "connecting"
  | "connected"
  | "disconnected"
  | "error"
  | "reconnecting";

export interface ReplyResult {
  success: boolean;
  error?: string;
}

/**
 * Type guard: is this event an awaiting.confirmation?
 */
export function isConfirmationEvent(
  event: AAEPEvent,
): event is AAEPConfirmationEvent {
  return event.type === "aaep:agent.awaiting.confirmation"
    && typeof event.reply_token === "string"
    && typeof event.action === "string";
}

/**
 * Type guard: is this event an awaiting.clarification?
 */
export function isClarificationEvent(
  event: AAEPEvent,
): event is AAEPClarificationEvent {
  return event.type === "aaep:agent.awaiting.clarification"
    && typeof event.reply_token === "string"
    && typeof event.question === "string";
}

/**
 * Should this event be announced via aria-live="assertive"?
 */
export function isCriticalEvent(event: AAEPEvent): boolean {
  if (event.urgency === "critical") return true;
  return (
    event.type === "aaep:agent.session.errored" ||
    event.type === "aaep:agent.awaiting.confirmation" ||
    event.type === "aaep:agent.awaiting.clarification" ||
    event.type === "aaep:agent.handoff.requested"
  );
}
