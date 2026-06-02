/**
 * Tests for AAEPEmitter and StreamCoalescer.
 *
 * Verifies the TypeScript implementation produces valid AAEP events with
 * the same safety guarantees as the Python reference. Run with:
 *     npm test
 */

import { describe, it, expect, beforeEach } from "vitest";
import { AAEPEmitter, makeId, classifyRisk, safeArgsSummary } from "../src/emitter.js";
import { StreamCoalescer } from "../src/coalescer.js";
import type { AAEPEvent } from "../src/types.js";


// === Test helpers ===

function buildEmitter(): { emitter: AAEPEmitter; events: AAEPEvent[] } {
    const events: AAEPEvent[] = [];
    const emitter = new AAEPEmitter({
        sendEvent: (event) => { events.push(event); },
        agentId: "test-agent",
        agentName: "Test Agent",
        model: "test-model",
    });
    return { emitter, events };
}

function eventsOfType<T extends AAEPEvent>(events: AAEPEvent[], type: string): T[] {
    return events.filter((e) => e.type === type) as T[];
}


// === ID generation ===

describe("makeId", () => {
    it("produces correctly formatted IDs", () => {
        const id = makeId("evt");
        expect(id).toMatch(/^evt_[a-f0-9]{16}$/);
    });

    it("rejects invalid prefixes", () => {
        expect(() => makeId("EVT")).toThrow(/lowercase letters/);
        expect(() => makeId("evt-x")).toThrow(/lowercase letters/);
    });

    it("generates unique IDs", () => {
        const ids = new Set();
        for (let i = 0; i < 1000; i++) {
            ids.add(makeId("sess"));
        }
        expect(ids.size).toBe(1000);
    });
});


// === Risk classification ===

describe("classifyRisk", () => {
    it("detects high-risk tools", () => {
        expect(classifyRisk("send_email").riskLevel).toBe("high");
        expect(classifyRisk("send_email").irreversible).toBe(true);
        expect(classifyRisk("transfer_funds").riskLevel).toBe("high");
        expect(classifyRisk("delete_record").irreversible).toBe(true);
    });

    it("defaults to low-risk for unknown tools", () => {
        expect(classifyRisk("fetch_data").riskLevel).toBe("low");
        expect(classifyRisk("search_records").irreversible).toBe(false);
    });
});


// === Secret redaction ===

describe("safeArgsSummary", () => {
    it("redacts password fields", () => {
        const result = safeArgsSummary({ username: "alice", password: "secret123" });
        expect(result).toContain("username=alice");
        expect(result).toContain("password=[redacted]");
        expect(result).not.toContain("secret123");
    });

    it("redacts other secret-like fields", () => {
        const result = safeArgsSummary({
            api_key: "sk-xyz",
            auth_token: "bearer-zzz",
            credential: "private",
        });
        expect(result).not.toContain("sk-xyz");
        expect(result).not.toContain("bearer-zzz");
        expect(result).not.toContain("private");
    });
});


// === Session lifecycle ===

describe("AAEPEmitter session lifecycle", () => {
    let emitter: AAEPEmitter;
    let events: AAEPEvent[];

    beforeEach(() => {
        ({ emitter, events } = buildEmitter());
    });

    it("startSession emits session.started", () => {
        const sessionId = emitter.startSession({
            summaryNormal: "Test session",
            requestText: "Hello",
        });
        expect(sessionId).toMatch(/^sess_/);
        const started = eventsOfType(events, "aaep:agent.session.started");
        expect(started.length).toBe(1);
        expect(started[0]?.summary_normal).toBe("Test session");
        expect(started[0]?.urgency).toBe("normal");
    });

    it("completeSession emits session.completed", () => {
        const sessionId = emitter.startSession({ summaryNormal: "Test" });
        emitter.completeSession({
            sessionId,
            summaryNormal: "Done",
            durationMs: 100,
            toolInvocationsCount: 2,
        });
        const completed = eventsOfType(events, "aaep:agent.session.completed");
        expect(completed.length).toBe(1);
        expect(completed[0]?.urgency).toBe("normal");
    });

    it("errorSession emits with critical urgency", () => {
        const sessionId = emitter.startSession({ summaryNormal: "Test" });
        emitter.errorSession({
            sessionId,
            errorCategory: "network",
            summaryNormal: "Network failed",
            recoverable: true,
        });
        const errored = eventsOfType(events, "aaep:agent.session.errored");
        expect(errored.length).toBe(1);
        expect(errored[0]?.urgency).toBe("critical");  // MUST per spec
        expect(errored[0]?.error_category).toBe("network");
    });

    it("sequence numbers increment per session", () => {
        const sid = emitter.startSession({ summaryNormal: "Test" });
        emitter.stateChanged({ sessionId: sid, fromState: "idle", toState: "thinking", summaryNormal: "Thinking" });
        emitter.stateChanged({ sessionId: sid, fromState: "thinking", toState: "writing_output", summaryNormal: "Writing" });

        const seqs = events.filter((e) => e.session_id === sid).map((e) => e.sequence_number);
        expect(seqs).toEqual([0, 1, 2]);
    });
});


