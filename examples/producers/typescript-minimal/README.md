# TypeScript Minimal Producer Example

A minimal but complete AAEP producer implementation in TypeScript, designed for Node.js (18+). Demonstrates the manual loop pattern with full safety machinery and HTTP/SSE transport.

If you're building AAEP producers in the TypeScript/Node.js ecosystem — whether for browser-side agents, Electron-based AT software, or Node backend agents — this is the example to copy.

---

## What this example demonstrates

- A complete AAEP emitter implemented in idiomatic TypeScript
- Strict type definitions for every event type (matching the JSON Schemas)
- Native Node.js streams and `fetch` (no framework dependency)
- HTTP/SSE transport using Node's `http` module
- The same safety machinery as the Python examples: irreversible+high MUST default reject, secret redaction, critical urgency on errored events
- Confirmation flow with `Promise`-based blocking
- Streaming output with sentence-boundary coalescing
- All 12 core AAEP event types emitted from a typical agent session
- Conformance Level 2 compatible

---

## When to use this example

**Pick this pattern when:**
- You're building agents in Node.js, TypeScript, or modern JavaScript
- You need AAEP support in browser-side agent UIs
- You're building AT software in Electron, Tauri, or similar frameworks
- You want strict type definitions for AAEP events in your codebase

**Pick a Python example when:** your agent stack is Python.

---

## Installation

```bash
cd examples/producers/typescript-minimal
npm install
npm run build
```

Requires Node.js 18 or newer.

---

## Quick start

```typescript
import { AAEPEmitter, AgentLoop, makeId } from 'aaep-typescript-producer';

// Step 1: create an emitter with your transport
const emitter = new AAEPEmitter({
    sendEvent: (event) => {
        // Forward to subscribers (HTTP/SSE, WebSocket, etc.)
        console.log(JSON.stringify(event));
    },
    agentId: 'my-agent',
    agentName: 'My Agent',
});

// Step 2: create an agent loop
const agent = new AgentLoop(emitter);

// Step 3: run a session
const sessionId = await agent.run('Tell me about retirement planning.');
```

The agent emits AAEP events through the configured transport as it runs. The same safety guarantees as Python: irreversible actions trigger confirmation events, errors emit critical-urgency terminal events, streaming output coalesces at sentence boundaries.

---

## Running the included demo

```bash
npm run demo
```

Runs three scenarios (basic query, tool use, irreversible tool with confirmation) and prints every emitted AAEP event in real time.

---

## Running the conformance suite against it

```bash
# Terminal 1: start the server (port 8084)
npm run server

# Terminal 2: run the Python conformance suite against the TypeScript server
aaep-conformance producer --endpoint http://localhost:8084 --level 2
```

The Python `aaep-conformance` package can verify any HTTP/SSE AAEP producer regardless of implementation language. Cross-language conformance is mechanically demonstrated.

---

## Project layout

```
typescript-minimal/
├── README.md
├── package.json
├── tsconfig.json
├── src/
│   ├── index.ts         # Public API exports
│   ├── types.ts         # TypeScript types matching the AAEP schemas
│   ├── emitter.ts       # AAEPEmitter class
│   ├── coalescer.ts     # StreamCoalescer for sentence-boundary buffering
│   ├── agent.ts         # AgentLoop with mock LLM
│   └── server.ts        # HTTP/SSE server
└── test/
    ├── emitter.test.ts
    └── coalescer.test.ts
```

---

## Key design decisions

### 1. Strict TypeScript types

Every AAEP event has a corresponding TypeScript interface (`SessionStartedEvent`, `ToolInvokedEvent`, etc.). The emitter methods are strongly typed so editor autocomplete shows valid field names and the compiler catches missing required fields. Types match the JSON Schemas exactly.

### 2. No framework dependencies

The example uses only the Node.js standard library plus type definitions. No Express, no Fastify, no agent framework — just the language and runtime. This makes the integration pattern clear and ensures the example survives ecosystem churn.

### 3. Runtime safety enforcement (same as Python)

The `awaitConfirmation` method throws if called with `irreversible: true`, `riskLevel: 'high'`, and `defaultDecision: 'accept'`. This matches the JSON Schema's if/then rule AND the Python emitter's runtime check. The safety contract is enforced at every layer.

### 4. Promise-based confirmation blocking

JavaScript doesn't have Python's `asyncio.Future`, but `Promise` works the same way. `awaitConfirmation()` returns a reply token; calling code does `await emitter.waitForDecision(token)` to block until the subscriber replies via `submitReply()`.

### 5. Compatible with browser-side agents

The emitter code is environment-agnostic (no Node-specific imports in `emitter.ts`). You can use the same `AAEPEmitter` in a browser bundle for browser-side agents. Only `server.ts` is Node-specific.

---

## Cross-language conformance verification

This example demonstrates that **AAEP is genuinely language-agnostic**. The same `aaep-conformance` Python tool that verifies the Python examples also verifies this TypeScript example without modification.

To prove this end-to-end:

```bash
# Run all 5 servers simultaneously
python -m aaep_minimal_producer.server --port 8080 &     # Python manual loop
python -m aaep_langchain.server --port 8081 &            # LangChain callback
python -m aaep_anthropic_sdk.server --port 8082 &        # Anthropic SDK
python -m aaep_maf.server --port 8083 &                  # Microsoft Agent Framework
npm run server &                                         # TypeScript (port 8084)

# Run conformance against all 5
for port in 8080 8081 8082 8083 8084; do
  aaep-conformance producer --endpoint http://localhost:$port --level 2
done
```

If all 5 pass Level 2, AAEP is interoperable across 4 Python integration patterns AND TypeScript. That's the mechanical proof of "AAEP is language-agnostic" — not a claim, a result.

---

## See also

- [`../python-minimal/`](../python-minimal/) — the Python reference (same machinery, different language)
- [Implementer's Guide §3.7](../../../guides/IMPLEMENTERS_GUIDE.md) — TypeScript integration specifics
- [Node.js SSE documentation](https://nodejs.org/api/http.html) — upstream reference for the transport
