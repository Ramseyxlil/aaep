# AAEP Narrator Bridge Prototype

A reference Windows bridge that subscribes to AAEP producers and routes events to Microsoft Narrator, the built-in Windows screen reader. Unlike the [NVDA add-on](../nvda-addon-prototype/), this is a standalone bridge process — Narrator does not have a third-party add-on mechanism, so we use Windows UI Automation (UIA) to surface announcements through a hidden window that Narrator monitors.

**Status:** Prototype. Demonstrates the integration pattern; not yet a production deployment artifact. See §"Production readiness" below.

Strategic significance: Narrator ships with every Windows machine. If AAEP works with Narrator, the protocol becomes accessible to hundreds of millions of Windows users without requiring them to install third-party screen readers.

---

## Why a bridge instead of an add-on?

Narrator's architecture differs from NVDA's in two important ways:

| Property | NVDA | Narrator |
|---|---|---|
| Add-on mechanism | First-class (.nvda-addon packages) | None for third parties |
| Speech control | Direct Python API (`speech.speak()`) | Via UIA accessibility tree |
| Modification scope | Add-ons can deeply customize Narrator-style behavior | Apps expose accessibility info; Narrator decides what to read |

Because Narrator can't load custom code, we use the **UI Automation pattern**: this bridge runs as a separate Windows process, exposes a hidden window with proper accessibility properties, and updates that window's accessible text when AAEP events arrive. Narrator (when focused on this window or running automatically with announcement-style features) reads the updated text.

This is the same pattern used by browsers (Edge, Chrome) and other apps that need to announce content to Narrator without being Narrator itself.

---

## What this bridge does

1. **Subscribes to one or more AAEP producers** via SSE
2. **Creates a hidden "announcement" window** with proper UIA accessibility properties
3. **Updates the window's accessible name and live-region property** when events arrive
4. **Plays system notification sounds** for critical events to ensure attention
5. **Provides a tray icon** for connection status and configuration
6. **Logs all events to disk** (optional) for debugging and audit

The bridge is opt-in: users explicitly add producer endpoints in the configuration UI.

---

## Architecture

```
   ┌──────────────────────────────────────────────────┐
   │  Windows host                                      │
   │                                                    │
   │  ┌──────────────────────────────────────────┐    │
   │  │  AAEP Narrator Bridge (standalone proc)   │    │
   │  │                                            │    │
   │  │  ┌──────────────────────────────────┐     │    │
   │  │  │ SSE Client (asyncio + httpx)     │     │    │
   │  │  └──────────────────────────────────┘     │    │
   │  │              │                             │    │
   │  │              ▼                             │    │
   │  │  ┌──────────────────────────────────┐     │    │
   │  │  │ Event Handler (priority routing) │     │    │
   │  │  └──────────────────────────────────┘     │    │
   │  │              │                             │    │
   │  │              ▼                             │    │
   │  │  ┌──────────────────────────────────┐     │    │
   │  │  │ UIA Announcer                    │     │    │
   │  │  │   - Hidden tk window             │     │    │
   │  │  │   - AccessibleObject updates     │     │    │
   │  │  │   - Live region notifications    │     │    │
   │  │  └──────────────────────────────────┘     │    │
   │  │              │                             │    │
   │  └──────────────┼─────────────────────────────┘    │
   │                 │                                  │
   │                 ▼                                  │
   │  ┌──────────────────────────────────────────┐    │
   │  │  Narrator (Windows built-in SR)           │    │
   │  │  Reads accessible text via UIA            │    │
   │  └──────────────────────────────────────────┘    │
   └──────────────────────────────────────────────────┘
```

The bridge runs as a regular user-space process. Narrator (which runs at a privileged level for some interactions) picks up announcements via Windows' built-in accessibility tree — no special permissions required.

---

## Installation

### Requirements

- Windows 10 (version 2004+) or Windows 11
- Python 3.10+
- Narrator enabled (`Settings → Accessibility → Narrator → Turn on Narrator`)

### Install

```powershell
cd examples\subscribers\narrator-bridge-prototype
pip install -e .
```

Optional dependencies:

```powershell
pip install -e .[ui]      # System tray icon and config GUI
pip install -e .[uia]     # Production UIA via pywin32 (Windows-only)
```

### Run

```powershell
aaep-narrator-bridge --endpoint http://localhost:8080
```

The bridge runs in the background. When AAEP events arrive, Narrator announces them. Press `Ctrl+C` in the terminal to stop.

---

## Quick start

In one terminal, start an AAEP producer:

```powershell
python -m aaep_minimal_producer.server --port 8080
```

In another terminal, start the bridge:

