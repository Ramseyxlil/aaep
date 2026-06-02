# Chapter 10 — Security considerations

*Status: Normative*

---

This chapter specifies the **threat model** for AAEP, the security guarantees the protocol does and does not provide, and the mitigations available to producers, subscribers, and operators. Security is treated as a first-class concern because AAEP carries information that can authorize side-effecting and irreversible actions; weakness here directly translates to user harm.

Implementers building AAEP support for safety-critical or regulated workflows (financial transactions, medical decisions, legal actions, infrastructure control) MUST read this chapter and the dispute resolution procedures in [governance/SECURITY.md](../governance/SECURITY.md) before deployment.

## 10.1 Security model and trust boundaries

AAEP is a peer protocol between a producer and one or more subscribers. The trust relationship between these parties is established **outside** the protocol, typically by:

- The operating system (for local-IPC transports).
- The TLS infrastructure and certificate authorities (for network transports).
- The deploying organization's identity and access management (for enterprise transports).
- User configuration (for desktop-application-to-assistive-technology pairing).

AAEP itself does **not** authenticate parties. The protocol assumes that the transport layer, the operating system, or organizational policy establishes trust. AAEP then adds protocol-level mechanisms (reply tokens, signed manifests, blocking contract) that depend on that established trust for safety.

A consequence: an AAEP deployment is only as secure as the transport and identity infrastructure carrying it. A producer reachable over an unauthenticated public HTTP endpoint cannot be trusted; an AAEP-conformant implementation will not by itself fix that.

### 10.1.1 Within-host trust

For local-IPC transports (Windows named pipes, Unix domain sockets, stdio), trust is established by the operating system. The producer is a process owned by a user account; the subscriber is another process. The two parties trust each other to the extent that the OS isolates user accounts and process privileges.

For these deployments, AAEP's security model is straightforward: anyone with the same user account as the producer can connect; anyone without cannot. Filesystem permissions on the socket or named pipe enforce this.

### 10.1.2 Cross-host trust

For network transports (HTTPS/SSE, WSS, gRPC over TLS), trust is established by TLS plus an additional authentication layer (Bearer tokens, mutual TLS certificates, signed JWS messages). AAEP does not specify which mechanism; implementations choose based on their organizational context.

The minimum requirement for production cross-host deployments is TLS 1.2 (with TLS 1.3 RECOMMENDED) plus subscriber authentication. Producers MUST refuse subscriptions from unauthenticated subscribers in cross-host deployments.

### 10.1.3 User-to-subscriber trust

The user's trust in their subscriber is established outside AAEP. The user installs Narrator, NVDA, JAWS, VoiceOver, or another assistive technology and configures it; that configuration includes trusting the AT to act on the user's behalf.

AAEP-conformant subscribers MUST honor this trust:

- A subscriber MUST NOT auto-respond to confirmation events on the user's behalf except as explicitly configured.
- A subscriber MUST present confirmation events with prominence appropriate to their `risk_level` and `urgency`.
- A subscriber MUST NOT silently drop, hide, or misrepresent the content of confirmation events.

A subscriber that violates user trust through any of the above is non-conforming, regardless of its technical correctness on other dimensions.

## 10.2 Threat model

The threat model below enumerates the specific threats AAEP addresses, the assumed capabilities of the attacker, and the mitigations the protocol provides. Threats not listed here are out of scope; implementers requiring additional protections must add them in the transport or application layer.

### 10.2.1 Assumed attacker capabilities

The threat model assumes a malicious actor with one or more of these capabilities:

1. **Network observer.** Can read traffic between producer and subscriber if the transport is unencrypted.
2. **Network injector.** Can inject or modify traffic if the transport is unauthenticated.
3. **Compromised subscriber.** A malicious or compromised subscriber that participates in the protocol but pursues malicious goals.
4. **Compromised producer.** A malicious or compromised producer that emits events designed to mislead users.
5. **Local process attacker.** A process running on the same host that does not have the same privileges as the legitimate producer or subscriber.
6. **Replay attacker.** Can capture and later replay valid messages.

The threat model does NOT assume:

- An attacker with full control of the host operating system (such an attacker can compromise any software).
- An attacker who can break TLS 1.3 or modern cryptographic primitives.
- An attacker who can compromise the underlying LLM or agent reasoning (this is an agent-safety concern, not an AAEP concern).

### 10.2.2 Specific threats and mitigations

Each numbered threat below states the attack, the AAEP-level mitigation, and any additional defense-in-depth recommendations.

#### Threat T1: Forged confirmation reply

