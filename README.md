# AAEP — Agent Accessibility Event Protocol

> **AAEP is an open protocol that lets AI agents tell assistive technology what they are doing, in a language any screen reader, voice control, or alternative input device can understand.**

[![Spec](https://img.shields.io/badge/spec-v1.0.0-blue)](spec/SPEC.md)
[![License: Spec CC-BY-4.0](https://img.shields.io/badge/spec-CC--BY--4.0-lightgrey)](LICENSE-CC-BY-4.0)
[![License: Code MIT](https://img.shields.io/badge/code-MIT-green)](LICENSE-MIT)
[![Conformance Tests](https://github.com/Ramseyxlil/aaep/actions/workflows/conformance-tests.yml/badge.svg)](https://github.com/Ramseyxlil/aaep/actions/workflows/conformance-tests.yml)
[![Website](https://img.shields.io/badge/website-aaep--protocol.org-blue)](https://aaep-protocol.org)
[![PyPI](https://img.shields.io/pypi/v/aaep-conformance)](https://pypi.org/project/aaep-conformance/)

---

## What this is, in one paragraph

AI agents are being deployed everywhere: in chat apps, in IDEs, in customer-service portals, in mobile assistants. For sighted users with no disabilities, these agents work reasonably well. For the more than one billion people worldwide who use assistive technology, agents are often unusable: state changes are invisible, tool calls are silent, streaming output floods the screen reader, and irreversible actions happen without surfaced confirmation. Every product team solves this differently, badly, or not at all. There is no shared language between agents and assistive technology. **AAEP is that shared language.**

## What this is not

- **AAEP is not a library.** There is no `pip install aaep` that turns your agent accessible.
- **AAEP is not a service.** There is no central server to run, no cloud account to register.
- **AAEP is not tied to any vendor.** It works with Microsoft Agent Framework, AutoGen, LangChain, Semantic Kernel, the Anthropic SDK, OpenAI, custom agents, and frameworks that have not been invented yet.
- **AAEP is not specific to any assistive technology.** It works with Narrator, NVDA, JAWS, VoiceOver, TalkBack, voice control, switch control, and assistive devices that have not been invented yet.

AAEP is a **specification**: a precise document that defines the events agents emit, the way subscribers receive them, and the contracts between the two. Implementers read the spec, write a few hundred lines of integration code in their own codebase, and ship. The protocol does the rest.

## How a developer adopts AAEP

```python
# Pseudocode. Real example code lives in examples/producers/.
# At each lifecycle point in your agent, emit an AAEP event.

emit({
    "@context": "https://aaep-protocol.org/context/v1",
    "type": "aaep:agent.tool.invoked",
    "event_id": "evt_8a3f...",
    "session_id": "sess_2c91...",
    "timestamp": "2026-06-30T14:22:11Z",
    "tool": "transfer_funds",
    "description": "Transfer money between accounts",
    "summary_normal": "Initiating transfer of $500 to savings",
    "risk_level": "high",
    "irreversible": true
})
```

That JSON object is the entire contract. Any AAEP-compliant subscriber, anywhere in the world, can receive it and announce the agent's action appropriately to the user. The developer wrote one event. The protocol carried it. The subscriber translated it into speech, braille, or whatever the user needed.

For a complete worked integration, read **[examples/producers/python-langchain/README.md](examples/producers/python-langchain/README.md)**.

## How a user experiences AAEP

The user never sees the protocol. They use whatever assistive technology they normally use. If that assistive technology supports AAEP, and the agents they interact with support AAEP, things start working. Confirmations get announced cleanly. Tool calls become audible. Streaming output is paced for human comprehension. Irreversible actions are blocked until explicit consent. Multi-agent orchestration becomes navigable.

The user experiences AAEP as "AI suddenly stopped being broken."

## Install

The conformance test suite is on PyPI:

```bash
pip install aaep-conformance
aaep-conformance --version
```

The minimal Python producer is on PyPI:

```bash
pip install aaep-minimal-producer
```

The TypeScript producer is on npm:

```bash
npm install aaep-typescript-producer
```

A React-based web subscriber is on npm:

```bash
npm install @aaep/web-subscriber-react
```

Additional reference packages for LangChain, Anthropic SDK, Microsoft Agent Framework, MCP bridge, OpenTelemetry bridge, and the multilingual and medical extensions are also available on PyPI; see **[examples/](examples/)**.

## Where to start

**If you want to understand what AAEP is and why it exists:**
Read **[spec/01-introduction.md](spec/01-introduction.md)**.

**If you want to implement AAEP for your agent or framework:**
Read **[guides/QUICKSTART.md](guides/QUICKSTART.md)** (30 minutes), then **[guides/IMPLEMENTERS_GUIDE.md](guides/IMPLEMENTERS_GUIDE.md)**.

**If you want to build an AAEP-aware subscriber (screen reader, voice control, accessible UI):**
Read **[guides/SUBSCRIBERS_GUIDE.md](guides/SUBSCRIBERS_GUIDE.md)**.

**If you want to read the full specification:**
Read **[spec/SPEC.md](spec/SPEC.md)** (the joined document) or browse the chapter files in **[spec/](spec/)**.

**If you want to extend AAEP for a specific domain:**
Read **[guides/EXTENSIONS_GUIDE.md](guides/EXTENSIONS_GUIDE.md)**.

**If you want to verify your implementation is correct:**
Run the conformance test suite from **[conformance/](conformance/)**.

## Repository layout

```
aaep/
├── spec/              ← The specification, by chapter
├── schemas/           ← JSON Schemas for every event type
├── guides/            ← Implementer's Guide, Subscribers' Guide, Quickstart, FAQ
├── conformance/       ← Conformance test suite (installable Python package)
├── examples/          ← Reference producers, subscribers, bridges, extensions
├── tools/             ← CLI utilities for validating, capturing, replaying events
├── governance/        ← Project governance, contribution rules, ADOPTERS, proposals
├── website/           ← Source for aaep-protocol.org
└── .github/           ← Issue templates, PR templates, CI workflows
```

For a full explanation of why each folder exists, read **[governance/GOVERNANCE.md](governance/GOVERNANCE.md)**.

## Core principles

1. **Protocols outlive libraries.** AAEP is a specification; implementations are downstream artifacts.
2. **Rigid core, extensible periphery.** Twelve standard event types with fixed semantics; an extension mechanism that lets anyone add new types, fields, transports, and capabilities without breaking compatibility.
3. **No vendor capture.** Spec is CC-BY-4.0, code is MIT, governance is open, no single company can take AAEP private.
4. **Disabled users are co-authors.** Every major design decision is validated with disabled developers and users; the spec credits them.
5. **Conformance is verifiable.** Claims of AAEP support must pass an open test suite. Without enforcement, "compliance" is marketing.

## Conformance levels

| Level | Name | Requirements |
|---|---|---|
| **1** | Notification | Producer emits lifecycle and state events; subscriber can announce them. No reply channel required. |
| **2** | Interactive | Adds confirmation, clarification, and handoff with a working reply channel and timeout semantics. |
| **3** | Negotiated | Adds subscription handshake, backpressure, coalescing negotiation, and signed manifests. The full protocol. |

A producer or subscriber that passes the conformance test suite at a given level may claim that level publicly. See **[spec/09-conformance.md](spec/09-conformance.md)** for full requirements.

## Stability and support window

AAEP v1.0.0 ships with the following stability commitments:

- **Backward-compatible** schema and behavioral stability throughout the v1.x series.
- **Full support window:** June 2026 through June 2031 (5 years).
- **Security-only maintenance:** through June 2033 (2 additional years).

See **[governance/ROADMAP.md](governance/ROADMAP.md)** for the public roadmap.

## Adopters

A current list of organizations and projects with AAEP support lives in **[governance/ADOPTERS.md](governance/ADOPTERS.md)**. If you have shipped AAEP support, please open a pull request adding yourself.

## Governance

AAEP was **founded by [Abdulrafiu Izuafa](https://www.linkedin.com/in/abdulrafiu-izuafa-a9a451264/), open to all contributors**. The protocol's long-term home is intended to be a foundation; this repository is the staging ground.

Decisions follow the proposal process documented in **[governance/CONTRIBUTING.md](governance/CONTRIBUTING.md)**. Major changes are tracked as AAEP Change Proposals (ACPs) in **[governance/proposals/](governance/proposals/)**.

Maintainers are listed in **[governance/MAINTAINERS.md](governance/MAINTAINERS.md)**.

## License

This repository uses a split-license model:

- **Specification, schemas, and documentation** are licensed under [Creative Commons Attribution 4.0 International (CC-BY-4.0)](LICENSE-CC-BY-4.0).
- **Code, examples, conformance tests, and tools** are licensed under the [MIT License](LICENSE-MIT).

This combination lets anyone, including commercial entities, implement and ship AAEP freely with appropriate attribution. See **[LICENSE](LICENSE)** for the combined notice and **[NOTICE](NOTICE)** for attributions.

## Citing AAEP

If you reference AAEP in academic or industry work, please use the citation metadata in **[CITATION.cff](CITATION.cff)**.

## Security

If you discover a security issue in the protocol or any reference implementation, please follow the responsible disclosure process in **[governance/SECURITY.md](governance/SECURITY.md)** rather than opening a public issue.

## Contact

- **Maintainer:** Abdulrafiu Izuafa (`Abdulrafiu@izusoft.tech`)
- **Issues and discussions:** [github.com/Ramseyxlil/aaep](https://github.com/Ramseyxlil/aaep)
- **Website:** [aaep-protocol.org](https://aaep-protocol.org)

---

*AAEP exists because accessibility cannot be retrofitted into agentic AI; it must be designed in. This protocol is one piece of that work. Contributions, criticism, and adoption are all welcome.*