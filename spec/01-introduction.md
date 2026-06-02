# Chapter 1 — Introduction

*Status: Informative*

---

## 1.1 The problem

In the span of roughly thirty months between 2023 and 2026, AI agents moved from research demos to production deployment. They now write code in IDEs, draft emails in mailbox clients, summarize documents in word processors, dispatch customer-service interactions in call centers, plan trips in travel applications, execute financial transactions in banking apps, and orchestrate workflows in operating systems. The pace of deployment has substantially outrun the pace of accessibility work.

For a sighted user with no significant disabilities, an AI agent typically appears in a side panel or chat window. The user types a request, watches a sequence of visible indicators describe what the agent is doing ("searching files," "calling the calendar tool," "drafting response"), reads or skims the output as it streams in, clicks a confirmation button when the agent asks, and moves on. The experience is imperfect but workable.

For the more than one billion people worldwide who use assistive technology, the same agent often presents an unusable interface. Several specific failure modes recur across virtually every AI agent product shipping today:

1. **State transitions are visually-signaled and inaudible.** When the agent transitions from "thinking" to "calling a tool" to "writing output," the visible indicator changes color or animates. The screen reader has no way of knowing that anything happened.

2. **Tool invocations are silent.** When the agent reads files, queries databases, or calls external APIs, those actions happen in a side panel that the screen reader does not announce. Users with vision impairments learn after the fact that the agent did things they did not authorize and could not perceive.

3. **Streaming output overwhelms the screen reader.** When the agent emits its final response, modern LLMs stream tokens at fifty to one hundred tokens per second. Screen readers cannot announce content that fast. The user hears a flood of partial words and broken sentences, or the screen reader buffers and announces only fragments, or the user disables announcements entirely and loses access to the response. None of these outcomes are acceptable.

4. **Confirmations are visual modals.** When the agent asks for permission to perform an irreversible action (sending an email, transferring funds, modifying a file), the request appears as a visual modal. Screen reader users may not be focused on the modal at the moment it appears, may not hear it announced, may interact with the wrong button, or may have the modal time out and execute a default action before they finish reading the question.

5. **Multi-agent orchestration is opaque.** When an agent system involves multiple agents collaborating (a research agent calling a coding agent calling a deployment agent), the visual interface shows a tree or graph of activity. Screen reader users cannot navigate that tree; they receive a linear stream of events and lose track of which agent is doing what.

6. **Voice control and switch control are barely supported.** Users who orchestrate AI agents via voice control (Dragon NaturallySpeaking, Windows Speech Recognition) or via switch input (single-switch scanning, sip-and-puff, eye gaze) encounter agents that cannot be cleanly interrupted, paused, or redirected. The agent's output sometimes conflicts with the user's input modality (voice agents talking over voice users).

These are not edge cases. Each of them is reproducible across every major AI agent product as of the time this specification is written. Each represents an exclusion of users with disabilities from the most consequential technology shift of the decade. Each is currently addressed, when addressed at all, by individual product teams writing custom one-off accessibility integrations that do not transfer between products.

The pattern is familiar to accessibility practitioners. It is the pattern that produced the era of inaccessible Flash applications, the era of inaccessible mobile apps, and the era of inaccessible single-page web applications. In each prior era, fragmentation of accessibility approaches across vendors prevented disabled users from having a coherent experience until a unifying standard emerged. ARIA emerged for the web. UIA emerged for Windows applications. AT-SPI emerged for Linux desktops. Mobile platform APIs emerged for iOS and Android. The agentic AI era has, as of 2026, no equivalent.

AAEP exists to fill that gap.

## 1.2 Why existing accessibility standards do not address this

A reasonable question for any new accessibility specification is: why is existing accessibility infrastructure insufficient? Existing accessibility standards address the **visual presentation layer**: the rendered UI that the user actually sees on screen. They specify how a button announces itself, how a dropdown communicates its state, how a live region notifies the user of changes. These standards are mature, widely adopted, and largely successful at their intended scope.

The accessibility problem that AI agents create is **not at the visual presentation layer**. It is at a layer one level higher: the agent's own reasoning and action state, much of which does not have a visual presentation at all. The agent's "thinking" between tool calls produces no UI. The agent's decision to call a tool with particular arguments produces no UI that the user can interact with. The agent's intent to perform an irreversible action exists in the agent's internal state for several seconds before any UI is rendered. The existing accessibility APIs operate on rendered UIs and cannot observe state that has not yet been rendered.

