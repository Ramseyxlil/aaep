# AAEP Adopters

This document lists organizations using AAEP in production, evaluating it for production use, or publicly endorsing the protocol. It serves two purposes:

1. **For prospective adopters:** see who else is using AAEP and how, to inform your own evaluation
2. **For the project:** track real-world adoption to inform roadmap priorities and governance transitions

This list is honest about current state. We do not pad it with aspirational entries, friend organizations, or vendors who said nice things without actually integrating. Adding an organization requires the criteria below.

---

## Current state (v1.0.0 launch)

**AAEP was published on June 30, 2026.** As of launch, this list is intentionally empty in the "Production" and "Evaluating" sections. Real adoption takes time, and we'd rather start empty and grow than start padded and lose credibility.

The project's own reference implementations (cli-debug, NVDA add-on prototype, MCP bridge, OTEL bridge, web React subscriber, Narrator bridge prototype) are listed as **Reference implementations** in their own section, not as external adopters.

If your organization is evaluating AAEP and you're willing to be listed, see the process in §4 below.

---

## 1. Production users

Organizations using AAEP in shipped products serving real users.

(none yet)

When entries appear here, each will follow this template:

```
### Organization Name
- **Use case:** What they're using AAEP for
- **Deployment scale:** Approximate number of agents or sessions
- **In production since:** YYYY-MM
- **Implementations:** Languages and stacks
- **Public reference:** Link to a blog post, case study, or product page
- **Contact:** Public point of contact (if listed)
```

---

## 2. Evaluating / piloting

Organizations actively evaluating AAEP through documented pilot programs.

(none yet)

When entries appear here, each will follow this template:

```
### Organization Name
- **Stage:** Internal proof-of-concept | Limited pilot | Broad pilot
- **Started:** YYYY-MM
- **Expected production decision:** YYYY-MM (or "ongoing")
- **Scope:** What they're piloting
- **Public reference:** Optional
```

---

## 3. Public supporters

Organizations and individuals who have publicly endorsed AAEP or contributed substantively to its development without yet deploying it in production.

(none yet)

Supporter listings document endorsement and contribution. They don't claim production usage.

---

## 4. Reference implementations

These are the implementations shipped with AAEP v1.0.0. They demonstrate the protocol but are not external adoption.

### Producers
- python-minimal — Simple AAEP producer for any Python agent
- python-langchain — LangChain integration adapter
- python-anthropic-sdk — Anthropic Claude SDK integration
- python-microsoft-agent-framework — Microsoft Agent Framework integration
- typescript-minimal — TypeScript/Node.js producer

### Subscribers
- cli-debug — Terminal-based debugging subscriber
- nvda-addon-prototype — NVDA screen reader add-on
- web-subscriber-react — Browser-based React component
- narrator-bridge-prototype — Microsoft Narrator bridge

### Bridges
- mcp-aaep-bridge — Model Context Protocol ↔ AAEP
- opentelemetry-aaep-bridge — AAEP → OpenTelemetry

### Extensions
- multilingual-african-languages — Yoruba, Hausa, Igbo
- medical-hipaa — HIPAA-aware healthcare profile

All reference implementations are maintained by the AAEP project under MIT license.

---

## 5. How to be added

To be listed in the **Production** section, your organization must:

1. **Be using AAEP in a shipped product** with real (non-test) users
2. **Have implemented at least Conformance Level 2** (verified via the conformance suite)
3. **Provide a public reference** (blog post, product page, conference talk, or similar)
4. **Provide a contact** (organization-level, not personal)
5. **Open a PR** adding your entry to this document

To be listed in the **Evaluating** section, your organization must:

1. **Have an active pilot or proof-of-concept** with internal users or limited external users
2. **Be willing to share the evaluation outcome** (publicly or privately to the project)
3. **Have a designated person at your organization** as contact
4. **Open a PR** adding your entry

To be listed in **Public supporters**, your organization must:

1. **Have a public endorsement** (signed statement, press release, conference talk, or similar) OR
2. **Have substantively contributed** to the protocol (multiple PRs, ACP authoring, security disclosure)
3. **Open a PR** adding your entry

We do not require corporate sponsorship for any listing. Membership is free and based on actual usage or contribution, not financial commitment.

---

## 6. Removal from the list

Organizations may be removed from this list:

- **At their own request** — open a PR or email `maintainers@aaep-protocol.org`
- **Automatically** if they stop using AAEP and notify the project
- **By the Steering Committee** if a listing is determined to be inaccurate (this requires a formal review per [`GOVERNANCE.md`](./GOVERNANCE.md) §8)

We do not remove organizations because they criticize AAEP or because they switch to a different protocol. Removal is about accuracy, not punishment.

---

## 7. Privacy considerations

This document is public. Organizations control what they share about their deployment, including:

- Whether to list themselves at all (we do not list organizations without their consent)
- What level of detail to provide (use case is recommended; deployment scale is optional)
- Whether to include a personal contact name (an org-level contact is fine)

The project does not track adoption beyond what organizations voluntarily disclose. We don't deploy analytics in the protocol itself; the only way we know an organization is using AAEP is if they tell us.

---

## 8. Statistics

For transparency, we'll publish quarterly aggregate statistics here once the list has 5 or more entries:

- Total adopters
- Geographic distribution (continents, not specific countries)
- Sector distribution (broad categories: healthcare, education, finance, etc.)
- Deployment scale ranges

Pre-5-entry stats are noise; we'll wait until the numbers mean something.

---

## Why honesty matters here

It's tempting for new protocols to inflate adoption claims — listing organizations as "users" when they've only attended a meeting, or counting reference implementations as "production deployments." We don't do this.

The reason: procurement officers, security auditors, and journalists check these lists. A discovered exaggeration damages credibility far more than starting with zero. By keeping this list honest, we make the entries that eventually appear here more credible than they'd be in an inflated list.

If you're evaluating AAEP and looking at this list at v1.0.0 launch, please understand: the protocol is new. The reference implementations work. The governance is honest. The list grows from here.

Your decision to adopt AAEP isn't about who's already using it — it's about whether the protocol solves a problem you have. Talk to us, run a pilot, see if it works. If it does, you can be the first entry in the Production section.
