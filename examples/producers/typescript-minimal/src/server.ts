#!/usr/bin/env node
/**
 * HTTP/SSE server wrapping the TypeScript AgentLoop for conformance testing.
 *
 * Endpoints (identical to the Python example servers):
 *     POST /sessions   - Start a new session
 *     GET  /events     - SSE event stream
 *     POST /messages   - Reply messages (confirmation, clarification)
 *     GET  /healthz    - Health check
 *
 * Run with:
 *     npm run server                  (auto-restart via tsx)
 *     node dist/server.js             (after `npm run build`)
 *
 * Then test with:
 *     aaep-conformance producer --endpoint http://localhost:8084 --level 2
 *
 * Cross-language conformance: the same Python conformance suite verifies
 * this TypeScript server. Pass Level 2 here AND in the Python examples
 * = AAEP is language-independent in practice, not just in theory.
 */

import { createServer, IncomingMessage, ServerResponse } from "node:http";
import { AAEPEmitter } from "./emitter.js";
import { AgentLoop } from "./agent.js";
import type { AAEPEvent } from "./types.js";


// === Event broadcaster ===

class EventBroadcaster {
    private readonly subscribers: Set<ServerResponse> = new Set();
    private readonly buffer: AAEPEvent[] = [];
    private readonly maxBuffer = 1000;

    publish(event: AAEPEvent): void {
        this.buffer.push(event);
        if (this.buffer.length > this.maxBuffer) {
            // Critical event bypass: never drop critical events on overflow
            const dropIndex = this.buffer.findIndex((e) => e.urgency !== "critical");
            if (dropIndex >= 0) {
                this.buffer.splice(dropIndex, 1);
            } else {
                this.buffer.shift();  // all critical; reluctantly drop oldest
            }
        }

        const data = `data: ${JSON.stringify(event)}\n\n`;
        for (const res of this.subscribers) {
            try {
                res.write(data);
            } catch {
                this.subscribers.delete(res);
            }
        }
    }

    addSubscriber(res: ServerResponse): void {
        this.subscribers.add(res);
        // Replay buffer to new subscribers
        for (const event of this.buffer) {
            try {
                res.write(`data: ${JSON.stringify(event)}\n\n`);
            } catch {
                this.subscribers.delete(res);
                return;
            }
        }
    }

    removeSubscriber(res: ServerResponse): void {
        this.subscribers.delete(res);
    }
}


// === Request body parsing ===

async function readJsonBody(req: IncomingMessage): Promise<unknown> {
    return new Promise((resolve, reject) => {
        const chunks: Buffer[] = [];
        req.on("data", (chunk: Buffer) => chunks.push(chunk));
        req.on("end", () => {
            try {
                const text = Buffer.concat(chunks).toString("utf-8");
                resolve(text ? JSON.parse(text) : {});
            } catch (err) {
                reject(err);
            }
        });
        req.on("error", reject);
    });
}


// === CORS headers ===

function corsHeaders(): Record<string, string> {
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
    };
}


// === Main ===

