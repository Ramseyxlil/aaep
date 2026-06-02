# Contributing to AAEP

We welcome contributions from everyone. This document explains how to participate effectively.

Before contributing, please read:

- [`GOVERNANCE.md`](./GOVERNANCE.md) — the governance model and decision processes
- [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md) — our community norms

If you're new to open source, see §10 below for a first-time contributor walkthrough.

---

## 1. Quick start

```bash
# Clone the repository
git clone https://github.com/Ramseyxlil/aaep.git
cd aaep

# Set up the Python dev environment
python -m venv .venv
source .venv/bin/activate    # On Windows: .venv\Scripts\activate
pip install -e ./conformance[dev]
pip install -e ./tools/aaep-tools[dev]
pip install -e ./examples/producers/python-minimal[dev]

# Set up the TypeScript dev environment (only if working on TS examples)
cd examples/producers/typescript-minimal
npm install
cd ../../..

# Run the full test suite
pytest conformance/
pytest tools/aaep-tools/
pytest examples/producers/python-minimal/

# Validate the JSON Schemas
python -c "
import json, jsonschema
from pathlib import Path
for path in Path('schemas/v1').rglob('*.json'):
    schema = json.loads(path.read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    print(f'OK {path}')
"
```

If any of these steps fail on a clean checkout, that's a bug. Please file an issue.

---

## 2. What can I contribute?

| Type of contribution | What it looks like |
|---|---|
| Bug report | A clear description of unexpected behavior with a reproduction |
| Bug fix | A pull request that resolves a filed issue |
| Documentation improvement | Clearer explanations, better examples, fixes to inaccuracies |
| Translation | Translating documentation or example summaries to other languages |
| Reference implementation | A new example producer, subscriber, or bridge |
| Conformance test | A new test for already-specified behavior |
| Extension proposal | A new optional extension via the ACP process |
| Core protocol change | A schema change or new event type via the ACP process |

The first six can typically be done through normal pull requests. The last two require an ACP (see §6 below and [`GOVERNANCE.md`](./GOVERNANCE.md) §4).

---

## 3. Issue reports

Good issues include:

- A clear, descriptive title
- What you expected to happen
- What actually happened
- Steps to reproduce, including a minimal code example if applicable
- Your environment: AAEP version, Python or Node version, OS
- For accessibility-related issues: which AT, which AT version, which agent

If you're not sure whether something is a bug or a feature request, file it as an issue and we'll triage. Don't apologize for asking; we'd rather over-triage than miss bug reports.

For security issues, see [`SECURITY.md`](./SECURITY.md). **Do not file security issues publicly.**

---

## 4. Pull requests

### 4.1 Before you start

For small changes (typos, docs, single bug fixes), file the PR directly. For larger changes, open an issue or discussion first to confirm the direction. This avoids wasted work.

For protocol changes (schemas, event types, conformance levels), please file an ACP first. The ACP can be a draft proposal that we iterate on together.

### 4.2 Branch naming

```
fix/short-description           # bug fixes
feat/short-description          # new features
docs/short-description          # documentation
refactor/short-description      # code restructuring with no behavior change
acp-NNNN/short-description      # implementation of an accepted ACP
```