**Attack:** An attacker sends a `confirmation.reply` message containing a valid `reply_token` (obtained through some means), causing the producer to perform a confirmed action that the user did not actually authorize.

**Why this matters:** This is the highest-impact attack on AAEP. A successful forged reply directly authorizes a side-effecting action.

**AAEP-level mitigation:**

- Reply tokens alone are NOT authorization (Chapter 6 §6.2.4). The producer MUST authenticate the sender at the transport layer before honoring the reply.
- The producer MUST validate that the reply arrives over the same subscription that received the originating confirmation event (or another subscription explicitly entitled to reply, per multi-subscriber rules in Chapter 5 §5.9).
- Reply tokens are single-use; once consumed, they cannot be reused.

**Defense in depth:**

- Use mutual TLS or signed JWS at the transport layer to bind reply messages to authenticated subscriber identities.
- For local-IPC transports, restrict subscriber connection permissions at the OS level.
- For very-high-risk actions (large financial transfers, irreversible deletions), consider out-of-band confirmation (SMS, hardware key, separate device) in addition to AAEP.

#### Threat T2: Replay attack

**Attack:** An attacker captures a valid `confirmation.reply` message and replays it later to cause the producer to repeat the confirmed action.

**AAEP-level mitigation:**

- Reply tokens are single-use; the producer marks tokens as consumed upon first valid reply and rejects subsequent uses of the same token (Chapter 6 §6.3.5).
- Reply tokens are bound to a specific session (`session_id` validation); tokens from one session cannot be used in another.
- Reply tokens have expiration: `timestamp` of reply must precede the originating event's `timestamp + timeout_seconds`.

**Defense in depth:**

- Use transport-level nonces (TLS session IDs, OAuth nonces) that prevent transport-level replay even if AAEP-level replay is somehow attempted.
- Log all reply attempts including rejected ones; flag patterns of rejected replays as potential attack indicators.

#### Threat T3: Confirmation phishing

**Attack:** A malicious or compromised producer emits a confirmation event whose `action` and `consequence` strings misrepresent what the agent will actually do. The user, reading the confirmation, accepts in good faith; the producer then performs a different action.

**AAEP-level mitigation:**

- The protocol cannot prevent a malicious producer from lying about what it will do. AAEP can only ensure the user is informed of what the producer **claims** it will do.
- Signed producer manifests (§10.4) cryptographically bind producer identity to its claimed capabilities, making it harder for an attacker to impersonate a known good producer.
- Subscribers SHOULD verify producer identity via signed manifests when the user has indicated this is a high-trust deployment.

**Defense in depth:**

- Deploy AAEP only with producers operated by trusted parties.
- For very-high-risk actions, the producer's outputs SHOULD be logged for after-the-fact audit comparison.
- For high-assurance environments, the producer SHOULD operate inside a sandboxed execution context that cannot perform actions outside what its manifest declares.

#### Threat T4: Denial of service via event flooding

**Attack:** A malicious or buggy producer floods a subscriber with events at a rate exceeding the subscriber's processing capacity, causing the subscriber to drop events, freeze, or crash.

**AAEP-level mitigation:**

- Subscribers declare `max_events_per_second` during the handshake (Chapter 5 §5.3.1.1). Producers MUST honor this rate.
- Conformance tests verify that producers do not exceed negotiated rates.
- Subscribers MAY close subscriptions where the producer is consistently violating rate limits.

**Defense in depth:**

- Subscribers SHOULD apply local rate-limiting in addition to negotiated rates, as defense against non-conforming or buggy producers.
- Subscribers SHOULD log rate violations and surface them to administrators.

#### Threat T5: Information disclosure via event content

**Attack:** A producer emits an event containing personally identifiable information (PII), credentials, secrets, or other sensitive data that should not be in the event payload. A network observer or compromised subscriber gains access to that data.

**AAEP-level mitigation:**

- The producer MUST NOT include secrets (API keys, passwords, PII beyond what the user has supplied) in `args_summary`, `summary_*`, or any other human-readable field.
- The producer SHOULD redact sensitive content from event payloads, especially for events that may be logged.
- The conformance test suite includes optional checks for known patterns of sensitive data (credit card numbers, SSN, common API key formats) in event payloads.

**Defense in depth:**

- Encrypt all network transports.
- Use AAEP's `extensions` namespace to mark sensitive content explicitly (e.g., a `privacy:` extension marking `phi_fields` so downstream tools can apply policy).
- Audit producer code for hard-coded sensitive values before deployment.

#### Threat T6: Producer impersonation

