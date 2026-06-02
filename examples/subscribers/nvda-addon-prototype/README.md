# AAEP Subscriber Add-on for NVDA (Prototype)

A reference NVDA add-on that subscribes to AAEP producers and routes events to NVDA's speech and braille engines. This is a **prototype** demonstrating how AAEP integrates with a real screen reader.

[NVDA (NonVisual Desktop Access)](https://www.nvaccess.org/) is the open-source Windows screen reader used by hundreds of thousands of blind and low-vision users worldwide. This add-on is the first reference subscriber for a major screen reader and serves as the template for similar integrations (JAWS, VoiceOver, Orca, Narrator).

**Status:** Prototype. Functional but not yet production-hardened. See §"Production readiness" below.

---

## What this add-on does

When loaded into NVDA, the add-on:

1. **Connects to one or more AAEP producers** over HTTP/SSE
2. **Routes incoming events to NVDA's speech engine** with appropriate priority
3. **Handles confirmations and clarifications via NVDA's input gestures** — the user accepts/rejects with keyboard shortcuts
4. **Surfaces critical events with appropriate urgency** — interrupting current speech for `awaiting.confirmation`, queueing for normal events
5. **Provides a settings dialog** in NVDA Preferences for configuring producer endpoints

The add-on is opt-in: users explicitly add producer endpoints. Nothing happens until they do.

---

## Why NVDA first

We chose NVDA as the first AT integration target for three reasons:

1. **Open source.** NVDA is under GPLv2. We can ship a real add-on freely, learn from how it integrates, and the community can iterate without licensing concerns.
2. **Strong add-on ecosystem.** NVDA has well-documented add-on APIs and a thriving add-on store. AAEP can land alongside existing add-ons rather than as a foreign integration.
3. **Linguistically diverse user base.** NVDA is used in over 50 languages worldwide. AAEP's multilingual extension (Yoruba, Hausa, Igbo) has natural fit with NVDA's existing language support.

After NVDA, similar add-ons can be built for [JAWS](https://www.freedomscientific.com/products/software/jaws/), [VoiceOver](https://www.apple.com/accessibility/vision/), [Orca](https://help.gnome.org/users/orca/), and [Narrator](https://support.microsoft.com/narrator).

---

## Installation

### Requirements

- NVDA 2023.1 or newer
- Python 3.10+ (bundled with NVDA)
- Network access to your AAEP producer(s)

### Installing the add-on

1. Download the `.nvda-addon` package from the [AAEP releases](https://github.com/Ramseyxlil/aaep/releases) page
2. Open NVDA → Tools → Manage Add-ons → Install from external file
3. Select the downloaded `.nvda-addon` file
4. Restart NVDA when prompted

Alternatively, install from source:

```bash
cd examples/subscribers/nvda-addon-prototype
python build_addon.py    # creates aaep-subscriber.nvda-addon
```

### Configuring

After installation, open NVDA → Preferences → Settings → AAEP Subscriber:

- **Producer endpoints** — Add one or more AAEP producer base URLs (e.g., `http://localhost:8080`)
- **Preferred languages** — Choose your AT language preference order (e.g., `["yo", "en"]`)
- **Auto-connect on startup** — Whether to start subscribing immediately when NVDA loads
- **Confirmation gesture** — Customize the keyboard shortcut to accept/reject confirmations (default: NVDA+Shift+A / NVDA+Shift+R)
- **Speech priority for critical events** — How to handle awaiting events (interrupt vs queue)

---

## Usage

Once configured, the add-on works in the background. When an AAEP producer is active:

### Normal events
Speech for normal-urgency events queues into NVDA's regular speech buffer. State changes, tool invocations, and streaming output flow naturally without interrupting the user.

Example: `"Mò ń bẹ̀rẹ̀ iṣẹ́ rẹ"` (Yoruba "I'm starting your task") plays as the agent begins.

### Critical events
Awaiting confirmation, awaiting clarification, session errors, and handoff requests:
- **Interrupt** any current speech
- Are spoken at higher priority
- Pause for user response

### Confirmation flow

When an `awaiting.confirmation` event arrives:

1. NVDA speaks: `"Confirm: Send email to alice@example.com. This action cannot be easily undone. Press NVDA+Shift+A to accept, NVDA+Shift+R to reject."`
2. The user presses NVDA+Shift+A (accept) or NVDA+Shift+R (reject)
3. The add-on POSTs the decision back to the producer's `/messages` endpoint
4. The agent proceeds or aborts based on the decision

If the user does nothing within the producer's timeout (typically 300 seconds), the default decision (usually "reject") applies. The add-on speaks: `"Confirmation timed out. Action rejected."`

### Clarification flow

For `awaiting.clarification`:
1. NVDA speaks the question
2. If options are provided, NVDA speaks them numbered
3. User responds via NVDA+Shift+1 through NVDA+Shift+9 for numbered options, or NVDA+Shift+C to enter free-form text
4. The add-on POSTs the response

---

## Architecture

```
   ┌────────────────────────────────────────────┐
   │              NVDA (host)                    │
   │                                              │
   │  ┌──────────────────────────────────────┐   │
   │  │  AAEP Subscriber Add-on              │   │
   │  │                                      │   │
   │  │  ┌────────────────────────────────┐  │   │
   │  │  │ HTTPSseConnection              │  │   │
   │  │  │   listens to /events           │  │   │
   │  │  └────────────────────────────────┘  │   │
   │  │              │                       │   │
   │  │              ▼                       │   │
   │  │  ┌────────────────────────────────┐  │   │
   │  │  │ AAEPEventHandler               │  │   │
   │  │  │   routes events by type        │  │   │
   │  │  │   selects language             │  │   │
   │  │  │   queues speech / interrupts   │  │   │
   │  │  └────────────────────────────────┘  │   │
   │  │              │                       │   │
   │  │              ▼                       │   │
   │  │  ┌────────────────────────────────┐  │   │
   │  │  │ NVDA APIs                       │  │   │
   │  │  │  - speech.speak()              │  │   │
   │  │  │  - braille.handler.message()   │  │   │
   │  │  │  - inputCore (gestures)        │  │   │
   │  │  │  - gui (settings dialog)       │  │   │
   │  │  └────────────────────────────────┘  │   │
   │  │                                      │   │
   │  └──────────────────────────────────────┘   │
   └──────────────────────────────────────────────┘
              │
              │ SSE / HTTP
              ▼
       AAEP Producer
```

The add-on lives entirely within NVDA's process. It uses NVDA's:

- **`speech` module** for spoken output
- **`braille.handler`** for braille display
- **`inputCore`** for custom keyboard gestures
- **`gui`** for the settings dialog
- **`config`** for persisting user preferences
- **`globalPluginHandler`** as the add-on entry point

---

## Project layout

```
nvda-addon-prototype/
├── README.md
├── build_addon.py              # Packages the add-on as .nvda-addon
├── manifest.ini                # NVDA add-on manifest
├── aaep_nvda_subscriber/
│   ├── __init__.py             # globalPluginHandler entry point
│   ├── sse_client.py           # SSE consumer for AAEP /events
│   ├── handler.py              # Event-to-speech translation
│   ├── gestures.py             # NVDA keyboard gesture bindings
│   └── settings.py             # NVDA Preferences integration
└── tests/
    └── test_handler.py
```

---

## Multilingual support

The add-on integrates with the [Multilingual African Languages extension](../../extensions/multilingual-african-languages/). Configure your preferred languages in Preferences:

- `["yo", "en"]` — prefer Yoruba, fall back to English
- `["ha", "en"]` — prefer Hausa, fall back to English
- `["ig", "en"]` — prefer Igbo, fall back to English
- `["en"]` — English only

When the agent emits events with `language: "yo"`, the add-on speaks the Yoruba summary. If the agent emits in a language not in your preference list, the add-on uses the extension's translation tables to render the equivalent in your preferred language (if available).

---

## Production readiness

This prototype demonstrates the integration but is not production-ready in several ways:

| Limitation | Status |
|---|---|
| Single producer at a time | Multi-producer support planned for v0.2 |
| Plain HTTP (no auth) | TLS + bearer token auth planned for v0.2 |
| No reconnection on disconnect | Auto-reconnect with backoff planned for v0.2 |
| English-only configuration UI | Localized UI planned for v1.0 |
| No usage statistics | Privacy-preserving stats planned for v0.2 |
| Limited error recovery | Robust error handling planned for v0.3 |

Production deployment requires resolving these limitations. We're targeting v1.0 of the add-on in Q4 2026 (per the [ROADMAP](../../../governance/ROADMAP.md)) with NVDA add-on store submission to follow.

---

## Contributing

NVDA add-on development requires:

- A Windows machine with NVDA installed
- Familiarity with NVDA's add-on architecture: https://github.com/nvaccess/nvda/blob/master/projectDocs/dev/addons.md
- Python 3.10+ knowledge

To contribute:

1. Read `governance/CONTRIBUTING.md`
2. Open issues for bugs you find or features you want
3. Submit PRs against this directory
4. Test with at least two NVDA versions (current + previous LTS)

We particularly welcome contributions from blind/low-vision developers and the NVDA community.

---

## See also

- [NVDA add-on development docs](https://github.com/nvaccess/nvda/blob/master/projectDocs/dev/addons.md)
- [Subscribers Guide](../../../guides/SUBSCRIBERS_GUIDE.md)
- [`../cli-debug/`](../cli-debug/) — simpler subscriber example to learn from first
- [`../web-subscriber-react/`](../web-subscriber-react/) — browser-based subscriber sibling
- [`../narrator-bridge-prototype/`](../narrator-bridge-prototype/) — Windows Narrator sibling
