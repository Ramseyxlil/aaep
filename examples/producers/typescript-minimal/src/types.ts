/**
 * TypeScript type definitions for AAEP events.
 *
 * These interfaces match the JSON Schemas exactly. Importing this file
 * gives you full type safety: editor autocomplete shows valid field names,
 * the compiler catches missing required fields, and discriminated unions
 * allow exhaustive switch statements on event type.
 *
 * See https://aaep-protocol.org/schemas/v1/ for the canonical schemas.
 */

// === Enumerated values ===

export type Urgency = "normal" | "critical";
export type Verbosity = "terse" | "normal" | "detailed";
export type AgentState =
    | "idle"
    | "thinking"
    | "calling_tool"
    | "writing_output"
    | "awaiting_user"
    | "completed";
export type RiskLevel = "low" | "medium" | "high";
export type ToolStatus = "success" | "error" | "timeout";
export type CoalesceHint =
    | "none"
    | "word"
    | "sentence"
    | "paragraph"
    | "completion";
export type Decision = "accept" | "reject";
export type ErrorCategory =
    | "timeout"
    | "network"
    | "authentication"
    | "authorization"
    | "rate_limit"
    | "invalid_input"
    | "policy"
    | "internal"
    | "transient"
    | "unknown";
export type CancelledBy = "user" | "system" | "timeout" | "policy";
export type Reversibility =
    | "reversible_easy"
    | "reversible_with_effort"
    | "irreversible";


// === Producer info ===

export interface Producer {
    agent_id: string;
    agent_version?: string;
    agent_name?: string;
    model?: string;
}


// === Localization hints (optional in all events) ===

export interface LocalizationHints {
    primary_language?: string;
    text_direction?: "ltr" | "rtl";
    available_languages?: string[];
}


// === The envelope: fields common to ALL events ===

export interface AAEPEnvelope {
    "@context": string;
    aaep_version?: string;
    type: string;
    event_id: string;
    session_id: string;
    sequence_number?: number;
    timestamp: string;
    producer: Producer;
    urgency: Urgency;
    verbosity?: Verbosity;
    localization_hints?: LocalizationHints;
    summary_terse?: string;
    summary_normal: string;
    summary_detailed?: string;
}


// === Core event types (12 in v1.0.0) ===

export interface SessionStartedEvent extends AAEPEnvelope {
    type: "aaep:agent.session.started";
    request_text?: string;
    requested_by?: string;
    expected_duration_ms?: number;
    tools_available?: string[];
}

export interface SessionCompletedEvent extends AAEPEnvelope {
    type: "aaep:agent.session.completed";
    duration_ms?: number;
    tool_invocations_count?: number;
    output_summary?: string;
}

export interface SessionErroredEvent extends AAEPEnvelope {
    type: "aaep:agent.session.errored";
    urgency: "critical";  // MUST be critical
    error_category: ErrorCategory;
    error_message?: string;
    recoverable?: boolean;
    remediation_hint?: string;
}

export interface SessionCancelledEvent extends AAEPEnvelope {
    type: "aaep:agent.session.cancelled";
    cancelled_by: CancelledBy;
    cancellation_reason?: string;
}

export interface StateChangedEvent extends AAEPEnvelope {
    type: "aaep:agent.state.changed";
    from_state: AgentState | string;
    to_state: AgentState | string;
}

export interface ProgressUpdatedEvent extends AAEPEnvelope {
    type: "aaep:agent.progress.updated";
    progress_percent?: number;
    progress_message?: string;
    estimated_remaining_ms?: number;
}

export interface ToolInvokedEvent extends AAEPEnvelope {
    type: "aaep:agent.tool.invoked";
    tool: string;
    tool_call_id?: string;
    description?: string;
    args_summary: string;
    expected_duration_ms?: number;
    risk_level: RiskLevel;
    irreversible: boolean;
}

export interface ToolCompletedEvent extends AAEPEnvelope {
    type: "aaep:agent.tool.completed";
    tool: string;
    tool_call_id?: string;
    status: ToolStatus;
    error_message?: string;
}

export interface OutputStreamingEvent extends AAEPEnvelope {
    type: "aaep:agent.output.streaming";
    chunk: string;
    position: number;
    complete: boolean;
    coalesce_hint: CoalesceHint;
    output_id?: string;
    content_type?: string;
    language?: string;
}

export interface AwaitingConfirmationEvent extends AAEPEnvelope {
    type: "aaep:agent.awaiting.confirmation";
    urgency: "critical";  // MUST be critical
    action: string;
    consequence: string;
    reply_token: string;
    timeout_seconds: number;
    default_decision: Decision;
    risk_level: RiskLevel;
    irreversible: boolean;
    reversibility?: Reversibility;
}

