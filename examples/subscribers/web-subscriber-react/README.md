# AAEP Web Subscriber (React)

A reference React component that subscribes to AAEP producers and integrates with the browser's accessibility tree via ARIA live regions. Designed for web applications that embed AI agents and need to expose agent activity to assistive technology running in the browser (screen readers like NVDA-in-Firefox, JAWS, VoiceOver, TalkBack).

This is the second reference subscriber, after the [NVDA add-on prototype](../nvda-addon-prototype/). Where that one integrates with native screen readers, this one works in any web browser without additional software installation.

---

## What this subscriber does

When dropped into a React application, the component:

1. **Connects to an AAEP producer's `/events` SSE endpoint** via the browser's `EventSource` API
2. **Announces events through ARIA live regions** that screen readers automatically read aloud
3. **Renders a visible event log** (optional, for sighted observers and debugging)
4. **Handles confirmations and clarifications** with accessible button interfaces
5. **Sends replies back to the producer** via the standard `/messages` endpoint
6. **Selects appropriate ARIA priority** (`polite` for normal events, `assertive` for critical)

The component is keyboard-accessible, screen-reader-friendly, and works in any modern browser without dependencies beyond React.

---

## Why a web subscriber?

Native screen reader integration (the NVDA add-on, future JAWS/VoiceOver/Narrator bridges) is the long-term goal for end users. But there are situations where a web subscriber is more practical:

- **Web applications that embed AI agents.** When the agent runs in a web app, having a built-in AT-friendly UI lets blind users use the app without separately installing AT-specific add-ons.
- **Accessibility testing and demos.** Web developers can verify their agents emit useful AAEP events by running this subscriber in their browser and inspecting the announcements.
- **Education and onboarding.** New developers can experience how AAEP feels from the AT user's perspective without setting up a screen reader.
- **Quick deployment.** No add-on installation, no system-level setup. Visit a URL, see the subscriber working.

This subscriber is complementary to native AT integrations, not a replacement.

---

## Installation

```bash
cd examples/subscribers/web-subscriber-react
npm install
npm run build
```

Requires Node.js 18+ and npm 9+.

The build produces a UMD bundle in `dist/` plus TypeScript definitions. Importable in any React 18+ application:

```bash
npm install @aaep/web-subscriber-react
```

---

## Quick start

```tsx
import { AAEPSubscriber } from "@aaep/web-subscriber-react";

function MyApp() {
  return (
    <div>
      <h1>My AI Assistant</h1>

      <AAEPSubscriber
        endpoint="http://localhost:8080"
        preferredLanguages={["en"]}
        showEventLog={true}
        onConnectionStatus={(status) => console.log("AAEP:", status)}
      />

      {/* The rest of your app */}
    </div>
  );
}
```

Once mounted, the component connects to the producer at the given endpoint and starts announcing events. Screen reader users hear the agent's activity in real time.

---

## Props

| Prop | Type | Default | Description |
|---|---|---|---|
| `endpoint` | `string` | (required) | AAEP producer base URL |
| `preferredLanguages` | `string[]` | `["en"]` | Language preference order |
| `showEventLog` | `boolean` | `false` | Render a visible event log alongside the live regions |
| `maxLogEntries` | `number` | `50` | Maximum events to keep in the visible log |
| `autoStart` | `boolean` | `true` | Connect immediately on mount |
| `onConnectionStatus` | `(status: string) => void` | `undefined` | Callback for connection state changes |
| `onEvent` | `(event: AAEPEvent) => void` | `undefined` | Callback fired for every received event |
| `theme` | `"light" \| "dark" \| "auto"` | `"auto"` | Visual theme for the event log |
| `replyTimeout` | `number` | `30000` | ms before showing timeout warning |

---

## How ARIA integration works

The component renders two `<div role="status" aria-live="..." aria-atomic="true">` elements:

