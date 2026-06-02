/**
 * AAEPEmitter — TypeScript port of the python-minimal emitter.
 *
 * Same architecture as Python: one method per AAEP event type, transport
 * via a configurable sendEvent callback, Promise-based confirmation flow.
 * The safety machinery (irreversible+high MUST default reject, secret
 * redaction, critical urgency on errored events) matches the Python emitter
 * one-for-one.
 *
 * This module has zero runtime dependencies beyond Node.js stdlib. The
 * `crypto` module is used for ID generation; everything else is built-in
 * language features.
 */

import { randomBytes } from "node:crypto";
import type {
    AAEPEvent,

    Decision,
    ErrorCategory,
    Producer,
    RiskLevel,
    ToolStatus,
} from "./types.js";
import {
    AAEP_CONTEXT_URL,
    AAEP_VERSION,
} from "./types.js";


// === ID generation ===

const ID_PREFIX_PATTERN = /^[a-z]+$/;

export function makeId(prefix: string): string {
    if (!ID_PREFIX_PATTERN.test(prefix)) {
        throw new Error(
            `ID prefix must be lowercase letters only, got ${JSON.stringify(prefix)}`,
        );
    }
    return `${prefix}_${randomBytes(8).toString("hex")}`;
}


// === RFC 3339 timestamp ===

export function nowIso(): string {
    const now = new Date();
    const ms = String(now.getUTCMilliseconds()).padStart(3, "0");
    return now.toISOString().replace(/\.\d{3}Z$/, `.${ms}Z`);
}


// === Error classification ===

export function classifyErrorCategory(error: unknown): ErrorCategory {
    if (!(error instanceof Error)) {
        return "unknown";
    }
    const name = error.name;
    if (name === "TimeoutError" || name === "AbortError") return "timeout";
    if (name === "TypeError" || name === "RangeError") return "invalid_input";
    if (error.message.toLowerCase().includes("network")) return "network";
    if (error.message.toLowerCase().includes("permission")) return "authorization";
    return "unknown";
}


// === Risk classification ===

const HIGH_RISK_PATTERNS = [
    "send_email", "transfer_funds", "delete_record", "delete_file",
    "publish_post", "make_payment", "execute_trade", "send_sms",
];

export function classifyRisk(toolName: string): {
    riskLevel: RiskLevel;
    irreversible: boolean;
} {
    const lower = toolName.toLowerCase();
    for (const pattern of HIGH_RISK_PATTERNS) {
        if (lower.includes(pattern)) {
            return { riskLevel: "high", irreversible: true };
        }
    }
    return { riskLevel: "low", irreversible: false };
}


// === Safe args summary (redacts secrets) ===

const SECRET_FIELD_PATTERNS = [
    "password", "secret", "token", "key", "auth", "credential",
];

export function safeArgsSummary(
    args: Record<string, unknown>,
    maxChars = 1000,
): string {
    const parts: string[] = [];
    for (const [k, v] of Object.entries(args)) {
        const lower = k.toLowerCase();
        const isSecret = SECRET_FIELD_PATTERNS.some((p) => lower.includes(p));
        if (isSecret) {
            parts.push(`${k}=[redacted]`);
        } else {
            const vStr = String(v);
            parts.push(`${k}=${vStr.length > 80 ? vStr.slice(0, 77) + "..." : vStr}`);
        }
    }
    return parts.join(", ").slice(0, maxChars);
}


// === Emitter options ===

export interface AAEPEmitterOptions {
    sendEvent: (event: AAEPEvent) => void | Promise<void>;
    agentId?: string;
    agentVersion?: string;
    agentName?: string;
    model?: string;
}


// === The emitter ===

export class AAEPEmitter {
    private readonly sendEvent: (event: AAEPEvent) => void | Promise<void>;
    private readonly producerInfo: Producer;
    private readonly sequenceNumbers: Map<string, number> = new Map();
    private readonly replyResolvers: Map<string, (decision: string) => void> = new Map();

    constructor(options: AAEPEmitterOptions) {
        this.sendEvent = options.sendEvent;
        this.producerInfo = {
            agent_id: options.agentId ?? "aaep-typescript-producer",
            agent_version: options.agentVersion ?? "1.0.0",
            agent_name: options.agentName ?? "AAEP TypeScript Producer",
            ...(options.model ? { model: options.model } : {}),
        };
    }

    /** Read-only view of the producer info (for tests). */
    get producer(): Readonly<Producer> {
        return this.producerInfo;
    }

    // === Session lifecycle ===