### 4.3 Commit messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
fix(emitter): correctly redact API keys with hyphens
feat(conformance): add Level 3 handshake check
docs(spec): clarify default_decision for reversible_with_effort
refactor(schemas): consolidate duplicate enum definitions
test(replay): cover --loop with multiple subscribers
chore(deps): bump httpx to 0.27.0
```

Each commit message must:

- Have a type prefix (`fix`, `feat`, `docs`, `refactor`, `test`, `chore`)
- Include a scope in parentheses (the directory or module touched)
- Be in the imperative mood ("add" not "added")
- Stay under 72 characters in the subject line
- Have a blank line before any body paragraph

For breaking changes, add `BREAKING CHANGE:` in the commit body and reference the relevant ACP.

### 4.4 Sign-off

All commits must be signed off with the Developer Certificate of Origin (DCO):

```bash
git commit -s -m "fix(emitter): correctly redact API keys with hyphens"
```

The `-s` flag adds a `Signed-off-by: Your Name <your@email>` line. This certifies that you wrote the change yourself or have the right to contribute it. See https://developercertificate.org for the full text.

### 4.5 PR review

Reviews check:

- **Correctness** — does the change do what it claims?
- **Tests** — are there tests for the new behavior?
- **Documentation** — are user-facing docs updated?
- **Style** — does it match the language's conventions and ours?
- **Accessibility implications** — does this change anything an AT user would notice?

We aim to acknowledge new PRs within 7 days and provide a first review within 14 days. Reviews may request changes. Please don't take this personally; reviews are about the code, not the contributor.

A PR is ready to merge when:

1. All CI checks pass.
2. The PR has approval per the decision tier in [`GOVERNANCE.md`](./GOVERNANCE.md) §3.
3. All review comments are resolved or explicitly deferred.
4. The DCO sign-off is present on every commit.

### 4.6 What we won't accept

These get declined regardless of how well-written they are:

- Removal of accessibility-related behavior without ACP approval
- Changes that break declared conformance guarantees in the current major version
- Additions that increase complexity without clear benefit
- Style-only refactoring of code we're satisfied with
- "Trivially correct" formatting changes that touch dozens of files in one PR
- Generated documentation translation (machine translation is fine as a *starting point* but must be reviewed by a fluent speaker)
- Re-licensing or copyright modifications

If you're unsure whether your change falls into one of these categories, open an issue first.

---

## 5. Code style

### 5.1 Python

- Format with `ruff format`. Configuration is in `pyproject.toml`.
- Lint with `ruff check`. Run before pushing.
- Type-hint public functions and methods. We use `mypy --strict` on the conformance suite and CLI tools.
- Docstrings on all public APIs. Use the format you find in the existing code (terse imperative summary, blank line, paragraph of detail).
- Prefer explicit imports over `*`.
- Don't use `print()` in library code; use `logging`.

### 5.2 TypeScript

- Format with `prettier`. Configuration in `.prettierrc`.
- Type-check with `tsc --noEmit` in strict mode. We use the strict settings shown in the typescript-minimal example.
- Prefer named exports over default exports for clarity.
- Don't disable strict checks via `// @ts-ignore` without a comment explaining why.

### 5.3 JSON Schema

- Indent 2 spaces.
- Property order: `$schema`, `$id`, `title`, `description`, `type`, then alphabetical for the rest.
- Every schema has a `$schema` and `$id`.
- Required fields are listed in the order they appear in the property definitions, not alphabetically.
- Use `description` liberally; subscribers may surface these to users.

### 5.4 Markdown

- One sentence per line in source files (helps git diffs).
- 80-character soft limit; longer is OK if it improves readability.
- Use ATX-style headers (`#`, `##`, etc.), not setext.
- Link to other docs with relative paths, not absolute URLs.

---

## 6. Writing ACPs

ACPs are how significant changes get proposed and adopted. The full process is in [`GOVERNANCE.md`](./GOVERNANCE.md) §4. The template is in [`proposals/template.md`](./proposals/template.md).

### 6.1 When to write an ACP

You need an ACP if your change:

- Adds, removes, or modifies any field in a schema
- Adds, removes, or modifies any event type
- Adds a new conformance level or changes an existing one
- Adds a new bridge to another protocol
- Changes the CLI contract of one of the official tools
- Modifies any "MUST" or "SHALL" requirement in the specification

You do **not** need an ACP for:

- Bug fixes that bring implementations into compliance with the existing spec
- Documentation clarifications that don't change meaning
- New reference examples
- New conformance tests for already-specified behavior

If you're unsure, ask in an issue.

### 6.2 What makes a good ACP

Strong ACPs share these traits:

1. **Concrete problem statement.** Not "X would be nice." Instead: "Users with cognitive disabilities cannot adjust verbosity per-session; the current spec requires global setting changes."
2. **Specific proposed change.** With actual schema snippets, event examples, and field definitions.
3. **Alternatives considered.** What other approaches were rejected, and why.
4. **Accessibility implications.** Which AT user groups are affected; whether anyone is disadvantaged.
5. **Backward compatibility analysis.** Does this break existing implementations? If so, how is migration handled?
6. **Reference implementation pointer.** Either a PR demonstrating the change, or a clear statement that one will be produced before Final status.

ACPs without an accessibility implications section are returned to the author without review. This is the one section we never bypass.

### 6.3 ACP discussion etiquette

- Keep discussion on the PR. Don't move to private channels.
- Substantively engage with disagreement. "I disagree" is not a review.
- The author may revise the proposal in response to feedback. Significant revisions reset the discussion clock.
- If consensus seems unreachable, the working group chair or a Maintainer may call for a structured vote per [`GOVERNANCE.md`](./GOVERNANCE.md) §3.
- Avoid pile-on. If three people have already made the same point, one more "+1" doesn't help.