```powershell
aaep-narrator-bridge --endpoint http://localhost:8080 --verbose
```

Make sure Narrator is on (Windows key + Ctrl + Enter to toggle). Then trigger an event:

```powershell
curl -X POST http://localhost:8080/sessions ^
    -H "Content-Type: application/json" ^
    -d "{\"user_message\": \"Send an email to alice@example.com\"}"
```

Narrator should announce the agent's activity in real time, including critical confirmations.

---

## Configuration

The bridge reads configuration from `%APPDATA%\aaep-narrator-bridge\config.json` (created with defaults on first run):

```json
{
  "endpoints": ["http://localhost:8080"],
  "preferred_languages": ["en"],
  "announce_normal_events": true,
  "announce_progress": false,
  "play_critical_chime": true,
  "log_file_path": null,
  "auto_connect_on_start": true
}
```

CLI flags override config file values.

---

## Confirmation flow

Narrator's UIA-based integration is fundamentally different from NVDA's direct gesture access. Confirmation gestures route through:

1. The bridge displays a small **modal-style dialog window** with proper UIA semantics (role=dialog, accessibility name, focus)
2. The dialog has `[Accept]` and `[Reject]` buttons with keyboard shortcuts
3. When the user presses Accept or Reject, the bridge sends the reply to the producer
4. Narrator naturally announces the dialog contents because Windows' accessibility tree exposes them

This means confirmations briefly pop a UI window. For unattended deployments, set `auto_reject_after_seconds` in config to fall through with the safe default.

---

## Limitations

Narrator integration has inherent constraints we can't work around:

- **No deep customization.** We can't change how Narrator pronounces things, control speech rate per event, or override Narrator's verbosity settings.
- **Announcement timing depends on Narrator's behavior.** Narrator may queue, interrupt, or skip announcements based on user settings we cannot inspect.
- **No braille output integration.** Braille support requires lower-level integration than UIA provides.
- **Focus-dependent behavior.** Some Narrator features only work when our window has focus, which steals focus from the user's actual work.

For users who need richer integration, the [NVDA add-on](../nvda-addon-prototype/) provides deeper control. The Narrator bridge is positioned for users who can't or don't want to install third-party screen readers.

---

## Production readiness

This prototype is a demonstration, not a production artifact. Known gaps:

| Limitation | Plan |
|---|---|
| Tk-based hidden window (heavy dependency) | Switch to a Win32 hidden window with raw UIA in v0.2 |
| No installer | Build MSI installer with WIX in v1.0 |
| No code signing | Add Authenticode signature in v1.0 |
| Limited UIA testing | Validate against Inspect.exe and Accessibility Insights in v0.3 |
| No automatic update mechanism | Add Squirrel.Windows update support in v1.0 |
| Single producer | Multi-producer support in v0.2 |

Target: v1.0 production release with Microsoft Store submission in Q1 2027 (per the [ROADMAP](../../../governance/ROADMAP.md)).

---

## Future: Narrator-native AAEP support

The long-term goal is for Microsoft to add native AAEP support to Narrator, eliminating the need for this bridge. Such an integration would:

- Subscribe to AAEP producers directly without the UIA workaround
- Use Narrator's full speech and braille capabilities natively
- Honor Narrator's user settings (rate, verbosity, voice)
- Surface AAEP confirmations through Narrator's input gesture system

This bridge serves as a **proof of integration concept** that a Microsoft Accessibility team can use when evaluating native support. The implementation demonstrates the value, identifies the integration points, and provides a working reference.

If you're at Microsoft and interested in native AAEP support for Narrator, we'd welcome a conversation: Abdulrafiu@izusoft.tech.

---

## Project layout

```
narrator-bridge-prototype/
├── README.md
├── pyproject.toml
├── aaep_narrator_bridge/
│   ├── __init__.py
│   ├── bridge.py            # Main subscriber loop
│   ├── announcer.py         # UIA announcement window
│   └── handler.py           # AAEP event → Narrator routing
└── tests/
    └── test_handler.py
```

---

## See also

- [Windows UI Automation overview](https://learn.microsoft.com/en-us/windows/win32/winauto/entry-uiauto-win32)
- [Narrator user guide](https://support.microsoft.com/windows/complete-guide-to-narrator-e4397a0d-ef4f-b386-d8ae-c172f109bdb1)
- [`../nvda-addon-prototype/`](../nvda-addon-prototype/) — third-party screen reader subscriber
- [`../web-subscriber-react/`](../web-subscriber-react/) — browser-based subscriber
- [`../cli-debug/`](../cli-debug/) — simplest reference subscriber
