# AAEP Website

Source for **https://aaep-protocol.org** — the public-facing site for the Agent Accessibility Event Protocol.

This directory contains the static site source. The deployed site is the result of running the build (see §4 below).

---

## What's hosted here

The website serves three primary functions:

1. **Landing page** — explains AAEP to first-time visitors with concrete examples
2. **Canonical specification URLs** — the spec is referenced from code via stable URLs hosted here
3. **Canonical schema URLs** — JSON Schemas live at versioned URLs that producers and validators reference

Schemas are hosted at the canonical path `https://aaep-protocol.org/schemas/v1/` and these URLs are baked into the schemas themselves (the `$id` field). Moving the schemas to a different host would break every implementation that validates against them. **The URL contract is permanent for the v1.x series.**

---

## Directory structure

```
website/
├── README.md                      # This file
├── build.sh                       # Build script (copies sources to dist/)
├── src/
│   ├── index.html                 # Landing page
│   ├── 404.html                   # Custom 404 with helpful navigation
│   ├── styles/
│   │   └── main.css               # All site styles (accessibility-first)
│   ├── schemas/v1/                # Canonical schema mount point
│   │   └── (synced from /schemas/v1/ during build)
│   └── spec/                      # Rendered spec
│       └── (synced from /spec/ during build, markdown → HTML)
└── dist/                          # Build output (gitignored)
```

The website is intentionally simple. We use plain HTML for the landing page (no framework), CSS for styling (no preprocessor), and a small bash build script. This makes the site:

- Easy to audit for accessibility
- Easy to deploy to GitHub Pages or any static host
- Easy to maintain across maintainer transitions
- Resistant to JS framework churn

---

## Accessibility commitment

The site itself is designed with accessibility as a primary requirement. It conforms to:

- **WCAG 2.1 Level AA** (currently; aiming for Level AAA in v1.1)
- **No JavaScript required** for the landing page content
- **Semantic HTML** with proper heading hierarchy
- **High-contrast color schemes** with `prefers-color-scheme` support
- **Keyboard navigation** for all interactive elements
- **Skip links** for screen reader users to bypass repetitive navigation
- **Plain language** in the landing copy (we'd rather be accurate than impressive)

If you find an accessibility issue with the site, please open an issue — that's a bug, not a feature request.

---

## Building locally

Requirements:
- bash (any modern POSIX shell)
- Python 3.10+ (for markdown rendering via `markdown` package)

```bash
cd website
./build.sh
```

The output goes to `website/dist/`. Open `dist/index.html` in a browser to preview.

To rebuild on file changes:

```bash
# Watch mode (requires entr or fswatch)
find src/ ../spec/ ../schemas/ | entr ./build.sh
```

---

## Deployment

The site deploys to GitHub Pages via the workflow in `.github/workflows/deploy-website.yml`. On every push to `main`:

1. The build script runs
2. The output is published to the `gh-pages` branch
3. GitHub Pages serves it from `https://aaep-protocol.org`

Custom domain configuration is in `dist/CNAME` (containing `aaep-protocol.org`).

---

## URL stability commitments

The following URLs are guaranteed stable for the entire v1.x lifetime:

| URL | Content |
|---|---|
| `https://aaep-protocol.org/schemas/v1/envelope.json` | Envelope schema |
| `https://aaep-protocol.org/schemas/v1/events/<event_type>.json` | Event-specific schemas |
| `https://aaep-protocol.org/schemas/v1/handshake/<message_type>.json` | Handshake schemas |
| `https://aaep-protocol.org/schemas/v1/context/<type>.json` | Context object schemas |

Each schema's `$id` field references its own URL. Validators dereference these URLs to load the schema. **Breaking these URLs breaks every conformance test in every implementation.** They are not URLs to change casually.

Additional URLs (not stability-guaranteed but expected to remain available):

| URL | Content |
|---|---|
| `https://aaep-protocol.org/` | Landing page |
| `https://aaep-protocol.org/spec/` | Specification index |
| `https://aaep-protocol.org/spec/<chapter>.html` | Individual chapters |
| `https://aaep-protocol.org/guides/` | Guides index |
| `https://aaep-protocol.org/security-team.asc` | PGP key for security reports |

---

## Future plans

| Feature | Target |
|---|---|
| Interactive schema browser | v1.1 (Q4 2026) |
| Conformance certificate verification page | v1.2 (Q1 2027) |
| Multilingual landing page (Yoruba, Hausa, Igbo first) | v1.2 (Q1 2027) |
| Search across spec and guides | v1.3 (Q2 2027) |
| Live event stream demo | v1.4 (Q3 2027) |

Per the [ROADMAP](../governance/ROADMAP.md).

---

## See also

- [`../spec/`](../spec/) — markdown source for the specification
- [`../schemas/v1/`](../schemas/v1/) — JSON Schemas (the originals)
- [`../guides/`](../guides/) — markdown source for the guides
- [`../.github/workflows/deploy-website.yml`](../.github/workflows/) — deployment workflow