async function main(): Promise<void> {
    const port = Number(process.env.PORT ?? 8084);
    const host = process.env.HOST ?? "127.0.0.1";

    const broadcaster = new EventBroadcaster();
    const emitter = new AAEPEmitter({
        sendEvent: (event) => broadcaster.publish(event),
        agentId: "aaep-typescript-server",
        agentName: "AAEP TypeScript Test Server",
        model: "mock-model",
    });
    const agent = new AgentLoop({ emitter });

    const server = createServer(async (req, res) => {
        // CORS preflight
        if (req.method === "OPTIONS") {
            res.writeHead(204, corsHeaders());
            res.end();
            return;
        }

        const url = req.url ?? "/";

        try {
            // GET /healthz
            if (req.method === "GET" && url === "/healthz") {
                res.writeHead(200, {
                    ...corsHeaders(),
                    "Content-Type": "application/json",
                });
                res.end(JSON.stringify({
                    status: "ok",
                    aaep_version: "1.0.0",
                    implementation: "typescript-minimal",
                }));
                return;
            }

            // GET /events (SSE stream)
            if (req.method === "GET" && url === "/events") {
                res.writeHead(200, {
                    ...corsHeaders(),
                    "Content-Type": "text/event-stream",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                });
                broadcaster.addSubscriber(res);
                req.on("close", () => broadcaster.removeSubscriber(res));
                return;
            }

            // POST /sessions
            if (req.method === "POST" && url === "/sessions") {
                const body = (await readJsonBody(req)) as {
                    user_message?: unknown;
                    user_id?: unknown;
                };

                if (typeof body.user_message !== "string" || !body.user_message.trim()) {
                    res.writeHead(400, {
                        ...corsHeaders(),
                        "Content-Type": "application/json",
                    });
                    res.end(JSON.stringify({ error: "user_message must be a non-empty string" }));
                    return;
                }

                // Schedule the agent run as a background task
                agent.run(body.user_message, {
                    userId: typeof body.user_id === "string" ? body.user_id : undefined,
                }).catch((err) => {
                    console.error("Session failed:", err);
                });

                // Small delay to let the session.started event be queued
                await new Promise((resolve) => setTimeout(resolve, 50));

                res.writeHead(202, {
                    ...corsHeaders(),
                    "Content-Type": "application/json",
                });
                res.end(JSON.stringify({
                    status: "started",
                    user_message: body.user_message,
                }));
                return;
            }

            // POST /messages
            if (req.method === "POST" && url === "/messages") {
                const body = (await readJsonBody(req)) as Record<string, unknown>;
                const replyToken = body.reply_token;

                if (typeof replyToken !== "string" || !replyToken) {
                    res.writeHead(400, {
                        ...corsHeaders(),
                        "Content-Type": "application/json",
                    });
                    res.end(JSON.stringify({ error: "reply_token is required" }));
                    return;
                }

                const msgType = body.type;

                if (msgType === "confirmation.reply") {
                    const decision = body.decision;
                    if (decision !== "accept" && decision !== "reject") {
                        res.writeHead(400, {
                            ...corsHeaders(),
                            "Content-Type": "application/json",
                        });
                        res.end(JSON.stringify({ error: "decision must be accept or reject" }));
                        return;
                    }
                    emitter.submitReply(replyToken, decision);
                    res.writeHead(200, {
                        ...corsHeaders(),
                        "Content-Type": "application/json",
                    });
                    res.end(JSON.stringify({ status: "received" }));
                    return;
                }

                if (msgType === "clarification.reply") {
                    const response = body.response;
                    if (response === undefined) {
                        res.writeHead(400, {
                            ...corsHeaders(),
                            "Content-Type": "application/json",
                        });
                        res.end(JSON.stringify({ error: "response field required" }));
                        return;
                    }
                    emitter.submitReply(replyToken, String(response));
                    res.writeHead(200, {
                        ...corsHeaders(),
                        "Content-Type": "application/json",
                    });
                    res.end(JSON.stringify({ status: "received" }));
                    return;
                }

                res.writeHead(400, {
                    ...corsHeaders(),
                    "Content-Type": "application/json",
                });
                res.end(JSON.stringify({ error: `unsupported message type: ${String(msgType)}` }));
                return;
            }

            // 404
            res.writeHead(404, {
                ...corsHeaders(),
                "Content-Type": "application/json",
            });
            res.end(JSON.stringify({ error: "Not found" }));

        } catch (error: unknown) {
            const err = error instanceof Error ? error : new Error(String(error));
            console.error("Request handler error:", err);
            res.writeHead(500, {
                ...corsHeaders(),
                "Content-Type": "application/json",
            });
            res.end(JSON.stringify({ error: err.message }));
        }
    });

    server.listen(port, host, () => {
        console.log(`Starting AAEP TypeScript server on http://${host}:${port}`);
        console.log(`Test with: aaep-conformance producer --endpoint http://${host}:${port} --level 2`);
    });

    // Graceful shutdown
    process.on("SIGINT", () => {
        console.log("\nShutting down...");
        server.close(() => process.exit(0));
    });
}


// === Entry point ===

main().catch((err) => {
    console.error("Server failed:", err);
    process.exit(1);
});