A concrete illustration: consider an agent that is about to send an email. Internally, the agent has decided to call the `send_email` tool with specific parameters. Externally, the agent has not yet rendered anything to the screen. In a typical implementation, the agent calls `send_email`, the email is sent, and only afterward is a status message rendered ("Email sent."). The accessibility layer has nothing to announce until the message is rendered. By the time the message is rendered, the irreversible action is complete.

A screen reader can do nothing useful with the post-hoc status message. The user needed the screen reader to announce the action *before it happened*, with enough detail to confirm or cancel it. That information lives only in the agent's internal state, and no existing accessibility API exposes it.

The same logic applies to streaming output, multi-agent state, tool invocations, and reasoning transitions. The information assistive technology needs lives in the agent's internal state, not in its rendered UI. Existing accessibility APIs do not address internal state because, before agentic AI, internal state was not a significant accessibility surface. With agentic AI, internal state becomes the *primary* accessibility surface.

AAEP defines the missing protocol layer: a vocabulary, exchange model, and conformance contract that lets agents announce their internal state to assistive technology in a standardized way.

## 1.3 What AAEP is

AAEP is, formally, three things:

1. **A wire format.** A precise JSON-based encoding for events that agents emit. The format includes a fixed envelope, twelve core event types, and an extension mechanism for domain-specific additions. The format is specified in [Chapter 3 (Event envelope)](03-event-envelope.md) and [Chapter 4 (Core event types)](04-core-event-types.md).

2. **An exchange model.** A defined protocol for how subscribers (assistive technology, accessible UIs, voice control, switch software) connect to producers (agents), negotiate capabilities, receive events, and reply to confirmation requests. The exchange model is specified in [Chapter 5 (Subscription handshake)](05-subscription-handshake.md) and [Chapter 6 (Confirmation protocol)](06-confirmation-protocol.md).

3. **A conformance contract.** A graded set of requirements that producers and subscribers can claim to satisfy. Three levels are defined: Level 1 (Notification), Level 2 (Interactive), and Level 3 (Negotiated). The conformance levels are specified in [Chapter 9 (Conformance)](09-conformance.md).

These three components together constitute the protocol. Implementations of the protocol exist in many forms (libraries, framework integrations, assistive technology subscribers, extensions) and are catalogued in [governance/ADOPTERS.md](../governance/ADOPTERS.md), but the protocol itself is defined entirely by the specification document.

## 1.4 What AAEP is not

The boundary of the specification is as important as its content. AAEP intentionally does not address several adjacent concerns. Implementers should be aware of these boundaries.

### AAEP is not an agent framework

AAEP does not define how to build an AI agent. It does not specify the agent's reasoning loop, its tool-calling mechanism, its memory model, its prompt structure, or its model provider. Existing agent frameworks (Microsoft Agent Framework, AutoGen, LangChain, Semantic Kernel, the Anthropic SDK with tool use, custom implementations) all define those concerns. AAEP plugs into whatever framework the implementer chooses.

### AAEP is not an accessibility framework

AAEP does not define how assistive technology should render announcements. It does not specify speech rates, braille line wrapping, switch-input scanning patterns, or haptic feedback timing. Existing assistive technology (Narrator, JAWS, NVDA, VoiceOver, TalkBack, voice control software, switch control software) defines those concerns. AAEP plugs into whatever assistive technology the user has chosen.

### AAEP is not a safety framework

