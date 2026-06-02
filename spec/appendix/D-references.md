# Appendix D — References

*Status: Informative (the appendix); citations marked individually as Normative or Informative.*

---

This appendix lists the normative and informative references cited throughout the AAEP specification. Citations are organized by source type within each category. Where multiple equivalent URLs exist for a reference, the canonical or most stable URL is given.

Implementers building production AAEP support SHOULD have working familiarity with the normative references in §D.1. The informative references in §D.2 provide background and context.

---

## D.1 Normative references

Normative references are documents that AAEP implementations MUST satisfy or that AAEP's text formally incorporates by reference. Conformance to AAEP implies conformance to these references where applicable.

### D.1.1 IETF Requests for Comments (RFCs)

**[RFC 2119]** — *Key words for use in RFCs to Indicate Requirement Levels.* S. Bradner. March 1997. [https://www.rfc-editor.org/rfc/rfc2119](https://www.rfc-editor.org/rfc/rfc2119)

Defines MUST, SHOULD, MAY and related conformance keywords. Updated by [RFC 8174]; together these form Best Current Practice 14.

**[RFC 3339]** — *Date and Time on the Internet: Timestamps.* G. Klyne, C. Newman. July 2002. [https://www.rfc-editor.org/rfc/rfc3339](https://www.rfc-editor.org/rfc/rfc3339)

Specifies the timestamp format used by AAEP for the envelope `timestamp` field. RFC 3339 is a profile of ISO 8601 suited to internet protocols.

**[RFC 3986]** — *Uniform Resource Identifier (URI): Generic Syntax.* T. Berners-Lee, R. Fielding, L. Masinter. January 2005. [https://www.rfc-editor.org/rfc/rfc3986](https://www.rfc-editor.org/rfc/rfc3986)

Defines URI syntax. AAEP uses URIs for `@context` values, event type identifiers, manifest URIs, and extension namespaces.

**[RFC 5234]** — *Augmented BNF for Syntax Specifications: ABNF.* D. Crocker (ed.), P. Overell. January 2008. [https://www.rfc-editor.org/rfc/rfc5234](https://www.rfc-editor.org/rfc/rfc5234)

Defines the grammar notation used in AAEP for formal syntax (e.g., the format of `event_id` and `session_id` values).

**[RFC 5646]** — *Tags for Identifying Languages.* A. Phillips, M. Davis (eds.). September 2009. [https://www.rfc-editor.org/rfc/rfc5646](https://www.rfc-editor.org/rfc/rfc5646)

Defines language tag syntax. AAEP requires BCP 47 / RFC 5646 tags in `localization_hints` and language capability fields. Together with [RFC 4647] forms Best Current Practice 47.

**[RFC 7515]** — *JSON Web Signature (JWS).* M. Jones, J. Bradley, N. Sakimura. May 2015. [https://www.rfc-editor.org/rfc/rfc7515](https://www.rfc-editor.org/rfc/rfc7515)

Defines JWS, used by AAEP for signed producer manifests at Conformance Level 3.

**[RFC 8174]** — *Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words.* B. Leiba. May 2017. [https://www.rfc-editor.org/rfc/rfc8174](https://www.rfc-editor.org/rfc/rfc8174)

Clarifies that the RFC 2119 conformance keywords have normative meaning only in their uppercase form.

**[RFC 8259]** — *The JavaScript Object Notation (JSON) Data Interchange Format.* T. Bray (ed.). December 2017. [https://www.rfc-editor.org/rfc/rfc8259](https://www.rfc-editor.org/rfc/rfc8259)

Defines JSON. AAEP messages MUST be valid JSON per RFC 8259, encoded as UTF-8.

### D.1.2 W3C Recommendations and standards

**[JSON-LD 1.1]** — *JSON-LD 1.1: A JSON-based Serialization for Linked Data.* G. Kellogg, P-A. Champin, D. Longley (eds.). W3C Recommendation, 16 July 2020. [https://www.w3.org/TR/json-ld11/](https://www.w3.org/TR/json-ld11/)

Defines the JSON-LD format used by AAEP, particularly the `@context` mechanism that enables the extension model.

### D.1.3 Unicode and internationalization

**[Unicode]** — *The Unicode Standard.* The Unicode Consortium. Current version 16.0 (2025). [https://www.unicode.org/standard/standard.html](https://www.unicode.org/standard/standard.html)

The character encoding standard underlying UTF-8. AAEP requires Unicode support throughout.

**[UAX #9]** — *Unicode Bidirectional Algorithm.* M. Davis, A. Lanin, K. Whistler (eds.). Unicode Standard Annex #9, current revision. [https://www.unicode.org/reports/tr9/](https://www.unicode.org/reports/tr9/)

Specifies how bidirectional (mixed left-to-right and right-to-left) text is rendered. Referenced by AAEP for subscriber handling of bidirectional content.

**[UAX #15]** — *Unicode Normalization Forms.* M. Davis, K. Whistler (eds.). Unicode Standard Annex #15, current revision. [https://www.unicode.org/reports/tr15/](https://www.unicode.org/reports/tr15/)

Specifies Unicode normalization forms (NFC, NFD, NFKC, NFKD). AAEP recommends NFC for emitted strings.

**[ISO 8601]** — *ISO 8601-1:2019. Date and time — Representations for information interchange.* International Organization for Standardization. 2019.

International standard for date and time format. AAEP's RFC 3339 timestamps are a profile of ISO 8601.

**[ISO 15924]** — *ISO 15924:2022. Information and documentation — Codes for the representation of names of scripts.* International Organization for Standardization. 2022.

International standard for script identifiers. Used in BCP 47 language tags and in AAEP's `localization_hints.script` field.

### D.1.4 Versioning

**[SemVer 2.0.0]** — *Semantic Versioning 2.0.0.* T. Preston-Werner. June 2013. [https://semver.org/spec/v2.0.0.html](https://semver.org/spec/v2.0.0.html)

The versioning scheme AAEP follows for its specification and extensions.

### D.1.5 Best Current Practices

**[BCP 14]** — *Best Current Practice 14: Key words for use in RFCs.* Combines [RFC 2119] and [RFC 8174]. [https://www.rfc-editor.org/info/bcp14](https://www.rfc-editor.org/info/bcp14)

The normative source for conformance keywords used throughout AAEP.

**[BCP 47]** — *Best Current Practice 47: Tags for Identifying Languages.* Combines [RFC 5646] and [RFC 4647]. [https://www.rfc-editor.org/info/bcp47](https://www.rfc-editor.org/info/bcp47)

The normative source for language tag syntax and matching used in AAEP internationalization.

---

## D.2 Informative references

Informative references provide context, background, and comparison. AAEP does not formally incorporate them, but readers benefit from familiarity with them.

### D.2.1 Accessibility standards

**[WAI-ARIA 1.2]** — *Accessible Rich Internet Applications (WAI-ARIA) 1.2.* J. Diggs, J. Craig, M. Cooper (eds.). W3C Recommendation, 6 June 2023. [https://www.w3.org/TR/wai-aria-1.2/](https://www.w3.org/TR/wai-aria-1.2/)

The W3C standard for accessible web content. AAEP complements WAI-ARIA: ARIA addresses rendered UI; AAEP addresses agent internal state.

**[WCAG 2.2]** — *Web Content Accessibility Guidelines (WCAG) 2.2.* M. Cooper, A. Kirkpatrick, J. O'Connor, M. Pluke (eds.). W3C Recommendation, 5 October 2023. [https://www.w3.org/TR/WCAG22/](https://www.w3.org/TR/WCAG22/)

The W3C guidelines for web accessibility, organized around POUR (Perceivable, Operable, Understandable, Robust). AAEP-conformant web subscribers SHOULD also conform to WCAG.

**[Microsoft UIA]** — *UI Automation Overview.* Microsoft. [https://learn.microsoft.com/en-us/windows/win32/winauto/entry-uiauto-win32](https://learn.microsoft.com/en-us/windows/win32/winauto/entry-uiauto-win32)

Microsoft's accessibility API for Windows. Used by Narrator and other Windows assistive technology.

**[AT-SPI]** — *Assistive Technology Service Provider Interface.* GNOME / Linux Foundation. [https://accessibility.linuxfoundation.org/a11yspecs/atspi/](https://accessibility.linuxfoundation.org/a11yspecs/atspi/)

The Linux accessibility framework. Used by Orca and other Linux assistive technology.

**[macOS AX API]** — *Accessibility programming guide for macOS.* Apple Inc. [https://developer.apple.com/documentation/accessibility](https://developer.apple.com/documentation/accessibility)

Apple's accessibility API. Used by VoiceOver and other macOS assistive technology.

**[Android Accessibility]** — *AccessibilityService API.* Google. [https://developer.android.com/reference/android/accessibilityservice/AccessibilityService](https://developer.android.com/reference/android/accessibilityservice/AccessibilityService)

Android's accessibility framework. Used by TalkBack and other Android assistive technology.

### D.2.2 Adjacent protocols

**[MCP]** — *Model Context Protocol.* Anthropic. 2024. [https://modelcontextprotocol.io/](https://modelcontextprotocol.io/)

An open protocol standardizing how LLM applications connect to tools and resources. AAEP is complementary to MCP; an MCP-to-AAEP bridge example is provided in [`examples/bridges/mcp-aaep-bridge/`](../../examples/bridges/mcp-aaep-bridge/).

**[LSP]** — *Language Server Protocol.* Microsoft. Current specification at [https://microsoft.github.io/language-server-protocol/](https://microsoft.github.io/language-server-protocol/)

A protocol between editors and language servers, using JSON-RPC. AAEP's stdio JSON-RPC transport binding follows patterns established by LSP.

**[ActivityStreams 2.0]** — *Activity Streams 2.0.* J. Snell, E. Prodromou. W3C Recommendation, 23 May 2017. [https://www.w3.org/TR/activitystreams-core/](https://www.w3.org/TR/activitystreams-core/)

A model and JSON-LD encoding for social activities. The `@context` and extension model in AAEP was influenced by ActivityStreams.

**[ActivityPub]** — *ActivityPub.* C. Lemmer-Webber, J. Tallon (eds.). W3C Recommendation, 23 January 2018. [https://www.w3.org/TR/activitypub/](https://www.w3.org/TR/activitypub/)

A federated social networking protocol built on ActivityStreams 2.0. Demonstrates successful real-world use of the JSON-LD extension model that AAEP adopts.

**[OpenAPI Specification]** — *OpenAPI Specification.* OpenAPI Initiative. Current version 3.1. [https://spec.openapis.org/](https://spec.openapis.org/)

A specification format for HTTP APIs. AAEP HTTP-based transports can be described using OpenAPI for documentation purposes.

**[gRPC]** — *gRPC: A high-performance, open-source universal RPC framework.* gRPC Authors. [https://grpc.io/](https://grpc.io/)

The RPC framework one of AAEP's transport bindings is built on. See [Appendix B §B.5](B-transport-bindings.md).

**[Verifiable Credentials]** — *Verifiable Credentials Data Model v2.0.* M. Sporny, D. Longley, D. Chadwick (eds.). W3C Recommendation, 2025. [https://www.w3.org/TR/vc-data-model-2.0/](https://www.w3.org/TR/vc-data-model-2.0/)

A standard for cryptographically verifiable claims. Demonstrates production use of JWS for content signing similar to AAEP's signed manifests.

### D.2.3 Web standards

**[WebSocket]** — *The WebSocket Protocol.* I. Fette, A. Melnikov. December 2011. [RFC 6455]. [https://www.rfc-editor.org/rfc/rfc6455](https://www.rfc-editor.org/rfc/rfc6455)

The WebSocket protocol. Used as one of AAEP's transport bindings.

**[SSE]** — *Server-Sent Events.* I. Hickson (ed.). WHATWG / HTML Living Standard. [https://html.spec.whatwg.org/multipage/server-sent-events.html](https://html.spec.whatwg.org/multipage/server-sent-events.html)

The Server-Sent Events specification. Used as one of AAEP's transport bindings.

**[JSON Schema 2020-12]** — *JSON Schema 2020-12.* JSON Schema Working Group. Current version. [https://json-schema.org/specification](https://json-schema.org/specification)

The schema definition language used in AAEP's `schemas/` directory. AAEP schemas declare conformance to JSON Schema 2020-12.

**[RFC 9110]** — *HTTP Semantics.* R. Fielding, M. Nottingham, J. Reschke (eds.). June 2022. [https://www.rfc-editor.org/rfc/rfc9110](https://www.rfc-editor.org/rfc/rfc9110)

HTTP semantics. AAEP HTTP-based transports operate within HTTP semantics. Also cited as inspiration for AAEP's versioning approach.

**[RFC 9457]** — *Problem Details for HTTP APIs.* M. Nottingham, E. Wilde, S. Dalal. July 2023. [https://www.rfc-editor.org/rfc/rfc9457](https://www.rfc-editor.org/rfc/rfc9457)

Standard format for structured HTTP error responses. AAEP's error reporting in `agent.session.errored` was influenced by this pattern.

### D.2.4 Observability and telemetry

**[OpenTelemetry]** — *OpenTelemetry Specification.* OpenTelemetry Authors. Current version. [https://opentelemetry.io/docs/specs/otel/](https://opentelemetry.io/docs/specs/otel/)

The observability framework that AAEP's `correlation_id` field interoperates with. An OpenTelemetry-to-AAEP bridge example is in [`examples/bridges/opentelemetry-aaep-bridge/`](../../examples/bridges/opentelemetry-aaep-bridge/).

**[W3C Trace Context]** — *W3C Trace Context.* M. Kondo, M. Trabauer, A. Reitbauer (eds.). W3C Recommendation, 17 March 2025. [https://www.w3.org/TR/trace-context-2/](https://www.w3.org/TR/trace-context-2/)

Standard for distributed trace context propagation. AAEP's `correlation_id` is compatible with W3C Trace Context identifiers.

### D.2.5 Research and prior art

**[Chen2026]** — Chen, N., Lu, J., Wang, Z., Qiu, L. K., Chen, S., Yang, Y. *From Struggle to Success: Context-Aware Guidance for Screen Reader Users in Computer Use.* CHI '26: Proceedings of the 2026 CHI Conference on Human Factors in Computing Systems. Microsoft Research. [https://arxiv.org/abs/2601.18092](https://arxiv.org/abs/2601.18092)

The paper that established the research direction of LLM-mediated accessibility for screen reader users. Motivates the need for the complementary infrastructure AAEP provides at the agent layer.

**[Brewer2024]** — *Inclusive Design for AI: Lessons from Accessibility.* Various authors. AccessibilityNYC Workshop, 2024.

Workshop proceedings discussing inclusive design principles applied to AI systems. Cited as background context.

**[Bigham2017]** — Bigham, J. P., Brady, E., Gleason, C., Guo, A., Shamma, D. A. *An Uninteresting Tour through Why Our Research Papers Aren't Accessible.* CHI EA '16: Proceedings of the 2016 CHI Conference Extended Abstracts on Human Factors in Computing Systems. [https://dl.acm.org/doi/10.1145/2851581.2892588](https://dl.acm.org/doi/10.1145/2851581.2892588)

A discussion of how accessibility considerations are routinely under-addressed in HCI publications. Methodologically relevant to AAEP's commitment to disabled users as co-authors.

**[Wobbrock2011]** — Wobbrock, J. O., Kane, S. K., Gajos, K. Z., Harada, S., Froehlich, J. *Ability-Based Design: Concept, Principles and Examples.* ACM Transactions on Accessible Computing, Vol. 3, Issue 3. [https://dl.acm.org/doi/10.1145/1952383.1952384](https://dl.acm.org/doi/10.1145/1952383.1952384)

Framework for designing technology around users' abilities rather than disabilities. Philosophically influential on AAEP's user-control principle.

### D.2.6 Process and tooling references

**[Keep a Changelog]** — *Keep a Changelog 1.1.0.* O. Lacan. [https://keepachangelog.com/en/1.1.0/](https://keepachangelog.com/en/1.1.0/)

The changelog format used by AAEP's `CHANGELOG.md`.

**[Citation File Format]** — *Citation File Format (CFF) 1.2.0.* S. Druskat, J. Spaaks, N. Chue Hong, R. Haines, J. Baker. [https://citation-file-format.github.io/](https://citation-file-format.github.io/)

The format used in AAEP's `CITATION.cff` for academic citation metadata.

**[Contributor Covenant]** — *Contributor Covenant 2.1.* C. Ehmke. [https://www.contributor-covenant.org/version/2/1/code_of_conduct/](https://www.contributor-covenant.org/version/2/1/code_of_conduct/)

The code of conduct adopted by the AAEP project. See [governance/CODE_OF_CONDUCT.md](../../governance/CODE_OF_CONDUCT.md).

### D.2.7 Anti-references

The following are NOT references for AAEP. They are listed to disambiguate AAEP from similarly-named or apparently-related work:

- **EUM (Enterprise User Management)** — unrelated; despite acronym similarity, not connected to AAEP.
- **AEP (Adobe Experience Platform)** — unrelated; a marketing platform from Adobe.
- **AAEP (American Association of Equine Practitioners)** — unrelated; a veterinary organization that happens to share the acronym.

The Agent Accessibility Event Protocol claims the AAEP acronym for the technical context of accessibility for AI agents; collisions in other domains are noted here for clarity.

---

## D.3 Reference URLs

All reference URLs in this appendix are intended to be stable for the lifetime of AAEP. Reference URLs that become unreachable in future will be replaced via PATCH-level errata to this appendix; the replacement URLs will preserve the citation's meaning even if hosting changes.

The AAEP project maintains a mirror of cited specifications at [https://aaep-protocol.org/references/](https://aaep-protocol.org/references/) (forthcoming).

## D.4 Suggested reading order

For readers new to the standards bodies and protocols cited above, the following reading order helps build foundational understanding:

1. **Start with the basics.** [RFC 8259] (JSON) and [RFC 3339] (timestamps) are the smallest, easiest to absorb.

2. **Then conformance language.** [BCP 14] explaining MUST/SHOULD/MAY is short and gives the vocabulary to read other standards.

3. **Then protocol-relevant references.** [JSON-LD 1.1] and [WebSocket] (RFC 6455) explain the mechanics underlying AAEP's transports.

4. **Then accessibility prior art.** [WAI-ARIA 1.2] is the most directly comparable accessibility standard. Skim its structure; AAEP follows similar conventions.

5. **Finally, related research.** [Chen2026] (the AskEase paper) provides the context for why AAEP exists.

This reading sequence takes approximately 8-15 hours and equips a reader to engage meaningfully with the AAEP specification, the conformance test suite, and the broader ecosystem.

## D.5 Where to go next

This appendix concludes the AAEP specification.

Implementers should now consult:

- The [Implementer's Guide](../../guides/IMPLEMENTERS_GUIDE.md) for framework-specific integration patterns.
- The [Subscribers' Guide](../../guides/SUBSCRIBERS_GUIDE.md) for assistive technology integration patterns.
- The [Extensions Guide](../../guides/EXTENSIONS_GUIDE.md) for publishing AAEP extensions.
- The [Quickstart](../../guides/QUICKSTART.md) for a ten-minute introduction.

Adopters should next:

- Review [governance/CONTRIBUTING.md](../../governance/CONTRIBUTING.md) for how to participate in AAEP's evolution.
- Register in [governance/ADOPTERS.md](../../governance/ADOPTERS.md) once production AAEP support ships.

Researchers and standards practitioners should next consult [governance/ROADMAP.md](../../governance/ROADMAP.md) for AAEP's path to W3C Community Group status.

The AAEP project welcomes feedback, criticism, and contribution at every level of engagement.

---

*End of specification.*