    startSession(opts: {
        summaryNormal: string;
        requestText?: string;
        requestedBy?: string;
        expectedDurationMs?: number;
        toolsAvailable?: string[];
    }): string {
        const sessionId = makeId("sess");
        this.emit({
            "@context": AAEP_CONTEXT_URL,
            aaep_version: AAEP_VERSION,
            type: "aaep:agent.session.started",
            event_id: makeId("evt"),
            session_id: sessionId,
            sequence_number: this.nextSeq(sessionId),
            timestamp: nowIso(),
            producer: { ...this.producerInfo },
            urgency: "normal",
            summary_normal: opts.summaryNormal,
            ...(opts.requestText && { request_text: opts.requestText }),
            ...(opts.requestedBy && { requested_by: opts.requestedBy }),
            ...(opts.expectedDurationMs && { expected_duration_ms: opts.expectedDurationMs }),
            ...(opts.toolsAvailable && { tools_available: opts.toolsAvailable }),
        });
        return sessionId;
    }

    completeSession(opts: {
        sessionId: string;
        summaryNormal: string;
        durationMs?: number;
        toolInvocationsCount?: number;
    }): void {
        this.emit({
            "@context": AAEP_CONTEXT_URL,
            type: "aaep:agent.session.completed",
            event_id: makeId("evt"),
            session_id: opts.sessionId,
            sequence_number: this.nextSeq(opts.sessionId),
            timestamp: nowIso(),
            producer: { ...this.producerInfo },
            urgency: "normal",
            summary_normal: opts.summaryNormal,
            ...(opts.durationMs !== undefined && { duration_ms: opts.durationMs }),
            ...(opts.toolInvocationsCount !== undefined && {
                tool_invocations_count: opts.toolInvocationsCount,
            }),
        });
    }

    errorSession(opts: {
        sessionId: string;
        errorCategory: ErrorCategory;
        summaryNormal: string;
        errorMessage?: string;
        recoverable?: boolean;
        remediationHint?: string;
    }): void {
        this.emit({
            "@context": AAEP_CONTEXT_URL,
            type: "aaep:agent.session.errored",
            event_id: makeId("evt"),
            session_id: opts.sessionId,
            sequence_number: this.nextSeq(opts.sessionId),
            timestamp: nowIso(),
            producer: { ...this.producerInfo },
            urgency: "critical",  // MUST per Chapter 4 §4.1.3
            error_category: opts.errorCategory,
            summary_normal: opts.summaryNormal,
            ...(opts.errorMessage && { error_message: opts.errorMessage }),
            ...(opts.recoverable !== undefined && { recoverable: opts.recoverable }),
            ...(opts.remediationHint && { remediation_hint: opts.remediationHint }),
        });
    }

    cancelledSession(opts: {
        sessionId: string;
        cancelledBy?: "user" | "system" | "timeout" | "policy";
        summaryNormal?: string;
    }): void {
        this.emit({
            "@context": AAEP_CONTEXT_URL,
            type: "aaep:agent.session.cancelled",
            event_id: makeId("evt"),
            session_id: opts.sessionId,
            sequence_number: this.nextSeq(opts.sessionId),
            timestamp: nowIso(),
            producer: { ...this.producerInfo },
            urgency: "normal",
            cancelled_by: opts.cancelledBy ?? "system",
            summary_normal: opts.summaryNormal ?? "Session cancelled.",
        });
    }

    // === State change ===

    stateChanged(opts: {
        sessionId: string;
        fromState: string;
        toState: string;
        summaryNormal: string;
    }): void {
        this.emit({
            "@context": AAEP_CONTEXT_URL,
            type: "aaep:agent.state.changed",
            event_id: makeId("evt"),
            session_id: opts.sessionId,
            sequence_number: this.nextSeq(opts.sessionId),
            timestamp: nowIso(),
            producer: { ...this.producerInfo },
            urgency: "normal",
            from_state: opts.fromState,
            to_state: opts.toState,
            summary_normal: opts.summaryNormal,
        });
    }

    // === Tool invocation ===

    toolInvoked(opts: {
        sessionId: string;
        tool: string;
        toolCallId: string;
        argsSummary: string;
        riskLevel?: RiskLevel;
        irreversible?: boolean;
        summaryNormal?: string;
    }): void {
        this.emit({
            "@context": AAEP_CONTEXT_URL,
            type: "aaep:agent.tool.invoked",
            event_id: makeId("evt"),
            session_id: opts.sessionId,
            sequence_number: this.nextSeq(opts.sessionId),
            timestamp: nowIso(),
            producer: { ...this.producerInfo },
            urgency: "normal",
            tool: opts.tool,
            tool_call_id: opts.toolCallId,
            args_summary: opts.argsSummary,
            risk_level: opts.riskLevel ?? "low",
            irreversible: opts.irreversible ?? false,
            summary_normal: opts.summaryNormal ?? `Calling ${opts.tool}.`,
        });
    }

