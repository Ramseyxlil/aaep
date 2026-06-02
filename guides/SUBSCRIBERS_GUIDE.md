# AAEP Subscribers' Guide

**For assistive technology vendors and accessibility-tool engineers building AAEP-aware consumers.**

This guide is for the people who build the software that announces AAEP events to users: screen readers (Narrator, NVDA, JAWS, VoiceOver, TalkBack, Orca), voice-control systems (Voice Access, Voice Control, Dragon), switch-input software, refreshable-braille displays, captioning services, and other assistive technology.

If you are an agent or framework engineer, read the [Implementer's Guide](IMPLEMENTERS_GUIDE.md) instead. This guide is for the opposite side of the protocol.

---

## Table of contents

1. [Your role in AAEP](#1-your-role-in-aaep)
2. [The subscriber lifecycle](#2-the-subscriber-lifecycle)
3. [Building the subscription handshake](#3-building-the-subscription-handshake)
4. [Receiving and routing events](#4-receiving-and-routing-events)
5. [Implementing the reply channel](#5-implementing-the-reply-channel)
6. [Coalescing strategies](#6-coalescing-strategies)
7. [Cognitive-load adaptation](#7-cognitive-load-adaptation)
8. [Handling multilingual content](#8-handling-multilingual-content)
9. [Multiple concurrent producers](#9-multiple-concurrent-producers)
10. [AT-specific guidance](#10-at-specific-guidance)
11. [Privacy and data handling](#11-privacy-and-data-handling)
12. [Conformance and certification](#12-conformance-and-certification)

---

## 1. Your role in AAEP

A subscriber sits between a producer (the agent) and the user. Your responsibilities, in order of importance:

1. **Reliably surface critical events to the user.** Confirmation requests, errors, and handoffs MUST reach the user. Other events MAY be filtered, suppressed, or coalesced based on user preference.

2. **Translate events into modality-appropriate announcements.** AAEP gives you structured event data; you decide whether to speak, display, vibrate, present braille, or render to a visual UI.

3. **Reply on the user's behalf when prompted.** Confirmations and clarifications block the producer until you respond. Latency matters: a slow reply degrades the user's experience.

4. **Negotiate sensible defaults during the handshake.** Your capability declaration tells the producer how to adapt to you.

5. **Protect the user from event flood.** Producers may emit hundreds of events per second. You decide what reaches the user and what gets summarized or dropped.

AAEP does not tell you how to render announcements. A screen reader speaks them. A braille display refreshes its cells. A switch-input system might present them as a yes/no question with a single switch press to confirm. AAEP only specifies what information is available; the modality is your choice.

---

## 2. The subscriber lifecycle

A typical subscriber lifecycle:

```
1. Subscriber discovers a producer (via manifest URL, transport endpoint, or platform mechanism)
2. Subscriber sends subscription.request with capability declaration
3. Producer responds:
   - subscription.accepted with subscription_id and honored_capabilities → proceed
   - subscription.rejected with reason_code → handle the failure
4. Producer emits events; subscriber receives, processes, and announces them
5. When a confirmation or clarification event arrives, subscriber:
   a. Surfaces the request to the user
   b. Awaits the user's response (in your modality)
   c. Sends confirmation.reply or clarification.reply
6. (Optional) Subscriber renegotiates capabilities mid-session
7. Subscriber closes the subscription when the user disengages
```

For Conformance Level 1 producers, there is no handshake — events arrive immediately. You should still implement steps 4-5 correctly.

---

## 3. Building the subscription handshake

### 3.1 Constructing your capability declaration

Your capabilities tell the producer how to adapt. The shape is fixed by the spec; the values depend on your AT product and the user's configuration.

```json
{
  "type": "subscription.request",
  "aaep_version": "1.0.0",
  "subscriber_id": "your-at-product-id",
  "subscriber_name": "Your AT Product Name and Version",
  "capabilities": {
    "max_events_per_second": 3,
    "preferred_verbosity": "normal",
    "languages": ["en-US"],
    "supports_confirmation_reply": true,
    "supports_clarification_reply": true,
    "coalesce_boundaries": ["sentence", "completion"],
    "supported_conformance_levels": [1, 2],
    "cognitive_load": "medium",
    "pace_wpm": 180
  }
}
```

### 3.2 Picking sensible defaults for your AT type

| Field | Screen reader default | Voice control default | Braille display default | Captioning service default |
|---|---|---|---|---|
| `max_events_per_second` | 2-5 | 5-10 | 1-2 (slower update cycle) | 10+ |
| `preferred_verbosity` | normal | terse | normal | detailed |
| `coalesce_boundaries` | ["sentence", "completion"] | ["completion"] | ["sentence", "paragraph", "completion"] | ["word", "sentence"] |
| `cognitive_load` | medium | medium | low (less buffer space) | medium |
| `pace_wpm` | follow user's TTS rate | 200 | follow refresh rate | not applicable |

These are defaults. Always allow user override via your settings UI.

### 3.3 Honoring user preferences in the handshake

If your user has configured "low cognitive load" mode (often called "Quiet mode" or "Focus mode"), declare:

```json
{
  "cognitive_load": "low",
  "max_events_per_second": 1,
  "event_filters": {
    "exclude": [
      "aaep:agent.state.changed",
      "aaep:agent.progress.updated"
    ]
  }
}
```

The producer will reduce verbosity and suppress non-critical state transitions. Critical events still arrive.

---

## 4. Receiving and routing events

### 4.1 The router pattern

Most subscribers benefit from a router that dispatches each event to a type-specific handler:

```python
class AAEPRouter:
    def __init__(self):
        self.handlers = {}

    def handler(self, event_type):
        def decorator(fn):
            self.handlers[event_type] = fn
            return fn
        return decorator

    def dispatch(self, event):
        event_type = event.get("type", "<unknown>")
        handler = self.handlers.get(event_type)
        if handler:
            handler(event)
        else:
            self.unknown_event_handler(event)

    def unknown_event_handler(self, event):
        # MUST handle gracefully — extensions exist
        pass


router = AAEPRouter()

@router.handler("aaep:agent.awaiting.confirmation")
def on_confirmation(event):
    surface_confirmation_to_user(event)

@router.handler("aaep:agent.output.streaming")
def on_streaming(event):
    queue_for_announcement(event["chunk"])

# ... etc
```

### 4.2 Handling unknown event types

You MUST handle unknown event types gracefully. Extensions add new event types over time, and producers may emit events from extensions you have not implemented.

The safe default: if the event has a `summary_normal` field, announce it. If not, ignore it. Critical events that require special handling always have well-known types (`agent.awaiting.confirmation`, `agent.session.errored`, `agent.handoff.requested`) — these are stable.

### 4.3 Respecting `urgency`

The `urgency` field tells you the producer's recommended priority:

| Urgency | Recommended subscriber behavior |
|---|---|
| `background` | May be silently suppressed in low-cognitive-load mode |
| `normal` | Announce per user's preferences |
| `critical` | MUST be announced promptly. MUST bypass rate limits and filters |

Critical events represent the user's safety: confirmations, errors, handoffs. Suppressing them under load violates the protocol.

---

## 5. Implementing the reply channel

### 5.1 Confirmation replies

When you receive `agent.awaiting.confirmation`:

1. Surface the `action` and `consequence` to the user in your modality.
2. Wait for the user's decision (in any way appropriate for your AT).
3. Send a `confirmation.reply` with the user's decision.

```python
def handle_confirmation(event):
    action = event["action"]
    consequence = event["consequence"]
    reply_token = event["reply_token"]
    timeout = event["timeout_seconds"]

    # Surface to user (modality-specific)
    speak(f"Confirmation required. {action}. {consequence}.")

    # Get user decision (modality-specific; here using stub)
    decision = await_user_decision(timeout_seconds=timeout)

    # Send reply
    reply = {
        "type": "confirmation.reply",
        "reply_token": reply_token,
        "decision": decision,  # "accept" or "reject"
        "subscription_id": current_subscription_id,
        "timestamp": now_rfc3339(),
        "decided_by": f"user:{current_user_id}",
    }
    transport.send(reply)
```

### 5.2 Clarification replies

Clarifications differ from confirmations: they collect free-form information rather than authorize an action. The `accepted_response_kinds` field tells you what input format the producer expects:

| accepted_response_kinds value | How to surface |
|---|---|
| `freetext` | Open-ended text input |
| `yes_no` | Two-button question or yes/no voice prompt |
| `multiple_choice` | Render `choices` as selectable list |
| `numeric` | Number entry input |

Your AT may not support all input methods. If you can't render one of the accepted kinds, escalate to the user (e.g., "The agent needs you to provide a number; please type it on your keyboard").

### 5.3 Preventing reply duplication

Each `reply_token` is single-use. Track tokens you have already replied to and avoid duplicate replies (a duplicate is harmless because the producer ignores it, but it wastes bandwidth).

### 5.4 Reply latency targets

| Action type | Recommended latency target |
|---|---|
| Confirmation reply (after user decides) | < 100ms transmission |
| Clarification reply | < 100ms transmission |
| User decision time | Bounded by `timeout_seconds`; usually 30-300 seconds |

Long user-decision time is expected. Long transmission time is not.

---

## 6. Coalescing strategies

Streaming output is where naive subscribers fail. Producers emit chunks as fast as the LLM generates them — often 30-100 tokens per second. Your AT cannot announce that fast.

### 6.1 Sentence-boundary coalescing (recommended default)

Buffer incoming chunks until a sentence boundary, then announce the complete sentence:

```python
class SentenceCoalescer:
    SENTENCE_ENDS = {".", "!", "?"}

    def __init__(self):
        self.buffer = ""

    def add(self, chunk, coalesce_hint, complete):
        self.buffer += chunk
        if complete or coalesce_hint == "sentence":
            self._flush()
        elif coalesce_hint == "paragraph":
            self._flush()
        # Otherwise wait for next chunk

    def _flush(self):
        if self.buffer:
            announce(self.buffer)
            self.buffer = ""
```

### 6.2 Producer-hint-driven coalescing

The `coalesce_hint` field tells you what boundary this chunk represents:

| coalesce_hint | What it means | Recommended action |
|---|---|---|
| `none` | Mid-content | Buffer |
| `word` | End of word | Buffer or announce per user preference |
| `sentence` | End of sentence | Announce |
| `paragraph` | End of paragraph | Announce with pause |
| `completion` | End of entire output | Announce final segment |

### 6.3 Cognitive-load-driven coalescing

If user has configured low cognitive load:

```python
if user_cognitive_load == "low":
    # Wait for completion before announcing anything
    if event.get("complete"):
        announce(event["chunk"])  # the final, complete output
elif user_cognitive_load == "medium":
    # Sentence-by-sentence
    sentence_coalescer.add(...)
else:  # high
    # Per-chunk if requested
    announce(event["chunk"])
```

### 6.4 Per-modality nuances

- **Speech (TTS):** sentence-based coalescing matches natural speech rhythm.
- **Braille:** paragraph-based or full-completion coalescing reduces refresh cycles.
- **Captions:** word- or phrase-based coalescing matches reading flow.
- **Voice control output:** completion-only often makes most sense.

---

## 7. Cognitive-load adaptation

Cognitive load is a user setting that says: how much information should reach me?

| Mode | Subscriber behavior |
|---|---|
| `low` | Suppress all background events. Coalesce streaming output to completion only. Announce only critical events and final outputs. |
| `medium` (default) | Standard announcement. Sentence-level coalescing. State changes announced briefly. |
| `high` | Verbose announcements. Per-chunk streaming. State changes announced with detail. |

Some users want detailed running commentary; others want only essential information. Both are legitimate. The protocol gives you a clean way to honor both.

---

## 8. Handling multilingual content

### 8.1 Language detection

The event's `localization_hints.primary_language` (envelope) and per-event `language` (on streaming events) tell you what language the content is in. Use this to:

- Switch TTS voice
- Route to a language-specific speech engine
- Adjust pace (some languages naturally read faster or slower)
- Apply correct grapheme/word segmentation rules

### 8.2 Fallback chains

If your subscriber doesn't support the producer's language, you can request a fallback:

```json
{
  "languages": ["yo-NG", "en-NG", "en-US"]
}
```

The producer will provide content in the first language it supports from your list.

### 8.3 Right-to-left text

When `text_direction` is `"rtl"` or content is in a known RTL script (Arabic, Hebrew, Persian, Urdu), apply the Unicode Bidirectional Algorithm (UAX #9) before rendering. Most modern TTS engines handle this automatically; braille displays and visual UIs may need explicit handling.

### 8.4 Tonal languages

For tonal languages like Yoruba (`yo-NG`), Igbo (`ig-NG`), Vietnamese (`vi-VN`), and Mandarin Chinese (`zh-Hans`, `zh-Hant`), use a TTS voice trained on the specific language. Standard English TTS reading Yoruba will mangle the tones; this is not just an accent issue but a comprehension one.

---

## 9. Multiple concurrent producers

A single user may have multiple AAEP-emitting agents running simultaneously (e.g., a coding assistant in their IDE, a customer service bot in their browser, a productivity agent in their email). Your AT may receive events from all of them.

### 9.1 Producer identification

Every event carries `producer.agent_id` and `producer.agent_name`. Use these to:

- Prefix announcements with the producer name when ambiguous
- Apply different routing rules per producer
- Allow the user to mute specific producers

### 9.2 Session interleaving

Don't assume events arrive in session-grouped order. A user might be running:

- Session A (their coding assistant)
- Session B (their email assistant)
- Session C (a one-shot question to a search agent)

Events from all three may interleave. Use `session_id` to keep them straight in your internal state.

### 9.3 Critical-event priority

When multiple producers want to announce critical events simultaneously, you decide the queueing order. Common heuristics:

- Most recent producer the user interacted with gets priority
- User-configured priority order
- First-come, first-served for events of equal urgency

---

## 10. AT-specific guidance

### 10.1 Microsoft Narrator (Windows)

Narrator supports AAEP via a UIA-bridged subscription model. Your add-on or extension subscribes via Narrator's plugin API and translates AAEP events into Narrator's announcement primitives.

Key integration points:

- Register as a UIA pattern handler for the agent's UI element
- Use Narrator's `Speak()` API for normal-urgency announcements
- Use `SpeakInterruptible()` for critical-urgency announcements
- Surface confirmation events using Narrator's confirmation dialog

A complete add-on prototype is in [`../examples/subscribers/narrator-bridge-prototype/`](../examples/subscribers/narrator-bridge-prototype/).

### 10.2 NVDA (Windows)

NVDA's plugin API makes AAEP integration relatively straightforward. Use a global plugin that:

1. Listens on a configured transport (stdio JSON-RPC or Unix socket are typical)
2. Routes events to NVDA's `speech.speak()` for announcements
3. Handles confirmations via NVDA's dialog framework

A worked NVDA add-on is in [`../examples/subscribers/nvda-addon-prototype/`](../examples/subscribers/nvda-addon-prototype/).

### 10.3 JAWS (Windows)

JAWS scripts can interface with AAEP via a Python bridge. Use a JAWS script that loads a Python process which speaks AAEP messages through JAWS's `SayString` function.

### 10.4 VoiceOver (macOS / iOS)

macOS VoiceOver supports AAEP through accessibility notifications. Send `NSAccessibilityAnnouncementRequestedNotification` for normal events; use `NSAccessibilityPriorityHigh` for critical events.

iOS VoiceOver requires app-side integration: each AAEP-aware app embeds an AAEP subscriber that posts `UIAccessibility.post(notification: .announcement, argument: ...)`.

### 10.5 TalkBack (Android)

TalkBack 14.1+ supports AAEP via Android's `AccessibilityService` API. Implement an `AccessibilityService` subclass that connects to a local AAEP socket and dispatches `AccessibilityEvent`s with `TYPE_ANNOUNCEMENT`.

### 10.6 Orca (Linux)

Orca's plugin API supports Python plugins. Implement a plugin that connects via Unix domain socket and uses Orca's `speak()` API.

### 10.7 Voice control systems

Voice control AAEP integration usually inverts the typical role: you primarily *send* clarification replies and *receive* confirmations. Streaming output is often coalesced to completion only.

### 10.8 Switch input

Switch users typically configure AAEP for `cognitive_load: "low"` and prefer `default_decision: "reject"` to give them more time to switch-confirm intentionally.

### 10.9 Refreshable braille

Braille displays have limited cell counts (often 40 or 80 cells). Aggressively coalesce: paragraph- or completion-only is usually appropriate. Use the manual review pattern: surface a summary on the braille line; the user requests detail via a button if interested.

---

## 11. Privacy and data handling

### 11.1 What you receive

AAEP events may contain:

- The user's original natural-language request
- Summarized tool arguments (possibly including user-supplied PII)
- Streamed model output
- Producer-supplied descriptions of actions

You may NOT receive:

- Tool secrets, API keys, or system credentials (producers MUST NOT include these)
- Full conversation history (unless the producer explicitly includes it)
- Internal model reasoning details (unless surfaced in `summary_detailed`)

### 11.2 What you should NOT log

By default, do not log:

- Full event payloads with `summary_normal` containing user requests
- Authentication tokens (these travel separately from event payloads)
- Cross-session correlation that could reveal user behavior patterns

If you need diagnostics, log envelope-only (type, event_id, session_id, timestamp, producer.agent_id). This is enough to debug timing issues without retaining user content.

### 11.3 User data in replies

When you send a clarification reply, the user's response is included in the `response` field. This data leaves your subscriber. Consider whether your AT's policies allow this; some health and education AT may need to redact PII before transmission.

---

## 12. Conformance and certification

### 12.1 What "AAEP-compliant subscriber" means

A subscriber that:

1. Implements at least Conformance Level 1 (the protocol's minimum)
2. Passes the subscriber half of the conformance test suite at its claimed level
3. Honors the negotiated capabilities throughout each subscription
4. Surfaces critical events to the user

### 12.2 Running the conformance suite

```bash
pip install aaep-conformance
aaep-conformance subscriber --connect <your-subscriber-endpoint> --level 2
```

The suite acts as a synthetic producer, exercising your subscriber against ~120 test cases. It generates `conformance-report.json` and HTML reports.

### 12.3 Publishing your conformance

Include in your AT's accessibility documentation:

- Conformance level claimed (1, 2, or 3)
- Date of last conformance run
- Link to the conformance report
- AAEP version supported

Example: *"VoiceOver supports AAEP v1.0 at Conformance Level 2. Last verified: 2026-09-15. Report: [link]."*

### 12.4 Reporting issues

If you find a producer claiming AAEP conformance whose behavior is non-conforming, file an issue on their repository. If your own AT product cannot pass a conformance test, file an issue on the AAEP repository — the spec may need clarification.

---

## Where to go from here

- For the precise normative rules, return to the [specification](../spec/SPEC.md).
- For implementing the **producer** side, read the [Implementer's Guide](IMPLEMENTERS_GUIDE.md).
- For domain-specific extensions, read the [Extensions Guide](EXTENSIONS_GUIDE.md).
- For reference subscriber implementations, see [`../examples/subscribers/`](../examples/subscribers/).
- For frequently asked questions, see the [FAQ](FAQ.md).

Welcome to the AAEP subscriber community. The protocol exists because of you.