---

## 7. Documentation contributions

Documentation matters as much as code. We especially welcome:

- Clearer explanations of confusing sections in the specification
- Worked examples for things the implementer's guide currently glosses over
- Translations into languages where AAEP could broaden access
- Tutorials and walkthroughs that complement the formal documentation

Docs follow the same review process as code. We use the Diataxis framework (tutorials, how-tos, reference, explanation) loosely — each piece of documentation should be obviously one of these four types.

### 7.1 Translation contributions

We welcome translations of:

- The implementer's guide
- The quickstart guide
- Specification appendices (the formal spec body is canonical English only, per W3C tradition)
- README files
- Localized strings in the multilingual extension

Translation contributions must:

- Be done by a fluent speaker of the target language (machine translation is OK as a starting point only)
- Preserve any code samples and technical terms unchanged
- Add the translator's name to the document's frontmatter
- Be reviewed by a second fluent speaker if available

We particularly welcome translations into Yoruba, Hausa, Igbo, Arabic, Swahili, Hindi, and other widely-spoken languages currently underserved by accessibility documentation.

---

## 8. Conformance test contributions

The conformance suite is what makes AAEP a real standard rather than a vague proposal. We welcome new tests for:

- Edge cases of already-specified behavior
- Specific producer or subscriber patterns
- Cross-language compatibility scenarios
- Stress and load conditions

Test contributions follow the same review process as code. Tests must:

- Have a clear, descriptive name
- Test exactly one behavior
- Pass on all current reference implementations
- Cite the specification section they validate
- Include a one-line docstring summarizing what's being tested

Tests that break existing reference implementations are not bugs in the implementations; they're either bugs in the test or evidence that an ACP is needed.

---

## 9. Communication

| Channel | Purpose |
|---|---|
| GitHub Issues | Bug reports, feature requests |
| GitHub Discussions | Open-ended technical discussion |
| GitHub Pull Requests | Code, documentation, and ACP submissions |
| Email: discuss@aaep-protocol.org | Mailing list for protocol discussions (subscription via GitHub Discussions) |
| Email: security@aaep-protocol.org | Security disclosures (see [`SECURITY.md`](./SECURITY.md)) |

We are intentionally NOT using Slack, Discord, or other realtime chat. Asynchronous discussion produces better-considered proposals and reduces the burden on contributors in different time zones.

Working groups may use their own communication channels documented in their charters.

---

## 10. First-time contributors

If you've never contributed to open source before, you're welcome here. Try this path:

1. **Read an existing issue or PR** to see how contributions look. Look for issues labeled `good first issue`.
2. **Fork the repository** to your GitHub account.
3. **Make a small change** — fixing a typo, improving a code comment, adding a clarifying sentence to a doc. The change being small makes it easy to focus on the process rather than the content.
4. **Push your fork and open a PR** against the main branch. Add the `-s` flag to your commit for DCO sign-off.
5. **Wait for review.** A Maintainer will respond, typically within 7 days. The response might be "looks great, merging" or it might be "please fix these few things." Either is normal and expected.
6. **Iterate as needed.** Push additional commits to your branch; they'll automatically update the PR.
7. **Celebrate when it merges.** Your name is in the commit log of an accessibility standard. That's a real thing you did.

After your first PR, the second is easier. After the fifth, you might be invited to become a Reviewer. After sustained engagement, you might be invited to become a Maintainer. The path is open.

---

## 11. Recognition

Contributors are recognized in:

- The git commit history (your name on every commit)
- `CHANGELOG.md` entries for significant changes
- `MAINTAINERS.md` for sustained Maintainer-level contribution
- The acknowledgments section of any specification document you substantially contributed to

We don't use point systems, badges, or contributor leaderboards. We do recognize meaningful work by name in the documentation it produced.

---

## 12. Questions?

- For technical questions, open a GitHub Discussion.
- For governance questions, email discuss@aaep-protocol.org or open a Discussion.
- For commercial inquiries (commercial support, custom development, partnership), email Abdulrafiu@izusoft.tech.
- For Code of Conduct concerns, see [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md).

Thank you for considering contributing to AAEP. The protocol exists to make agents accessible to everyone; that work depends on you.