**Attack:** An attacker stands up a producer that pretends to be a known, trusted producer (using the same `agent_id`, `agent_name`, etc.) but performs malicious actions or extracts user data.

**AAEP-level mitigation:**

- Signed producer manifests (§10.4) cryptographically bind producer identity to its capabilities. A subscriber that verifies the signed manifest can detect impersonation.
- Transport-level authentication (mutual TLS, OAuth) binds the network endpoint to a specific organizational identity.

**Defense in depth:**

- For desktop integrations, restrict named pipes and Unix domain sockets to specific user accounts.
- For cloud deployments, require signed manifests and pin to specific certificate authorities for known producers.
- Maintain a public registry of trusted producer identities; subscribers can validate against this registry.

#### Threat T7: Malicious extension

**Attack:** An attacker publishes an AAEP extension that, when adopted by subscribers, causes them to disclose data, accept unsafe defaults, or be vulnerable to other attacks.

**AAEP-level mitigation:**

- Extensions are namespaced; the `aaep:` core namespace is reserved and cannot be impersonated.
- Subscribers MUST gracefully ignore extensions they do not understand. A subscriber that has not adopted a malicious extension is unaffected by it.
- Extension authors are documented in the [Extensions Registry](../governance/EXTENSIONS_REGISTRY.md), with contact and maintenance status.

**Defense in depth:**

- Treat extension adoption as a security review activity: the subscriber team reviews the extension specification, threat model, and provenance before adoption.
- Prefer extensions from established sources; treat new extensions with appropriate skepticism.

#### Threat T8: Subscription hijacking

**Attack:** An attacker uses some side channel to obtain a `subscription_id` and inject events or replies onto that subscription, masquerading as the legitimate party.

**AAEP-level mitigation:**

- Subscription IDs are not authentication credentials. The producer MUST authenticate each message at the transport layer regardless of subscription_id presence.
- For Level 3 implementations, subscriber identity is part of the handshake and is carried forward in transport-level authentication for all subsequent messages.

**Defense in depth:**

- Use mutual TLS or signed JWS at the transport layer.
- Rotate subscription IDs on a regular cadence in long-lived deployments.

## 10.3 Authentication and authorization

AAEP does not specify a single authentication mechanism. The choice depends on transport, deployment context, and organizational policy. The following mechanisms are RECOMMENDED:

### 10.3.1 Transport-level authentication

For TLS-based transports (HTTPS/SSE, WSS, gRPC):

- **Mutual TLS (mTLS):** Both parties present X.509 certificates. The strongest and most widely-deployed mechanism for cross-host AAEP.
- **Bearer tokens (OAuth 2.0, OIDC):** The subscriber presents an Authorization header carrying a signed token issued by an identity provider. Simpler than mTLS but requires an identity provider.
- **API keys:** Pre-shared opaque tokens. Easy to implement but harder to rotate and revoke. NOT RECOMMENDED for new deployments at any scale.

For local-IPC transports:

- **Unix domain socket peer credentials:** The kernel exposes the connecting process's UID/GID/PID, which the producer reads to verify identity.
- **Windows named pipe security descriptors:** The named pipe is protected by an ACL specifying which user accounts may connect.

For stdio JSON-RPC:

- **Parent-child process trust:** The subscriber spawned the producer (or vice versa), establishing trust at the OS level.

### 10.3.2 Authorization

Authorization is the question of whether an authenticated party is allowed to perform a specific action (subscribe, reply to a confirmation, request renegotiation). AAEP does not specify an authorization model; the producer applies its own policy.

Recommended pattern: associate each authenticated subscriber identity with a role (e.g., `accessibility_consumer`, `auditor`, `admin`). Map roles to AAEP capabilities (e.g., `accessibility_consumer` can subscribe and reply; `auditor` can subscribe in read-only mode; `admin` can additionally view internal state).

## 10.4 Signed producer manifests

At Conformance Level 3, producers MAY cryptographically sign their manifests using JSON Web Signature (JWS, [RFC 7515]). A signed manifest gives subscribers proof that the manifest was issued by the holder of a specific private key, enabling defense against producer impersonation.

[RFC 7515]: https://www.rfc-editor.org/rfc/rfc7515

### 10.4.1 Signing procedure

The producer:

1. Generates a JSON manifest per Chapter 5 §5.10.
2. Constructs a JWS with the manifest as the payload, the producer's signing key, and `alg: ES256` or `alg: RS256` (others permitted; ES256 RECOMMENDED for new keys).
3. Includes the JWS in the `subscription.accepted` message's `signed_manifest` field, OR makes the JWS-wrapped manifest available at the manifest URI.