```html
<div role="status" aria-live="polite" aria-atomic="true" id="aaep-polite">
  <!-- Normal-urgency events announced here -->
</div>

<div role="status" aria-live="assertive" aria-atomic="true" id="aaep-assertive">
  <!-- Critical-urgency events (confirmations, errors, handoffs) -->
</div>
```

When the component receives an AAEP event, it updates the appropriate live region. Screen readers detect the change and read the new content aloud.

- **`aria-live="polite"`** — screen reader waits until current speech finishes, then announces
- **`aria-live="assertive"`** — screen reader interrupts current speech to announce immediately
- **`aria-atomic="true"`** — the entire region content is read, not just the changed portion

This is the standard W3C ARIA live region pattern, supported by every modern screen reader.

---

## Confirmation flow

When an `awaiting.confirmation` event arrives, the component:

1. Announces the action via the `assertive` live region
2. Renders an inline confirmation UI:
   ```
   ┌───────────────────────────────────────────┐
   │ Confirm: Send email to alice@example.com  │
   │ This action cannot be easily undone.      │
   │                                             │
   │ [Accept (A)]  [Reject (R)]                 │
   │                                             │
   │ Auto-rejects in 4:58                       │
   └───────────────────────────────────────────┘
   ```
3. Sets keyboard focus to the Accept button (with focus trap until the user responds)
4. Listens for `A` or `R` key presses as shortcuts
5. POSTs the user's decision to `/messages`
6. Removes the UI and resumes normal event flow

The Accept and Reject buttons are real `<button>` elements with proper `aria-label` and `aria-describedby` attributes, so screen reader users navigate them naturally.

---

## Multilingual support

The component reads the event's `language` field and selects the best available translation per `preferredLanguages` prop. When the [Multilingual African Languages extension](../../extensions/multilingual-african-languages/) is configured on the producer side, this component renders Yoruba, Hausa, or Igbo summaries directly.

```tsx
<AAEPSubscriber
  endpoint="http://localhost:8080"
  preferredLanguages={["yo", "en"]}  // Prefer Yoruba, fall back to English
/>
```

For events emitted in English, the component does not attempt translation in the browser (translation tables live on the producer side; the component just renders what the producer emits).

---

## Project layout

```
web-subscriber-react/
├── README.md
├── package.json
├── tsconfig.json
├── src/
│   ├── index.ts                 # Public API exports
│   ├── AAEPSubscriber.tsx       # The React component
│   ├── useAAEPEvents.ts          # Hook for SSE consumption
│   ├── types.ts                 # AAEP event type definitions
│   └── styles.css               # Default styles
├── public/
│   └── demo.html                # Self-contained demo page
└── tests/
    └── AAEPSubscriber.test.tsx
```

---

## Production readiness

This prototype is functional but has known limitations:

- **No authentication.** Producers exposing /events must trust the requesting origin. Add CSRF tokens or signed URLs before production deployment.
- **No reconnection backoff configuration.** The component reconnects on disconnect but doesn't expose tuning knobs yet.
- **Limited mobile testing.** Tested on desktop browsers; mobile screen readers (TalkBack, VoiceOver iOS) may behave slightly differently.
- **No event filtering UI.** All events are announced; future versions will expose filters.
- **Bundle size.** ~24KB minified+gzipped; acceptable for most apps but could be smaller.

For production use, fork this component and adapt to your specific authentication, theming, and accessibility audit requirements.

---

## Browser compatibility

Tested with:

- Chrome 120+ with built-in screen reader
- Firefox 120+ with NVDA
- Safari 17+ with VoiceOver (macOS and iOS)
- Edge 120+ with Narrator

Older browsers may work but aren't validated.

---

## See also

- [W3C ARIA Live Regions specification](https://www.w3.org/TR/wai-aria-1.2/#live_region_roles)
- [`../nvda-addon-prototype/`](../nvda-addon-prototype/) — native Windows screen reader integration
- [`../narrator-bridge-prototype/`](../narrator-bridge-prototype/) — Windows Narrator sibling
- [Subscribers Guide](../../../guides/SUBSCRIBERS_GUIDE.md)
