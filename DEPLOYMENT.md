# AAEP v1.0.0 Launch Playbook

This document is the operational guide for taking AAEP from this repository to a live, public protocol at `https://aaep-protocol.org` and `https://github.com/Ramseyxlil/aaep`. Follow it step-by-step. The launch date is **June 30, 2026**.

You are reading the launch playbook. Read it once end-to-end before executing any step, then work through it in order.

---

## Table of contents

1. [Pre-flight verification](#1-pre-flight-verification)
2. [License finalization](#2-license-finalization)
3. [GitHub repository setup](#3-github-repository-setup)
4. [First commit and push](#4-first-commit-and-push)
5. [GitHub Pages activation](#5-github-pages-activation)
6. [DNS configuration for aaep-protocol.org](#6-dns-configuration-for-aaep-protocolorg)
7. [GitHub Actions enablement](#7-github-actions-enablement)
8. [PyPI publishing](#8-pypi-publishing)
9. [npm publishing](#9-npm-publishing)
10. [Pre-launch checklist (T-30 to T-1)](#10-pre-launch-checklist-t-30-to-t-1)
11. [Launch day (June 30, 2026)](#11-launch-day-june-30-2026)
12. [Announcement strategy (T+0 to T+30)](#12-announcement-strategy-t0-to-t30)
13. [Post-launch monitoring](#13-post-launch-monitoring)

---

## 1. Pre-flight verification

Before doing anything else, verify the repository is complete.

### Run the conformance suite

```bash
cd conformance/aaep_conformance
pip install -e .[dev]
pytest -v
```

Expected: all tests pass. If any fail, do not proceed.

### Build the website locally

```bash
cd website
./build.sh --clean
```

Expected: `Build complete.` with 39 rendered pages.

### Check schema URL consistency

```bash
python3 -c "
from pathlib import Path
import json
ok = True
for p in Path('schemas/v1').rglob('*.json'):
    schema = json.loads(p.read_text())
    expected = 'https://aaep-protocol.org/schemas/v1/' + str(p.relative_to('schemas/v1'))
    if schema.get('\$id') != expected:
        print(f'MISMATCH: {p}')
        ok = False
print('OK' if ok else 'FIX SCHEMAS BEFORE LAUNCH')
"
```

### Verify file totals

```bash
find . -type f | wc -l         # Should be ~283 (including __init__.py, fixtures, etc.)
find . -type f -name "*.md" | wc -l   # Should be ~80+ markdown files
find . -type f -name "*.py" | wc -l   # Should be ~50+ Python files
```

### Check for placeholder strings

```bash
grep -r "TODO\|FIXME\|XXX\|PLACEHOLDER" --include="*.md" --include="*.py" --include="*.yml" .
```

Any matches must be reviewed and either resolved or explicitly marked as future work.

---

## 2. License finalization

**Critical:** the `LICENSE-CC-BY-4.0` file currently contains placeholder text. You must replace it with the canonical license text before publishing.

### Replace LICENSE-CC-BY-4.0

1. Visit https://creativecommons.org/licenses/by/4.0/legalcode.txt
2. Copy the entire license text
3. Replace the contents of `LICENSE-CC-BY-4.0` with the canonical text
4. Verify the file contains the exact phrase: *"Creative Commons Attribution 4.0 International Public License"*

### Verify LICENSE-MIT

The MIT license file should be the standard MIT text with copyright line:

```
Copyright (c) 2026 Abdulrafiu Izuafa
```

If it's missing or different, replace with the canonical MIT text from https://opensource.org/license/mit.

### Verify root LICENSE file

The root `LICENSE` file should be a dual-license notice pointing to both `LICENSE-MIT` (for code) and `LICENSE-CC-BY-4.0` (for specification text).

---

## 3. GitHub repository setup

### Create the repository

1. Visit https://github.com/new
2. **Owner:** `Ramseyxlil`
3. **Repository name:** `aaep`
4. **Description:** `Agent Accessibility Event Protocol — an open standard for AI agents to communicate with assistive technology`
5. **Visibility:** Public
6. **Initialize:** Do NOT initialize with README, LICENSE, or .gitignore (we have these locally)
7. Click **Create repository**

### Configure repository settings

Navigate to **Settings → General**:

- **Default branch:** `main`
- **Features:**
  - ✅ Issues
  - ✅ Discussions
  - ✅ Projects
  - ❌ Wiki (we use the website instead)
- **Pull requests:**
  - ✅ Allow squash merging (default)
  - ❌ Allow merge commits
  - ❌ Allow rebase merging
  - ✅ Automatically delete head branches

Navigate to **Settings → Branches → Add branch protection rule** for `main`:

- ✅ Require a pull request before merging
- ✅ Require approvals: 1
- ✅ Dismiss stale pull request approvals
- ✅ Require status checks to pass:
  - `Conformance gate`
  - `Validate JSON schemas`
  - `Spec build / Build website`
- ✅ Require branches to be up to date
- ✅ Require linear history
- ✅ Include administrators (yes — even you)

Navigate to **Settings → Discussions**:

- Enable Discussions
- Create categories: `Announcements`, `Q&A`, `Show and tell`, `Ideas`, `General`

---

## 4. First commit and push

From the repository root:

```bash
cd /path/to/aaep

# Initialize git
git init
git branch -m main

# Configure user (use the email associated with your GitHub account)
git config user.name "Abdulrafiu Izuafa"
git config user.email "Abdulrafiu@izusoft.tech"

# Stage everything
git add .

# Verify what will be committed
git status

# Initial commit with DCO sign-off
git commit -s -m "Initial commit: AAEP v1.0.0

The Agent Accessibility Event Protocol v1.0.0 release.

- 17-chapter specification + 4 appendices
- 21 JSON schemas with canonical URLs
- 3-level conformance suite
- 13 reference implementations (5 producers, 4 subscribers, 2 bridges, 2 extensions)
- 3 CLI tools
- 12 governance documents + 2 ACPs
- Full website source

Signed-off-by: Abdulrafiu Izuafa <Abdulrafiu@izusoft.tech>"

# Add remote
git remote add origin https://github.com/Ramseyxlil/aaep.git

# Push
git push -u origin main
```

After the push, verify on GitHub that all 283 files appear in the web UI.

### Tag the release

```bash
git tag -a v1.0.0 -m "AAEP v1.0.0 — initial public release

Released June 30, 2026.

5-year full support through June 2031.
2 additional years of security-only maintenance through June 2033.

See CHANGELOG.md for the complete v1.0.0 contents."

git push origin v1.0.0
```

Navigate to **Releases → Draft a new release**, choose the `v1.0.0` tag, paste the CHANGELOG.md `[1.0.0]` section as the description, and publish.

---

## 5. GitHub Pages activation

Navigate to **Settings → Pages**:

1. **Source:** GitHub Actions (NOT "Deploy from a branch" — we use our `publish-website.yml` workflow)
2. **Custom domain:** Leave empty for now (we set this after DNS)
3. **Enforce HTTPS:** Will be enabled automatically after DNS verification

The first push to `main` should trigger the `Publish Website` workflow automatically. Watch its progress in **Actions**.

If it fails, check:

- That `publish-website.yml` has the right permissions block (`pages: write`, `id-token: write`)
- That GitHub Pages source is set to "GitHub Actions"
- The build logs for any path or markdown rendering errors

After successful first deploy, the site is reachable at `https://ramseyxlil.github.io/aaep/`. We change to `aaep-protocol.org` after DNS.

---

## 6. DNS configuration for aaep-protocol.org

You should already own `aaep-protocol.org` from earlier in the project. If not, register it at any reputable registrar (Namecheap, Porkbun, Cloudflare Registrar). Cost: ~$15/year.

### Required DNS records

At your DNS provider, add these records:

| Type | Name | Value | TTL |
|---|---|---|---|
| A | `@` | `185.199.108.153` | 300 |
| A | `@` | `185.199.109.153` | 300 |
| A | `@` | `185.199.110.153` | 300 |
| A | `@` | `185.199.111.153` | 300 |
| AAAA | `@` | `2606:50c0:8000::153` | 300 |
| AAAA | `@` | `2606:50c0:8001::153` | 300 |
| AAAA | `@` | `2606:50c0:8002::153` | 300 |
| AAAA | `@` | `2606:50c0:8003::153` | 300 |
| CNAME | `www` | `ramseyxlil.github.io` | 300 |
| TXT | `_github-pages-challenge-ramseyxlil` | (provided by GitHub) | 300 |

These IPs are GitHub Pages' official anycast endpoints. Verify the current set at https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site (they update rarely).

### Configure the custom domain in GitHub

Once DNS propagates (usually 5-30 minutes):

1. **Settings → Pages → Custom domain:** Enter `aaep-protocol.org`
2. Wait for the DNS check to pass (green checkmark)
3. ✅ **Enforce HTTPS** — toggle on after the SSL certificate provisions (5-10 minutes)

### Verify the deployment

```bash
curl -I https://aaep-protocol.org
# Expected: HTTP/2 200, server: GitHub.com

curl https://aaep-protocol.org/schemas/v1/envelope.json | head -5
# Expected: the envelope schema starts here

curl https://aaep-protocol.org/spec/01-introduction.html | grep "<title>"
# Expected: <title>Specification: 01 Introduction — AAEP</title>
```

Check from multiple geographic locations if possible (https://www.whatsmydns.net).

---

## 7. GitHub Actions enablement

Navigate to **Settings → Actions → General**:

- **Actions permissions:** Allow all actions and reusable workflows
- **Workflow permissions:** Read and write permissions (needed for Pages deploy)
- **Allow GitHub Actions to create and approve pull requests:** ✅ (for Dependabot)

Navigate to **Settings → Environments → New environment**:

- **Name:** `github-pages`
- **Required reviewers:** Add yourself (Ramseyxlil)
- **Wait timer:** 0 (no delay)
- **Deployment branches:** Selected branches → `main`

The first deploy may require your approval at this point. Subsequent deploys proceed automatically.

### Verify the four workflows are enabled

Navigate to **Actions**:

1. **Conformance Tests** — should show its first run from the initial push
2. **Schema Validation** — same
3. **Spec Build** — same
4. **Publish Website** — should have already succeeded

If any workflow shows as disabled, click into it and select **Enable workflow**.

---

## 8. PyPI publishing

The repository ships 11 PyPI-publishable Python packages. Publish them in dependency order so each can resolve its dependencies.

### Setup (one-time)

```bash
# Install publishing tools
pip install --upgrade build twine

# Configure ~/.pypirc with your PyPI token
# Get a token at https://pypi.org/manage/account/token/
cat > ~/.pypirc <<EOF
[pypi]
username = __token__
password = pypi-AgEIcHlwaS5vcmcCJDk... (your token)
EOF
chmod 600 ~/.pypirc
```

### Publishing order

Publish in this exact order. Wait ~60 seconds between packages so PyPI's index updates.

#### 1. aaep-conformance (foundation — has no AAEP dependencies)

```bash
cd conformance/aaep_conformance
python -m build
twine upload dist/*
# Verify: https://pypi.org/project/aaep-conformance/
```

#### 2. aaep-minimal-producer (foundation — used by other producers)

```bash
cd examples/producers/python-minimal
python -m build
twine upload dist/*
# Verify: https://pypi.org/project/aaep-minimal-producer/
```

#### 3. aaep-tools

```bash
cd tools/aaep-tools
python -m build
twine upload dist/*
```

#### 4-6. Producer integrations (depend on aaep-minimal-producer)

```bash
for pkg in python-langchain python-anthropic-sdk python-microsoft-agent-framework; do
    cd "examples/producers/$pkg"
    python -m build
    twine upload dist/*
    cd ../../..
    sleep 60
done
```

#### 7-8. Bridges

```bash
for pkg in mcp-aaep-bridge opentelemetry-aaep-bridge; do
    cd "examples/bridges/$pkg"
    python -m build
    twine upload dist/*
    cd ../../..
    sleep 60
done
```

#### 9-10. Extensions

```bash
for pkg in multilingual-african-languages medical-hipaa; do
    cd "examples/extensions/$pkg"
    python -m build
    twine upload dist/*
    cd ../../..
    sleep 60
done
```

#### 11. Subscriber packages

```bash
for pkg in cli-debug narrator-bridge-prototype; do
    cd "examples/subscribers/$pkg"
    python -m build
    twine upload dist/*
    cd ../../..
    sleep 60
done
```

The NVDA add-on is not on PyPI (it's distributed as a `.nvda-addon` file via the NVDA add-on store).

### Verify

```bash
pip install aaep-conformance aaep-minimal-producer aaep-tools \
            aaep-ext-african-languages aaep-ext-medical-hipaa
aaep-validate --version  # Should print 1.0.0
```

---

## 9. npm publishing

Two TypeScript packages need to be published to npm under the `@aaep` scope.

### Setup (one-time)

```bash
# Create npm account if needed: https://www.npmjs.com/signup
# Create the @aaep organization at https://www.npmjs.com/org/create

npm login
# Or: npm set //registry.npmjs.org/:_authToken=YOUR_TOKEN
```

### 1. @aaep/typescript-minimal

```bash
cd examples/producers/typescript-minimal
npm install
npm run build
npm publish --access public
```

### 2. @aaep/web-subscriber-react

```bash
cd examples/subscribers/web-subscriber-react
npm install
npm run build
npm publish --access public
```

### Verify

```bash
# In a scratch directory
npm view @aaep/web-subscriber-react
npm install @aaep/web-subscriber-react
```

---

## 10. Pre-launch checklist (T-30 to T-1)

A countdown checklist starting 30 days before launch.

### T-30 days (May 31, 2026)

- [ ] Repository created and pushed to GitHub
- [ ] Initial CI workflows green
- [ ] LICENSE-CC-BY-4.0 has canonical text (not placeholder)
- [ ] ORCID registered for "Abdulrafiu Izuafa" (https://orcid.org/register)
- [ ] CITATION.cff updated with the ORCID identifier

### T-21 days (June 9, 2026)

- [ ] DNS records configured for aaep-protocol.org
- [ ] GitHub Pages serves at aaep-protocol.org (HTTPS green)
- [ ] All schemas resolve from canonical URLs
- [ ] Announcement post drafts in private (LinkedIn, X, Mastodon)

### T-14 days (June 16, 2026)

- [ ] All 11 PyPI packages published
- [ ] Both npm packages published
- [ ] `pip install aaep-conformance` works from a fresh environment
- [ ] `npm install @aaep/web-subscriber-react` works

### T-7 days (June 23, 2026)

- [ ] Send pre-launch notification to early reviewers (private list)
- [ ] Confirm Microsoft MVP forum cross-post (must be approved by MVP MS team)
- [ ] Confirm AzureLearn AI community announcement scheduled
- [ ] Verify every governance email address routes correctly:
  - `Abdulrafiu@izusoft.tech` (general)
  - `security@aaep-protocol.org` (security disclosures)
  - `conduct@aaep-protocol.org` (Code of Conduct)
  - `trademark@aaep-protocol.org` (trademark inquiries)
  - `maintainers@aaep-protocol.org` (removal/correction requests)

### T-3 days (June 27, 2026)

- [ ] Final spec re-read for any last typos or unclear language
- [ ] Re-run all CI workflows
- [ ] Verify https://aaep-protocol.org renders correctly on:
  - Chrome (Windows, Mac, Android)
  - Firefox (Windows, Linux)
  - Safari (Mac, iOS)
  - Edge (Windows)
  - With dark mode toggled
  - With reduced-motion enabled
  - With Windows High Contrast Mode active
  - With NVDA (Firefox) reading the page
  - With VoiceOver (Safari) reading the page

### T-1 day (June 29, 2026)

- [ ] Final dry-run of announcement posts (everything proofread, links tested)
- [ ] Confirm all schedule reminders set for tomorrow
- [ ] Verify the GitHub repo is public and discoverable
- [ ] Sleep well

---

## 11. Launch day (June 30, 2026)

Sequence the actions, don't do everything at once.

### 09:00 WAT — Launch confirmation

- [ ] Verify aaep-protocol.org is up and serving the current spec
- [ ] Verify GitHub repository is public
- [ ] Verify PyPI/npm packages all resolve
- [ ] Final spot-check of CHANGELOG.md, README.md, governance docs

### 10:00 WAT — Primary announcement

Post the launch announcement on **LinkedIn first** (your primary professional audience):

> The Agent Accessibility Event Protocol (AAEP) v1.0.0 is now public.
>
> AAEP is an open standard that lets AI agents communicate with assistive
> technology — screen readers, AAC devices, Braille displays — in real time,
> with safety-by-default semantics and first-class multilingual support
> including Yoruba, Hausa, and Igbo.
>
> Specification, reference implementations, conformance suite, and
> governance documents at https://aaep-protocol.org. Source at
> https://github.com/Ramseyxlil/aaep.
>
> Free to use under MIT (code) and CC-BY-4.0 (spec).
>
> #accessibility #ai #opensource #protocol

### 10:15 WAT — X / Mastodon

Cross-post a shorter thread with the same key points and a screenshot of the landing page.

### 10:30 WAT — AzureLearn AI community

Post in your 1,500+ member AzureLearn AI Discord/community:

> Big day for accessibility in AI. AAEP v1.0.0 is live. This was a
> significant effort over the past months — full spec, 13 reference
> implementations, conformance suite, governance, the whole thing.
>
> Specifically for our community: there are extensions for African
> languages and a working NVDA add-on prototype. If you're building
> agents, this is the protocol to make them accessible.
>
> https://aaep-protocol.org

### 11:00 WAT — Microsoft MVP cross-post

In the Microsoft MVP community forums, share the announcement focusing on:
- Microsoft Agent Framework integration is shipped
- Narrator bridge prototype demonstrates UIA-based integration
- Direct ask for feedback from Microsoft Accessibility team

### 12:00 WAT — Targeted outreach (private)

Send personalized emails to:

- **Microsoft Accessibility team contacts** — direct link to Narrator bridge prototype with the explicit invitation to discuss native Narrator AAEP support
- **NV Access (NVDA developers)** — direct link to the NVDA add-on prototype
- **Anthropic** — note that AAEP cites MCP as the inspiration for the extension mechanism; invite feedback
- **GNOME Orca team** — note the bridge architecture could be applied to Orca
- **Apple Accessibility (if you have a contact)** — note VoiceOver integration is a v1.x roadmap item

Template:

> Subject: AAEP v1.0.0 launched today — would value your perspective
>
> Hi [Name],
>
> The Agent Accessibility Event Protocol launched today at
> https://aaep-protocol.org. The reason I'm reaching out personally
> rather than just announcing publicly: [specific reason for this contact].
>
> [Specific link to their relevant section.]
>
> Would welcome 30 minutes to discuss whether this could help
> [their product/community]. No pitch, just exchange.
>
> Best,
> Abdulrafiu

### 14:00 WAT — Track responses

Set up a simple tracker (spreadsheet or Notion) for:
- Outreach sent / response received
- Public mentions of AAEP
- Pull requests opened
- Stars on the repo

### 18:00 WAT — Evening check

- [ ] Any urgent issues raised? Respond.
- [ ] Any CI failures from new traffic? Investigate.
- [ ] Any DM responses from outreach? Reply.

### 20:00 WAT — Stop working

The protocol is launched. Adoption takes months. Closing your laptop today is the right move. Resume tomorrow.

---

## 12. Announcement strategy (T+0 to T+30)

### Week 1 (July 1-7, 2026)

- **Day 2:** Post a "what we built and why" technical blog on Dev.to and Medium
- **Day 3:** Submit AAEP to Hacker News with the title *"AAEP: An open protocol for AI agents to communicate with assistive technology"*. Use the right timing (Tuesday or Wednesday, 8am Pacific) for best traction.
- **Day 5:** Cross-post to Lobsters, Reddit r/programming, r/accessibility
- **Day 7:** First "what we learned in week 1" reflection on LinkedIn

### Week 2 (July 8-14, 2026)

- Submit a CFP to relevant conferences:
  - **CSUN Assistive Technology Conference** (next year)
  - **ARIA & Authoring Practices working group** at W3C TPAC
  - **Accessibility Discovery Center** events
  - **Microsoft Ability Summit** (Microsoft accessibility event)
  - **NeurIPS AI Accessibility workshop**

### Week 3-4 (July 15-30, 2026)

- Follow up with any contacts who responded but haven't yet engaged
- Pursue any partnerships that surfaced from launch outreach
- Open the first canonical extension RFC for community discussion (e.g., the Swahili extension)
- Publish a "30 days post-launch" status update on the website (added to `governance/ADOPTERS.md` if any production users emerged)

### Beyond T+30

- Continue weekly updates for the first 3 months on the announcement channel
- Submit a paper to a workshop or journal (the Microsoft Press proposal from Shourav Bose could be relevant here)
- Track conformance suite downloads from PyPI / npm to gauge adoption interest

---

## 13. Post-launch monitoring

### Daily for the first 30 days

- [ ] Check GitHub Issues — respond within 24 hours
- [ ] Check the security mailbox — respond within 48 hours
- [ ] Check `conduct@` and `maintainers@` — respond within 48 hours
- [ ] Monitor CI workflow runs — investigate any failures
- [ ] Check PyPI download statistics (https://pypistats.org/packages/aaep-conformance)

### Weekly for the first 90 days

- [ ] Review Dependabot PRs (should be manageable batch)
- [ ] Read any external mentions (Google Alerts, GitHub forks, blog posts)
- [ ] Update `governance/ADOPTERS.md` if a real production user appears
- [ ] Track any spec-clarification issues — these inform the v1.0.1 patch

### Monthly for the first year

- [ ] Publish a status update on the website
- [ ] Review the roadmap and re-prioritize based on what adopters actually need
- [ ] Consider whether any reserved namespaces have approached the 18-month expiry
- [ ] Audit `governance/MAINTAINERS.md` — has anyone earned promotion?

### Reverse-engineer success

A month after launch, examine:

- **Quality signal:** number of GitHub stars/forks (less important than substance)
- **Adoption signal:** PyPI/npm download counts (proxy for trying it)
- **Engagement signal:** Discussions activity, Issues created, PRs from outside contributors
- **Strategic signal:** any direct conversations with Microsoft Accessibility, NV Access, Anthropic, W3C

The strategic signal matters most. A protocol with 50 stars but Microsoft's interest is more successful than one with 5000 stars and no institutional adoption.

---

## Appendix A: Emergency procedures

### Security incident

A reported vulnerability before public disclosure:

1. Acknowledge receipt within 48 hours (per `SECURITY.md`)
2. Assess severity within 5 business days
3. Plan remediation within 10 business days
4. Patch within 30 days for critical/high, 90 for medium, 180 for low
5. Disclose 90 days after patch is widely available

### Site goes down

If `aaep-protocol.org` becomes unreachable:

1. Check GitHub Pages status: https://www.githubstatus.com
2. Re-run the `Publish Website` workflow from Actions
3. Verify DNS hasn't changed at your registrar
4. If DNS expired/lapsed, renew immediately

The schema URLs in the JSON Schemas reference this domain. Downtime breaks downstream validators. **Site downtime is a P0 incident.**

### Domain expires

The `aaep-protocol.org` domain must NEVER expire. Configure:

- Auto-renew at your registrar
- Renewal payment method that won't expire
- Email notifications to multiple addresses (not just one)
- 90-day-out, 30-day-out, and 7-day-out reminders

Losing the domain = losing the schemas = breaking every implementation. This is non-negotiable.

---

## Appendix B: Maintainer succession

If anything happens to you (the bootstrap Maintainer):

The `governance/GOVERNANCE.md` document specifies the path: a designated successor maintainer takes over with the existing community's support. The trust arrangement around the trademark in `TRADEMARK.md` covers this case explicitly.

For practical succession, ensure:

- Your designated successor has access to (or can recover):
  - The `Ramseyxlil` GitHub account credentials (via your password manager / 2FA recovery)
  - The DNS registrar account for `aaep-protocol.org`
  - The PyPI account with permissions to the `aaep-*` packages
  - The npm account with permissions to the `@aaep` org

- Document this access in a separate sealed envelope or password vault with succession instructions.

This isn't morbid — it's responsible. Open protocols outlive their authors.

---

## Closing notes

The launch isn't the end of the project. It's day one of years of work — listening to adopters, refining the spec, expanding the extension ecosystem, eventually transitioning to a foundation.

You've built something real. Now ship it.

Good luck.

— *Written by Claude as part of the AAEP repository build, June 1, 2026*