### 10.4.2 Verification procedure

The subscriber:

1. Receives the signed manifest (inline or by dereferencing the manifest URI).
2. Identifies the signing key, either from a `kid` (key ID) in the JWS header that resolves to a known key, or via a key included in the JWS header (with appropriate trust evaluation), or from a separately-managed key directory.
3. Verifies the JWS signature.
4. Verifies the manifest's `agent_id` matches the `agent_id` claimed in `subscription.accepted`.
5. Verifies the manifest's claims (supported transports, conformance levels, languages) are consistent with what the producer is offering on this subscription.

### 10.4.3 Key management

AAEP does not standardize key distribution. Implementers may use:

- **Certificate authority infrastructure:** Producers sign with keys that chain to a CA the subscriber trusts (typical for enterprise deployments).
- **Public key directories:** Subscribers maintain a directory of trusted producer keys, populated by configuration.
- **DNS-based key discovery:** Producers publish keys via DNSSEC-signed TXT records at well-known names.
- **Web-of-trust:** Subscribers trust keys signed by other trusted parties (less common but supported by JWS).

The choice depends on deployment context. The conformance test suite verifies that signed manifests are valid JWS but does not enforce a specific key distribution mechanism.

## 10.5 Privacy considerations

AAEP carries information about agent activity, including potentially-sensitive content. Implementers MUST consider:

### 10.5.1 Event content sensitivity

Event payloads may include:

- User requests (e.g., the `request_text` field on `agent.session.started`).
- Tool inputs (e.g., `args_summary` on `agent.tool.invoked`).
- Agent outputs (e.g., `chunk` on `agent.output.streaming`).

This content may be confidential, sensitive, or regulated. Producers MUST consider the privacy implications of every field they populate. The principle of data minimization applies: include only what is necessary for the subscriber to fulfill its purpose.

### 10.5.2 Logging and retention

Subscribers and infrastructure intermediaries (proxies, observability platforms) may log AAEP events. Implementers SHOULD:

- Define a retention policy for AAEP event logs.
- Redact sensitive content from logs (using extensions like a hypothetical `privacy:` extension marking sensitive fields).
- Limit access to AAEP logs to authorized personnel.
- Provide users with mechanisms to request deletion of AAEP events relating to their activity (where regulations like GDPR or CCPA apply).

### 10.5.3 Cross-subscriber leakage

When a producer has multiple subscribers, events emitted to one subscriber are observable by all that match the filters. Producers MUST consider whether sensitive content should be filtered per subscriber identity. For example, an `auditor` subscription might receive full PII while an `accessibility_consumer` subscription receives only summary data.

This is implemented by tailoring `event_filters` and per-subscriber summary content; AAEP supports the pattern but does not enforce it.

## 10.6 Security audit recommendations

Before deploying AAEP to production with safety-critical actions, organizations SHOULD conduct a security audit covering:

1. **Transport security:** TLS version, cipher suites, certificate validation, mTLS configuration.
2. **Authentication:** Identity provider, token validation, key rotation policy.
3. **Authorization:** Mapping of authenticated identities to AAEP capabilities.
4. **Confirmation flow review:** Verify `default_decision` is correct per Chapter 6 §6.4.1 for every action type.
5. **Producer manifest:** Verify signed manifest if Level 3; verify accuracy of claimed capabilities.
6. **Extension review:** Audit all AAEP extensions used for spec quality and threat model.
7. **Logging and retention:** Verify logs do not retain sensitive content beyond necessity.
8. **Conformance test results:** Run the conformance suite and review the report.

Organizations operating in regulated industries SHOULD additionally:

- Map AAEP requirements to applicable regulations (HIPAA, GDPR, PCI-DSS, etc.).
- Document AAEP's role in their accessibility compliance posture.
- Include AAEP in periodic security assessments.

## 10.7 Vulnerability disclosure

The AAEP project follows a responsible disclosure process for security vulnerabilities in the specification or reference implementations. See [governance/SECURITY.md](../governance/SECURITY.md) for the disclosure process, contact addresses, and response commitments.

Implementers SHOULD subscribe to the AAEP security advisory channel (linked from [governance/SECURITY.md](../governance/SECURITY.md)) to receive notifications of relevant vulnerabilities.

## 10.8 Where to go next

Readers should now proceed to [Chapter 11 (Internationalization)](11-internationalization.md), which specifies how AAEP handles languages, locales, character encoding, right-to-left text, and culturally-sensitive content.

Implementers preparing security review documentation should additionally consult [governance/SECURITY.md](../governance/SECURITY.md) for the disclosure process.