    toolCompleted(opts: {
        sessionId: string;
        tool: string;
        toolCallId: string;
        status: ToolStatus;
        summaryNormal?: string;
        errorMessage?: string;
    }): void {
        if (!["success", "error", "timeout"].includes(opts.status)) {
            throw new Error(
                `status must be success/error/timeout, got ${JSON.stringify(opts.status)}`,
            );
        }
        this.emit({
            "@context": AAEP_CONTEXT_URL,
            type: "aaep:agent.tool.completed",
            event_id: makeId("evt"),
            session_id: opts.sessionId,
            sequence_number: this.nextSeq(opts.sessionId),
            timestamp: nowIso(),
            producer: { ...this.producerInfo },
            urgency: "normal",
            tool: opts.tool,
            tool_call_id: opts.toolCallId,
            status: opts.status,
            summary_normal: opts.summaryNormal ?? "",
            ...(opts.errorMessage && { error_message: opts.errorMessage }),
        });
    }

    // === Streaming output ===

    outputStreaming(opts: {
        sessionId: string;
        outputId: string;
        chunk: string;
        position: number;
        complete: boolean;
        coalesceHint?: "none" | "word" | "sentence" | "paragraph" | "completion";
        language?: string;
    }): void {
        this.emit({
            "@context": AAEP_CONTEXT_URL,
            type: "aaep:agent.output.streaming",
            event_id: makeId("evt"),
            session_id: opts.sessionId,
            sequence_number: this.nextSeq(opts.sessionId),
            timestamp: nowIso(),
            producer: { ...this.producerInfo },
            urgency: "normal",
            summary_normal: "",
            chunk: opts.chunk,
            position: opts.position,
            complete: opts.complete,
            coalesce_hint: opts.coalesceHint ?? "none",
            output_id: opts.outputId,
            ...(opts.language && { language: opts.language }),
        });
    }

    // === Confirmation flow ===

    awaitConfirmation(opts: {
        sessionId: string;
        action: string;
        consequence: string;
        timeoutSeconds?: number;
        defaultDecision?: Decision;
        riskLevel?: RiskLevel;
        irreversible?: boolean;
        summaryNormal?: string;
    }): string {
        const riskLevel = opts.riskLevel ?? "low";
        const irreversible = opts.irreversible ?? false;
        const defaultDecision = opts.defaultDecision ?? "reject";

        // Runtime safety enforcement (mirrors Python emitter)
        if (
            irreversible
            && (riskLevel === "high" || riskLevel === "medium")
            && defaultDecision !== "reject"
        ) {
            throw new Error(
                `Irreversible ${riskLevel}-risk confirmations MUST have `
                + `default_decision='reject' (got '${defaultDecision}'). `
                + `This is enforced both by the schema and at runtime.`,
            );
        }

        const replyToken = makeId("rpl");
        const promise = new Promise<string>((resolve) => {
            this.replyResolvers.set(replyToken, resolve);
        });
        // Store the promise via the resolver map; expose waitForDecision separately
        (this as any)._pendingReplies = (this as any)._pendingReplies ?? new Map();
        (this as any)._pendingReplies.set(replyToken, promise);

        this.emit({
            "@context": AAEP_CONTEXT_URL,
            type: "aaep:agent.awaiting.confirmation",
            event_id: makeId("evt"),
            session_id: opts.sessionId,
            sequence_number: this.nextSeq(opts.sessionId),
            timestamp: nowIso(),
            producer: { ...this.producerInfo },
            urgency: "critical",  // MUST per Chapter 4 §4.4.1
            action: opts.action,
            consequence: opts.consequence,
            reply_token: replyToken,
            timeout_seconds: opts.timeoutSeconds ?? 300,
            default_decision: defaultDecision,
            risk_level: riskLevel,
            irreversible: irreversible,
            summary_normal: opts.summaryNormal ?? `Confirm: ${opts.action}`,
        });

        return replyToken;
    }

    submitReply(replyToken: string, decision: string): boolean {
        const resolver = this.replyResolvers.get(replyToken);
        if (!resolver) return false;
        resolver(decision);
        this.replyResolvers.delete(replyToken);
        return true;
    }

    async waitForDecision(replyToken: string): Promise<string> {
        const pending = (this as any)._pendingReplies as Map<string, Promise<string>>;
        const promise = pending?.get(replyToken);
        if (!promise) {
            throw new Error(`Unknown reply_token: ${replyToken}`);
        }
        try {
            return await promise;
        } finally {
            pending.delete(replyToken);
        }
    }

    // === Internals ===

    private nextSeq(sessionId: string): number {
        const seq = this.sequenceNumbers.get(sessionId) ?? 0;
        this.sequenceNumbers.set(sessionId, seq + 1);
        return seq;
    }

    private emit(event: AAEPEvent): void {
        const result = this.sendEvent(event);
        if (result instanceof Promise) {
            // Fire-and-forget async sender; errors are swallowed
            result.catch((err) => {
                // In production, route this to your logger
                console.error("[AAEPEmitter] sendEvent failed:", err);
            });
        }
    }
}
