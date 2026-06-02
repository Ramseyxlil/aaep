/**
 * StreamCoalescer — TypeScript port of the Python StreamCoalescer.
 *
 * Buffers streaming tokens and emits agent.output.streaming events at
 * coalesce boundaries (default: sentence boundaries). The boundary
 * detection regexes match the Python implementation exactly.
 *
 * Usage:
 *   const coalescer = new StreamCoalescer({
 *       emitter,
 *       sessionId: "sess_x",
 *       outputId: "out_y",
 *       coalesceAt: "sentence",
 *   });
 *   coalescer.addToken("Hello ");
 *   coalescer.addToken("world. ");      // sentence boundary -> emit
 *   coalescer.addToken("Goodbye.");
 *   coalescer.finish();                 // final emit with complete=true
 */

import type { CoalesceHint } from "./types.js";
import { AAEPEmitter } from "./emitter.js";


export interface StreamCoalescerOptions {
    emitter: AAEPEmitter;
    sessionId: string;
    outputId: string;
    coalesceAt?: CoalesceHint;
    language?: string;
}


export class StreamCoalescer {
    private readonly emitter: AAEPEmitter;
    private readonly sessionId: string;
    private readonly outputId: string;
    private readonly coalesceAt: CoalesceHint;
    private readonly language: string | undefined;

    private buffer = "";
    private position = 0;
    private finished = false;

    constructor(options: StreamCoalescerOptions) {
        this.emitter = options.emitter;
        this.sessionId = options.sessionId;
        this.outputId = options.outputId;
        this.coalesceAt = options.coalesceAt ?? "sentence";
        this.language = options.language;
    }

    /**
     * Add a token to the buffer. May emit one or more events if coalesce
     * boundaries are crossed by the addition.
     */
    addToken(token: string): void {
        if (this.finished) {
            throw new Error("Cannot add tokens to a finished coalescer");
        }
        this.buffer += token;
        this.flushAtBoundary();
    }

    /**
     * Flush any remaining buffer and emit the final completion event
     * (complete=true). Idempotent; safe to call multiple times.
     */
    finish(): void {
        if (this.finished) return;

        this.emitChunk(this.buffer, /* complete = */ true);
        this.buffer = "";
        this.finished = true;
    }

    /** Inspect the current buffered text (for tests). */
    get bufferedText(): string {
        return this.buffer;
    }

    /** Whether finish() has been called. */
    get isFinished(): boolean {
        return this.finished;
    }

    // === Internals ===

    private flushAtBoundary(): void {
        // 'completion' coalescing means "flush only on finish()"
        if (this.coalesceAt === "completion") return;
        if (this.coalesceAt === "none") {
            // Emit every token as a separate event
            const text = this.buffer;
            this.buffer = "";
            this.emitChunk(text, /* complete = */ false);
            return;
        }

        const boundaries = this.findBoundaries();
        for (const boundaryEnd of boundaries) {
            const chunk = this.buffer.slice(0, boundaryEnd);
            this.buffer = this.buffer.slice(boundaryEnd);
            this.emitChunk(chunk, /* complete = */ false);
        }
    }

    private findBoundaries(): number[] {
        const boundaries: number[] = [];
        let regex: RegExp;

        if (this.coalesceAt === "word") {
            // End of word: non-space followed by whitespace
            regex = /\S+\s+/g;
        } else if (this.coalesceAt === "sentence") {
            // End of sentence: ., !, or ? followed by whitespace or end
            regex = /[.!?](\s|$)/g;
        } else if (this.coalesceAt === "paragraph") {
            // Paragraph break: double newline
            regex = /\n\n/g;
        } else {
            return [];
        }

        let match: RegExpExecArray | null;
        while ((match = regex.exec(this.buffer)) !== null) {
            boundaries.push(match.index + match[0].length);
        }
        return boundaries;
    }

    private emitChunk(chunk: string, complete: boolean): void {
        if (!chunk && !complete) return;

        this.emitter.outputStreaming({
            sessionId: this.sessionId,
            outputId: this.outputId,
            chunk,
            position: this.position,
            complete,
            coalesceHint: complete ? "completion" : this.coalesceAt,
            ...(this.language && { language: this.language }),
        });

        this.position += chunk.length;
    }
}