export interface AwaitingClarificationEvent extends AAEPEnvelope {
    type: "aaep:agent.awaiting.clarification";
    urgency: "critical";  // MUST be critical
    question: string;
    reply_token: string;
    timeout_seconds: number;
    options?: string[];
    multi_select?: boolean;
    free_form_allowed?: boolean;
}

export interface HandoffRequestedEvent extends AAEPEnvelope {
    type: "aaep:agent.handoff.requested";
    urgency: "critical";  // MUST be critical
    reason: string;
    handoff_target: string;
    context_summary?: string;
}


// === Discriminated union of all core events ===

export type AAEPEvent =
    | SessionStartedEvent
    | SessionCompletedEvent
    | SessionErroredEvent
    | SessionCancelledEvent
    | StateChangedEvent
    | ProgressUpdatedEvent
    | ToolInvokedEvent
    | ToolCompletedEvent
    | OutputStreamingEvent
    | AwaitingConfirmationEvent
    | AwaitingClarificationEvent
    | HandoffRequestedEvent;


// === Handshake messages (Level 3) ===

export interface SubscriptionRequest {
    type: "subscription.request";
    aaep_version: string;
    subscriber_id: string;
    subscriber_name?: string;
    subscriber_version?: string;
    capabilities: Capabilities;
}

export interface Capabilities {
    max_events_per_second?: number;
    preferred_verbosity?: Verbosity;
    languages?: string[];
    supports_confirmation_reply?: boolean;
    supports_clarification_reply?: boolean;
    coalesce_boundaries?: CoalesceHint[];
    event_filters?: {
        include?: string[];
        exclude?: string[];
    };
    supported_conformance_levels?: number[];
    supported_extensions?: string[];
    cognitive_load?: "high" | "medium" | "low";
    pace_wpm?: number;
    accept_signed_manifests_only?: boolean;
    [key: string]: unknown;
}

export interface SubscriptionAccepted {
    type: "subscription.accepted";
    subscription_id: string;
    aaep_version: string;
    producer: Producer;
    honored_capabilities: Capabilities;
    signed_manifest?: string;
}

export type RejectReason =
    | "version_unsupported"
    | "manifest_signature_required"
    | "capabilities_incompatible"
    | "rate_limit"
    | "authentication_required"
    | "authorization_denied"
    | "transport_unavailable"
    | "unknown";

export interface SubscriptionRejected {
    type: "subscription.rejected";
    reason_code: RejectReason;
    reason_message: string;
    retry_after_seconds?: number;
}


// === Reply messages (Level 2) ===

export interface ConfirmationReply {
    type: "confirmation.reply";
    reply_token: string;
    decision: Decision;
    subscription_id?: string;
    decided_by?: string;
    timestamp: string;
    decision_reason?: string;
}

export interface ClarificationReply {
    type: "clarification.reply";
    reply_token: string;
    response: unknown;
    subscription_id?: string;
    decided_by?: string;
    timestamp: string;
}


// === Type guards ===

export function isSessionEvent(
    event: AAEPEvent,
): event is SessionStartedEvent | SessionCompletedEvent
    | SessionErroredEvent | SessionCancelledEvent {
    return event.type.startsWith("aaep:agent.session.");
}

export function isToolEvent(
    event: AAEPEvent,
): event is ToolInvokedEvent | ToolCompletedEvent {
    return event.type === "aaep:agent.tool.invoked"
        || event.type === "aaep:agent.tool.completed";
}

export function isAwaitingEvent(
    event: AAEPEvent,
): event is AwaitingConfirmationEvent | AwaitingClarificationEvent {
    return event.type.startsWith("aaep:agent.awaiting.");
}

export function isCriticalEvent(event: AAEPEvent): boolean {
    return event.urgency === "critical";
}


// === Constants ===

export const AAEP_CONTEXT_URL = "https://aaep-protocol.org/context/v1";
export const AAEP_VERSION = "1.0.0";

export const CRITICAL_URGENCY_EVENT_TYPES = new Set([
    "aaep:agent.session.errored",
    "aaep:agent.awaiting.confirmation",
    "aaep:agent.awaiting.clarification",
    "aaep:agent.handoff.requested",
] as const);

export const HIGH_RISK_TOOL_NAMES = new Set([
    "send_email",
    "transfer_funds",
    "delete_record",
    "delete_file",
    "publish_post",
    "make_payment",
    "execute_trade",
    "send_sms",
    "send_message",
] as const);
