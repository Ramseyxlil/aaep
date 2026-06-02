<!--
Thank you for contributing to AAEP! Please complete this template so reviewers
can evaluate your change efficiently. Sections marked "Required" must be filled.

See governance/CONTRIBUTING.md for the full contribution guide, and
governance/CODE_OF_CONDUCT.md for community standards.
-->

## Summary

<!-- Required: 1-3 sentence description of what this PR does. -->

## Type of change

<!-- Required: check exactly one. -->

- [ ] Bug fix (does not change the spec or schemas)
- [ ] Feature (adds capability without breaking existing behavior)
- [ ] Documentation (no code or spec changes)
- [ ] Spec change (modifies the normative specification — requires an ACP)
- [ ] Schema change (modifies JSON schemas — requires an ACP)
- [ ] Breaking change (incompatible with existing AAEP implementations — requires an ACP and migration plan)
- [ ] Tooling / CI / build (affects only the development process)

## Related issue(s)

<!-- Required: link to the issue this PR addresses, or "None" if this is unsolicited.
Format: Closes #123 / Fixes #123 / Related to #123 -->

## Accessibility implications

<!--
REQUIRED for every PR. Per governance/CONTRIBUTING.md §6.2, PRs without
this section are returned to authors without review.

If you genuinely believe this PR has no accessibility implications, state
that explicitly. Don't leave the section blank. Examples:
  "No accessibility implications. This is a build script change that
   affects only CI."
  "Improves screen reader announcement order for confirmation events."
  "May affect users on slow connections; tested with 3G throttling."
-->

## How has this been tested?

<!-- Required: describe how you verified your change. -->

- [ ] Ran the conformance suite (Level 1 / 2 / 3 — circle which)
- [ ] Added new tests
- [ ] Tested manually (describe how)
- [ ] N/A — explain why

## Spec / schema impact

<!-- If this PR modifies the spec or schemas, complete this section.
Otherwise delete it. -->

- ACP number: ACP-NNNN (link)
- Schema files affected: ...
- Migration path: ...
- Backward compatibility: ...

## Checklist

- [ ] My commits follow [Conventional Commits](https://www.conventionalcommits.org/)
- [ ] I have signed off my commits with `git commit -s` (DCO)
- [ ] I have read [CONTRIBUTING.md](../governance/CONTRIBUTING.md)
- [ ] I agree to license my contribution under MIT (code) or CC-BY-4.0 (spec)
- [ ] No `aria-hidden="true"` on focusable elements (if HTML changes)
- [ ] No motion that ignores `prefers-reduced-motion` (if CSS changes)
- [ ] Conformance tests still pass (run `aaep-conformance` locally)

## Additional context

<!-- Anything else reviewers should know. Screenshots, performance numbers,
related discussions, etc. -->
