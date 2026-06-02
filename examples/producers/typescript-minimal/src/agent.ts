/**
 * AgentLoop — TypeScript port of the Python python-minimal AgentLoop.
 *
 * Production-grade reference of the manual loop pattern with a mock LLM
 * for portability. Replace `_MockLLM` with a real client (Anthropic, OpenAI,
 * Azure OpenAI, etc.) for production use.
 */

import {
    AAEPEmitter,
    classifyErrorCategory,
    classifyRisk,
    makeId,
    safeArgsSummary,
} from "./emitter.js";
import { StreamCoalescer } from "./coalescer.js";


// === Tool descriptor ===

export interface ToolDescriptor {
    name: string;
    description: string;
    handler: (args: Record<string, unknown>) => unknown | Promise<unknown>;
    riskLevel?: "low" | "medium" | "high";
    irreversible?: boolean;
}


// === Agent loop options ===

export interface AgentLoopOptions {
    emitter: AAEPEmitter;
    tools?: ToolDescriptor[];
}


// === The agent loop ===

export class AgentLoop {
    private readonly emitter: AAEPEmitter;
    private readonly tools: Map<string, ToolDescriptor>;
    private readonly llm: _MockLLM;
    private readonly activeSessions: Map<string, AbortController> = new Map();

    constructor(options: AgentLoopOptions) {
        this.emitter = options.emitter;
        this.tools = new Map(
            (options.tools ?? this.defaultTools()).map((t) => [t.name, t]),
        );
        this.llm = new _MockLLM();
    }

    /**
     * Run a complete agent session. Returns the session_id.
     *
     * The session is fully owned by this method: it emits all lifecycle
     * events including the terminal event, even on exception.
     */
    async run(userMessage: string, opts: { userId?: string } = {}): Promise<string> {
        const sessionId = this.emitter.startSession({
            summaryNormal: `Processing: ${userMessage.slice(0, 80)}`,
            requestText: userMessage,
            requestedBy: opts.userId ? `user:${opts.userId}` : undefined,
            toolsAvailable: Array.from(this.tools.keys()),
        });

        const abortController = new AbortController();
        this.activeSessions.set(sessionId, abortController);

        try {
            await this.runLoop(sessionId, userMessage, abortController.signal);
        } finally {
            this.activeSessions.delete(sessionId);
        }

        return sessionId;
    }

    /** Cancel an in-progress session. Returns true if cancellation was issued. */
    cancel(sessionId: string): boolean {
        const controller = this.activeSessions.get(sessionId);
        if (!controller) return false;
        controller.abort();
        return true;
    }

    // === Internal: the thinking-and-acting loop ===

    private async runLoop(
        sessionId: string,
        userMessage: string,
        abortSignal: AbortSignal,
    ): Promise<void> {
        const startTime = Date.now();
        let currentState = "idle";
        let toolCount = 0;
        let coalescer: StreamCoalescer | null = null;
        const messages: Array<{ role: string; content: unknown }> = [
            { role: "user", content: userMessage },
        ];

        try {
            while (true) {
                if (abortSignal.aborted) {
                    throw new DOMException("Cancelled", "AbortError");
                }

                // Transition to thinking
                if (currentState !== "thinking") {
                    this.emitter.stateChanged({
                        sessionId,
                        fromState: currentState,
                        toState: "thinking",
                        summaryNormal: "Considering the request.",
                    });
                    currentState = "thinking";
                }

                const response = await this.llm.complete(messages, Array.from(this.tools.values()));

                if (response.toolCalls.length > 0) {
                    // Tools requested
                    this.emitter.stateChanged({
                        sessionId,
                        fromState: "thinking",
                        toState: "calling_tool",
                        summaryNormal: `Preparing to call ${response.toolCalls.length} tool(s).`,
                    });
                    currentState = "calling_tool";

                    const toolResults: Array<{ tool_call_id: string; result: unknown }> = [];
                    for (const toolCall of response.toolCalls) {
                        const result = await this.executeTool(sessionId, toolCall);
                        toolCount++;
                        toolResults.push({ tool_call_id: toolCall.id, result });
                    }

                    messages.push({
                        role: "assistant",
                        content: response.text,
                    });
                    messages.push({
                        role: "tool_results",
                        content: toolResults,
                    });
                    continue;
                }

                // No more tools; stream output
                this.emitter.stateChanged({
                    sessionId,
                    fromState: "thinking",
                    toState: "writing_output",
                    summaryNormal: "Generating response.",
                });
                currentState = "writing_output";

                const outputId = makeId("out");
                coalescer = new StreamCoalescer({
                    emitter: this.emitter,
                    sessionId,
                    outputId,
                    coalesceAt: "sentence",
                });

                for await (const chunk of this.llm.stream(response)) {
                    if (abortSignal.aborted) {
                        throw new DOMException("Cancelled", "AbortError");
                    }
                    coalescer.addToken(chunk);
                }
                coalescer.finish();
                coalescer = null;
                break;
            }

            // Success
            const durationMs = Date.now() - startTime;
            this.emitter.completeSession({
                sessionId,
                summaryNormal: "Response complete.",
                durationMs,
                toolInvocationsCount: toolCount,
            });

        } catch (error: unknown) {
            if (coalescer) {
                try {
                    coalescer.finish();
                } catch {
                    // Already finished or in bad state; swallow
                }
            }

            if (error instanceof DOMException && error.name === "AbortError") {
                this.emitter.cancelledSession({
                    sessionId,
                    cancelledBy: "system",
                    summaryNormal: "Session cancelled.",
                });
            } else {
                const err = error instanceof Error ? error : new Error(String(error));
                this.emitter.errorSession({
                    sessionId,
                    errorCategory: classifyErrorCategory(err),
                    summaryNormal: `Error: ${err.name}`,
                    errorMessage: err.message.slice(0, 1000),
                    recoverable: err.name === "TimeoutError" || err.message.toLowerCase().includes("network"),
                });
            }
            throw error;
        }
    }

