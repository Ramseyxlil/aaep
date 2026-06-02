/**
 * AAEP TypeScript Producer — public API.
 *
 * Reference implementation of an AAEP producer in TypeScript / Node.js.
 * Demonstrates the manual loop pattern with full safety machinery.
 *
 * @example
 * ```typescript
 * import { AAEPEmitter, AgentLoop, makeId } from 'aaep-typescript-producer';
 *
 * const emitter = new AAEPEmitter({
 *     sendEvent: (event) => console.log(JSON.stringify(event)),
 *     agentId: 'my-agent',
 * });
 *
 * const agent = new AgentLoop(emitter);
 * await agent.run('Tell me about retirement planning.');
 * ```
 *
 * See README.md for full usage and design notes.
 */

export const VERSION = "1.0.0";
export const AAEP_SPEC_VERSION = "1.0.0";

// Core emitter and helpers
export {
    AAEPEmitter,
    classifyErrorCategory,
    classifyRisk,
    makeId,
    nowIso,
    safeArgsSummary,
    type AAEPEmitterOptions,
} from "./emitter.js";

// Streaming coalescer
export { StreamCoalescer, type StreamCoalescerOptions } from "./coalescer.js";

// Agent loop
export { AgentLoop, type ToolDescriptor, type AgentLoopOptions } from "./agent.js";

// All type definitions
export * from "./types.js";