AAEP does not define whether an agent should be permitted to perform a particular action. It does not encode policy about which tools agents may call, which data they may access, or which decisions they may make autonomously. AAEP describes what the agent is doing to consumers that need to know, including the user. Policies about what the agent may do belong to other systems (organizational policy, regulatory frameworks, agent governance platforms like [Microsoft Agent 365](https://techcommunity.microsoft.com/blog/agent-365-blog), corporate compliance tools).

The distinction matters: AAEP's confirmation protocol can be used to surface a request for user consent before an irreversible action, but AAEP does not decide which actions require consent. That decision is made by the agent's author or the deploying organization.

### AAEP is not a UI accessibility specification

AAEP does not define how the agent's rendered UI should be accessible. WAI-ARIA already covers web UI accessibility. UIA, AT-SPI, and platform-specific APIs cover native UI accessibility. AAEP addresses the agent's internal state layer, which sits above the UI layer and is currently unaddressed by any standard.

In practice, an accessible agent product implements both AAEP for state announcements and ARIA (or platform equivalents) for UI rendering. The two layers complement each other.

### AAEP is not a tool protocol

AAEP does not standardize how agents call tools. The [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) addresses that. An agent using MCP for tool integration can simultaneously use AAEP for accessibility announcements; the two protocols address orthogonal concerns and are designed to coexist. A bridge example demonstrating this coexistence is provided in [`examples/bridges/mcp-aaep-bridge/`](../examples/bridges/mcp-aaep-bridge/).

### AAEP is not a hosted service

There is no AAEP server. There is no AAEP cloud. There is no central authority that grants AAEP compliance, hosts AAEP events, or routes AAEP traffic. The protocol is fully decentralized. Producers emit events directly to subscribers over whatever transport they negotiate. The AAEP project provides only the specification, the conformance test suite, and reference materials.

## 1.5 Audience

This specification has multiple audiences with different needs. The following groups are explicitly addressed.

### Agent developers and framework maintainers

Engineers who build AI agent products or maintain agent frameworks (Microsoft Agent Framework, AutoGen, LangChain, Semantic Kernel, Anthropic SDK, OpenAI Assistants, custom implementations) are the primary audience for the producer side of AAEP. They need to understand which events to emit, when, and with what content, so that their agents become accessible without per-product accessibility engineering.

For this audience, the primary chapters are [3 (Event envelope)](03-event-envelope.md), [4 (Core event types)](04-core-event-types.md), [5 (Subscription handshake)](05-subscription-handshake.md), and [9 (Conformance)](09-conformance.md). The [Implementer's Guide](../guides/IMPLEMENTERS_GUIDE.md) provides integration patterns.

### Assistive technology vendors

Maintainers of screen readers, voice control software, switch control software, refreshable braille displays, captioning systems, and other assistive technology are the primary audience for the subscriber side of AAEP. They need to understand how to subscribe to agent event streams, how to interpret events, and how to integrate AAEP events with their existing announcement and interaction models.

For this audience, the primary chapters are [3 (Event envelope)](03-event-envelope.md), [4 (Core event types)](04-core-event-types.md), [5 (Subscription handshake)](05-subscription-handshake.md), [6 (Confirmation protocol)](06-confirmation-protocol.md), and [11 (Internationalization)](11-internationalization.md). The [Subscribers' Guide](../guides/SUBSCRIBERS_GUIDE.md) provides implementation patterns.

### Users with disabilities and accessibility advocates

Users who rely on assistive technology, and advocates who represent their interests, are the population AAEP exists to serve. While the specification itself is technical, the [Introduction](01-introduction.md) (this chapter) is written to be readable by non-engineers. Users who want a non-technical overview should also consult the project [FAQ](../guides/FAQ.md) and the [README](../README.md).

User feedback is the most important input to AAEP's design. Mechanisms for participating in formative studies, providing review feedback, and joining as co-authors are documented in [governance/CONTRIBUTING.md](../governance/CONTRIBUTING.md).

### Researchers and standards practitioners

Researchers in human-computer interaction, accessibility, and AI, along with practitioners at standards bodies (W3C, IETF, ISO, regional accessibility regulators), are an important secondary audience. They evaluate whether AAEP is rigorous enough to merit standardization and citation.

For this audience, the full specification is intended to be read in order, with particular attention to [Chapter 2 (Terminology)](02-terminology.md), [Chapter 7 (Extensions)](07-extensions.md), [Chapter 10 (Security)](10-security.md), and [Chapter 12 (Versioning)](12-versioning.md).

### Domain experts designing AAEP extensions

Experts in specialized domains (medical AI, autonomous systems, financial services, education, government) may wish to extend AAEP with domain-specific event types, fields, or capabilities. AAEP's extension mechanism is designed to make this possible without requiring changes to the core specification.

For this audience, the primary chapter is [Chapter 7 (Extensions)](07-extensions.md), and the [Extensions Guide](../guides/EXTENSIONS_GUIDE.md) provides design patterns.

## 1.6 Design principles

The following principles guided the design of AAEP. They are stated here so that future revisions of the protocol can be evaluated against them, and so that implementers can understand the trade-offs that shaped each decision.

### Principle 1: Protocols outlive libraries

AAEP is specified as a protocol, not distributed as a library. Libraries are language-specific, framework-specific, version-specific artifacts. Protocols are language-neutral, framework-neutral, version-stable contracts. A protocol implemented well outlives the implementations that first carry it.

In practice, this means AAEP avoids tying its design to any particular programming language, agent framework, transport, or assistive technology. Reference implementations exist as illustrations, not as the official way to use the protocol. Implementers are expected to write integration code in their own codebases, against the spec, in their own languages.

### Principle 2: Rigid core, extensible periphery

The core of AAEP — the envelope, the twelve event types, the subscription handshake, the confirmation protocol — is rigidly specified and not extensible. Implementations must conform to these exactly. The periphery — additional event types, additional fields on existing events, additional transports, additional capabilities — is open and extensible by anyone, without requiring permission from AAEP maintainers.

This principle is borrowed from successful prior standards (HTTP, ARIA, ActivityStreams). The rigid core enables interoperability. The extensible periphery enables evolution. A protocol with neither dies; a protocol with only one or the other fragments.

### Principle 3: Disabled users are co-authors

Decisions about accessibility cannot be made well by non-disabled people designing for disabled users. AAEP's design is intended to be validated through formative studies with disabled developers and disabled users at every major revision. Findings from such studies must be reflected in the specification or explicitly addressed in the changelog as out-of-scope.

This principle has implications for how the project is governed (see [governance/GOVERNANCE.md](../governance/GOVERNANCE.md)) and how the specification evolves (see [Chapter 12 (Versioning)](12-versioning.md)). It is not a marketing claim; it is a design constraint that affects how decisions get made.

### Principle 4: No vendor capture

AAEP is licensed permissively (specification under CC-BY-4.0, reference code under MIT) and governed openly. No single vendor controls the protocol, and no vendor's preferences are privileged in its design. Where AAEP must make decisions that align with one vendor's product more than another's, those decisions are documented and justified in the specification or in the associated [proposal](../governance/proposals/).

The long-term governance plan is to transition stewardship of AAEP to a W3C Community Group, then potentially a W3C Working Group, neither of which is vendor-controlled.

### Principle 5: Conformance is verifiable

Claims of AAEP compliance must be verifiable through the conformance test suite. A vendor that says "we support AAEP" must be able to produce a passing conformance report. Without enforcement, "compliance" is marketing language; with enforcement, it is a contract.

The conformance test suite is open-source, included in this repository at [`conformance/`](../conformance/), and can be run by anyone against any endpoint. Test results are reproducible.

### Principle 6: Backward compatibility is a feature

Once a major version of the specification is stable, breaking changes to that major version are not permitted. New features are added through minor versions in a backward-compatible way. When a breaking change is truly necessary, it requires a major version bump and a deprecation period for the prior version.

This principle is unfashionable in the agentic AI space, which is moving rapidly and prizes velocity over stability. AAEP deliberately prioritizes stability because the cost of breaking compliance for downstream implementers (re-engineering assistive technology, re-certifying compliance with disability regulations, re-validating with disabled users) is far higher than the cost of waiting one version for a feature.

### Principle 7: The user is in control

AAEP gives the end user, through their chosen assistive technology, the ability to declare preferences and have those preferences honored by producers. Users with high cognitive load receive less verbose announcements. Users in a different language receive localized content. Users with motor disabilities have additional time to confirm actions. These preferences are not optional features; they are first-class capabilities in the subscription handshake.

Producers are required to honor declared preferences within the limits of what they can support. Where preferences cannot be honored, producers must say so explicitly during the handshake rather than ignore the user's request.

## 1.7 A walkthrough example

To make the abstract concepts concrete, consider the following scenario. A blind product manager named Folake uses Windows with the Narrator screen reader. She works at a financial services company. She has been given an AI-powered customer-service agent in Microsoft Teams that handles routine support tickets. The agent has tools for checking account balances, initiating transfers, and freezing accounts in response to fraud reports. Without AAEP, Folake's experience of this agent is broken: tool calls happen silently, the agent's streaming output overwhelms Narrator, and the visual confirmation modals time out before she can hear and respond to them. She has filed three complaints in two weeks.

With AAEP support in both the agent and Narrator, the same workflow proceeds as follows.

Folake types: "Please look into the fraud report on case 4471."

Narrator announces, paced naturally:

> "Customer service agent started."
>
> "Thinking."
>
> "Calling check_case_details. Looking up case 4471."
>
> "Case 4471 reported by Mr. Adebayo. Three suspicious transactions on account 7821, totaling 240,000 naira."
>
> "Thinking."
>
> "Confirmation required. Freeze account 7821 pending investigation. Customer will lose access until manually unfrozen by compliance team. Press space to confirm, escape to reject, or wait three hundred seconds to auto-cancel."

Folake reviews the case in her mind. She presses space.

> "Account 7821 frozen. Case ID compliance-2026-1129 opened."
>
> "Drafting customer notification."
>
> *(paced sentence by sentence as the LLM streams)*
>
> "Dear Mr. Adebayo. Thank you for reporting the suspicious activity on your account. As a precaution, your account has been temporarily frozen while our compliance team investigates."
>
> "Notification ready. Press F6 to review, press Enter to send, or Escape to revise."

Folake presses F6 to review, then Enter to send.

> "Notification sent. Case 4471 status updated to under review."
>
> "Done."

The entire workflow took ninety seconds. Folake performed it independently, without needing a sighted colleague to read her the modal text, and without missing the confirmation step. The agent's accessibility was not engineered specifically for her product; the agent emitted AAEP events, Narrator subscribed to them, and the protocol carried the information.

This is not an aspirational scenario. It describes the end state that AAEP is designed to enable. The exact event types and exchange mechanisms underlying this walkthrough are specified in [Chapter 4 (Core event types)](04-core-event-types.md) and [Chapter 5 (Subscription handshake)](05-subscription-handshake.md).

## 1.8 What this specification does not require of you

Implementers approaching AAEP for the first time sometimes assume that adopting the protocol implies large changes to their existing codebase. This is generally not the case. The following are explicitly *not* required:

- **You do not need to rewrite your agent.** AAEP events are emitted at lifecycle points your agent already has (session start, LLM call, tool call, output stream, session end). Most frameworks expose these as middleware hooks, callbacks, or events. AAEP integration typically adds 100-300 lines of code to an existing agent codebase.

- **You do not need to choose AAEP exclusively.** AAEP coexists with WAI-ARIA for web UI accessibility, with platform accessibility APIs for native UI accessibility, with MCP for tool calling, with OpenTelemetry for observability. An agent can use all of these simultaneously without conflict.

- **You do not need to support all conformance levels.** Level 1 (Notification) is sufficient for many use cases and is much easier to implement than Level 3 (Negotiated). Implementers should choose the level appropriate to their product and may upgrade later.

- **You do not need to install any AAEP library.** AAEP is a protocol. Implementers may use reference code from `examples/` as a starting point, but the canonical way to support AAEP is to read the specification and implement event emission directly in your own codebase.

- **You do not need to host anything new.** AAEP runs over transports your infrastructure likely already supports (Server-Sent Events over HTTPS, WebSocket, local IPC). No new services, no cloud accounts, no third-party dependencies.

- **You do not need permission from anyone to implement AAEP.** The specification is published under CC-BY-4.0. The reference code is published under MIT. Any developer at any organization may implement AAEP support and may claim conformance after passing the conformance tests.

## 1.9 Document structure

The remainder of this specification proceeds as follows.

[Chapter 2 (Terminology and conventions)](02-terminology.md) defines the precise vocabulary used throughout the rest of the specification. Reading Chapter 2 is recommended even for readers who plan to skim other chapters, because terms used informally elsewhere may carry specific meaning under the AAEP specification.

[Chapter 3 (Event envelope)](03-event-envelope.md) specifies the required fields that every AAEP event carries, regardless of event type. The envelope is the rigid foundation on which all other events are built.

[Chapter 4 (Core event types)](04-core-event-types.md) specifies the twelve normative event types in detail, including required fields, optional fields, examples, and semantic constraints. This is the longest chapter and the one that implementers will reference most frequently.

[Chapter 5 (Subscription handshake)](05-subscription-handshake.md) specifies how subscribers connect to producers, declare capabilities, and negotiate the terms of event delivery.

[Chapter 6 (Confirmation protocol)](06-confirmation-protocol.md) specifies the blocking flow for irreversible actions: reply tokens, timeouts, default decisions, and security boundaries.

[Chapter 7 (Extensions)](07-extensions.md) specifies how third parties can extend AAEP with new event types, fields, and capabilities, without requiring changes to the core specification.

[Chapter 8 (Transports)](08-transports.md) specifies the transport-agnostic requirements that any conforming transport must satisfy, and provides a non-normative survey of recommended transports.

[Chapter 9 (Conformance)](09-conformance.md) specifies the three conformance levels and their normative requirements.

[Chapter 10 (Security considerations)](10-security.md) specifies the threat model and security boundary of AAEP.

[Chapter 11 (Internationalization)](11-internationalization.md) specifies how AAEP handles languages, locales, character encoding, right-to-left text, and culturally-sensitive content.

[Chapter 12 (Versioning and evolution)](12-versioning.md) specifies how the protocol changes over time and what implementers can rely on across versions.

The appendices provide non-normative reference material: the event state machine (Appendix A), concrete transport binding examples (Appendix B), the glossary (Appendix C), and references (Appendix D).

## 1.10 Where to go next

Readers should now proceed to [Chapter 2 (Terminology and conventions)](02-terminology.md), which establishes the vocabulary used throughout the rest of the specification.

Readers who prefer to start with a concrete example may instead jump to [Chapter 3 (Event envelope)](03-event-envelope.md), which shows the shape of an AAEP event, or to the [Quickstart guide](../guides/QUICKSTART.md), which walks through a complete minimal integration in approximately ten minutes.