    // === Internal: execute one tool with full AAEP cycle ===

    private async executeTool(
        sessionId: string,
        toolCall: { id: string; name: string; arguments: Record<string, unknown> },
    ): Promise<unknown> {
        const descriptor = this.tools.get(toolCall.name);
        const aaepCallId = makeId("call");
        const args = toolCall.arguments;

        const { riskLevel, irreversible } = descriptor
            ? {
                  riskLevel: descriptor.riskLevel ?? "low",
                  irreversible: descriptor.irreversible ?? false,
              }
            : classifyRisk(toolCall.name);

        // Emit tool.invoked BEFORE side effect
        this.emitter.toolInvoked({
            sessionId,
            tool: toolCall.name,
            toolCallId: aaepCallId,
            argsSummary: safeArgsSummary(args),
            riskLevel,
            irreversible,
            summaryNormal: `Calling ${toolCall.name}.`,
        });

        // Confirmation gating for irreversible or high-risk
        if (irreversible || riskLevel === "high") {
            const replyToken = this.emitter.awaitConfirmation({
                sessionId,
                action: `Call ${toolCall.name} with: ${safeArgsSummary(args, 200)}`,
                consequence: irreversible
                    ? "This action cannot be easily undone."
                    : "This action will be executed.",
                timeoutSeconds: 300,
                defaultDecision: "reject",
                riskLevel,
                irreversible,
                summaryNormal: `Confirm: call ${toolCall.name}?`,
            });

            const decision = await this.emitter.waitForDecision(replyToken);

            if (decision !== "accept") {
                this.emitter.toolCompleted({
                    sessionId,
                    tool: toolCall.name,
                    toolCallId: aaepCallId,
                    status: "error",
                    errorMessage: "User declined to authorize this action.",
                });
                return `<user declined to call ${toolCall.name}>`;
            }
        }

        // Execute the tool
        try {
            if (!descriptor) {
                throw new Error(`No handler for tool ${JSON.stringify(toolCall.name)}`);
            }
            const result = await descriptor.handler(args);

            this.emitter.toolCompleted({
                sessionId,
                tool: toolCall.name,
                toolCallId: aaepCallId,
                status: "success",
                summaryNormal: String(result).slice(0, 200),
            });
            return result;

        } catch (error: unknown) {
            const err = error instanceof Error ? error : new Error(String(error));
            const isTimeout = err.name === "TimeoutError" || err.message.includes("timeout");
            this.emitter.toolCompleted({
                sessionId,
                tool: toolCall.name,
                toolCallId: aaepCallId,
                status: isTimeout ? "timeout" : "error",
                errorMessage: err.message.slice(0, 1000),
            });
            throw error;
        }
    }

    // === Default mock tools ===

    private defaultTools(): ToolDescriptor[] {
        return [
            {
                name: "fetch_balance",
                description: "Look up an account balance",
                handler: async (args) => {
                    await sleep(300);
                    const account = (args.account as string) ?? "checking";
                    const balances: Record<string, string> = {
                        checking: "$3,247.18",
                        savings: "$12,891.40",
                    };
                    return balances[account] ?? "$0.00";
                },
                riskLevel: "low",
                irreversible: false,
            },
            {
                name: "send_email",
                description: "Send an email",
                handler: async (args) => {
                    await sleep(500);
                    return `Email sent to ${args.to ?? "recipient"}`;
                },
                riskLevel: "high",
                irreversible: true,
            },
            {
                name: "transfer_funds",
                description: "Move money between accounts",
                handler: async (args) => {
                    await sleep(700);
                    return `Transferred $${args.amount} from ${args.from} to ${args.to}`;
                },
                riskLevel: "high",
                irreversible: true,
            },
        ];
    }
}


// === Mock LLM ===

interface MockLLMResponse {
    text: string;
    toolCalls: Array<{ id: string; name: string; arguments: Record<string, unknown> }>;
}


class _MockLLM {
    private calls = 0;

    async complete(
        messages: Array<{ role: string; content: unknown }>,
        _tools: ToolDescriptor[],
    ): Promise<MockLLMResponse> {
        await sleep(400);
        this.calls++;

        const lastMsg = messages[messages.length - 1];
        const lastText = typeof lastMsg?.content === "string" ? lastMsg.content : "";
        const lower = lastText.toLowerCase();

        // On the first call, sometimes call a tool to exercise the flow
        if (this.calls === 1) {
            if (lower.includes("balance")) {
                return {
                    text: "Let me check that for you.",
                    toolCalls: [{
                        id: `tool_${this.calls}`,
                        name: "fetch_balance",
                        arguments: { account: "checking" },
                    }],
                };
            }
            if (lower.includes("email")) {
                return {
                    text: "I'll send that email.",
                    toolCalls: [{
                        id: `tool_${this.calls}`,
                        name: "send_email",
                        arguments: {
                            to: "recipient@example.com",
                            subject: "Re: your request",
                        },
                    }],
                };
            }
        }

        // No more tools; return final output (caller will stream the text)
        return { text: "", toolCalls: [] };
    }

    async *stream(_response: MockLLMResponse): AsyncIterable<string> {
        const chunks = [
            "Here's what I found. ",
            "Your account is in good standing ",
            "with no pending issues. ",
            "Is there anything else ",
            "I can help you with?",
        ];
        for (const chunk of chunks) {
            await sleep(50);
            yield chunk;
        }
    }
}


// === Helpers ===

function sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
}