// === Safety rule enforcement ===

describe("AAEPEmitter safety rules", () => {
    it("throws on irreversible+high with default_decision=accept", () => {
        const { emitter } = buildEmitter();
        const sid = emitter.startSession({ summaryNormal: "Test" });
        expect(() => emitter.awaitConfirmation({
            sessionId: sid,
            action: "Delete everything",
            consequence: "Cannot undo",
            riskLevel: "high",
            irreversible: true,
            defaultDecision: "accept",  // SAFETY VIOLATION
        })).toThrow(/default_decision/);
    });

    it("allows irreversible+high with default_decision=reject", () => {
        const { emitter, events } = buildEmitter();
        const sid = emitter.startSession({ summaryNormal: "Test" });
        const token = emitter.awaitConfirmation({
            sessionId: sid,
            action: "Send email",
            consequence: "Cannot undo",
            riskLevel: "high",
            irreversible: true,
            defaultDecision: "reject",  // CORRECT
        });
        expect(token).toMatch(/^rpl_/);
        const conf = eventsOfType(events, "aaep:agent.awaiting.confirmation");
        expect(conf[0]?.urgency).toBe("critical");
        expect(conf[0]?.default_decision).toBe("reject");
    });

    it("submitReply resolves the waiting promise", async () => {
        const { emitter } = buildEmitter();
        const sid = emitter.startSession({ summaryNormal: "Test" });
        const token = emitter.awaitConfirmation({
            sessionId: sid,
            action: "Continue",
            consequence: "Will proceed",
            riskLevel: "low",
            irreversible: false,
        });
        const decisionPromise = emitter.waitForDecision(token);
        emitter.submitReply(token, "accept");
        await expect(decisionPromise).resolves.toBe("accept");
    });
});


// === StreamCoalescer ===

describe("StreamCoalescer", () => {
    it("emits at sentence boundaries", () => {
        const { emitter, events } = buildEmitter();
        const sid = emitter.startSession({ summaryNormal: "Test" });
        const coalescer = new StreamCoalescer({
            emitter,
            sessionId: sid,
            outputId: "out_test",
            coalesceAt: "sentence",
        });

        coalescer.addToken("Hello ");
        coalescer.addToken("world. ");  // sentence boundary -> emit
        coalescer.addToken("Goodbye.");
        coalescer.finish();

        const streaming = eventsOfType(events, "aaep:agent.output.streaming");
        expect(streaming.length).toBeGreaterThanOrEqual(1);
        expect(streaming[streaming.length - 1]?.complete).toBe(true);

        // Reconstructed text matches input
        const reconstructed = streaming.map((e: any) => e.chunk).join("");
        expect(reconstructed).toBe("Hello world. Goodbye.");
    });

    it("final event has coalesce_hint='completion'", () => {
        const { emitter, events } = buildEmitter();
        const sid = emitter.startSession({ summaryNormal: "Test" });
        const coalescer = new StreamCoalescer({
            emitter,
            sessionId: sid,
            outputId: "out_test",
            coalesceAt: "word",
        });
        coalescer.addToken("Hello world.");
        coalescer.finish();

        const streaming = eventsOfType(events, "aaep:agent.output.streaming");
        const last = streaming[streaming.length - 1] as any;
        expect(last?.complete).toBe(true);
        expect(last?.coalesce_hint).toBe("completion");
    });

    it("finish is idempotent", () => {
        const { emitter } = buildEmitter();
        const sid = emitter.startSession({ summaryNormal: "Test" });
        const coalescer = new StreamCoalescer({
            emitter,
            sessionId: sid,
            outputId: "out_test",
        });
        coalescer.addToken("Test.");
        coalescer.finish();
        expect(() => coalescer.finish()).not.toThrow();
    });
});


// === Envelope smoke test (mirrors conformance suite) ===

describe("Conformance: every event has envelope fields", () => {
    it("all required envelope fields present on every event", () => {
        const { emitter, events } = buildEmitter();
        const sid = emitter.startSession({ summaryNormal: "Test" });
        emitter.stateChanged({ sessionId: sid, fromState: "idle", toState: "thinking", summaryNormal: "x" });
        emitter.toolInvoked({
            sessionId: sid,
            tool: "test_tool",
            toolCallId: makeId("call"),
            argsSummary: "x=1",
        });
        emitter.completeSession({ sessionId: sid, summaryNormal: "Done" });

        const required = ["@context", "type", "event_id", "session_id", "timestamp", "producer", "urgency"];
        for (const event of events) {
            for (const field of required) {
                expect(event).toHaveProperty(field);
            }
        }
    });
});
