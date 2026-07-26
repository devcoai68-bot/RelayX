# RelayX Security Audit

Audit date: 2026-07-26

## Scope

This review covered the RelayX Python package, benchmark helpers, tests, Docker assets, nginx example, configuration defaults, and project automation. The review focused on production hardening without changing the RelayX v1 wire protocol, packet layout, AEAD construction, replay format, message schema, or public API.

## Architecture overview

RelayX is a message-oriented encrypted HTTP application relay. A local client accepts complete HTTP/1.1 application requests, serializes them as strict RelayRequest messages, optionally compresses the serialized bytes, encrypts them with ChaCha20-Poly1305, and sends the ciphertext as an ordinary HTTP/1.1 POST body with `Content-Type: application/octet-stream`. The relay server authenticates the carrier with `Authorization: Bearer <token>`, decrypts and validates the message, forwards the complete request with `httpx`, buffers the complete upstream response, encrypts a RelayResponse or RelayError, and returns it as the POST response.

## Trust boundaries

- Local application to local RelayX client: local applications can ask RelayX to make HTTP or HTTPS requests.
- Local RelayX client to CDN/reverse proxy: carrier traffic is ordinary HTTP POST and must be protected by TLS in production.
- Reverse proxy/CDN to RelayX server: the server must authenticate every carrier request before decrypting or forwarding.
- RelayX server to upstream services: the server can reach any network destination allowed by host firewall, routing, and DNS.
- Operators to configuration: environment variables contain bearer tokens and encryption keys and must be treated as secrets.

## Threat model

RelayX assumes attackers may observe, replay, delay, reorder, truncate, corrupt, or forge carrier HTTP requests. Attackers may also send unauthenticated carrier traffic to the server, send malformed HTTP requests to the local client, or operate malicious upstream HTTP servers. RelayX does not assume a compromised bearer token or encryption key remains safe; either secret compromise enables unauthorized relay use, and encryption-key compromise enables packet creation and decryption.

## Attacker model

- Network attacker without secrets: can cause transport failures and send invalid carrier packets, but cannot produce valid AEAD tags.
- Authenticated client with bearer token and encryption key: can request server-side HTTP/HTTPS destinations allowed by deployment policy.
- Malicious upstream: can return large bodies, many headers, unusual status text, or slow responses.
- Local user on the client host: can send requests to the local proxy bind address.

## Findings

### RX-AUDIT-001: Oversized carrier chunks were buffered before limit rejection

Status: fixed.

The FastAPI carrier-body reader appended each incoming ASGI chunk to a `bytearray` and then checked whether the total exceeded `RELAYX_MAX_CARRIER_BODY_BYTES`. A very large single chunk could therefore be buffered before rejection. The fix checks the remaining allowed byte budget before extending the buffer, preserving the same 413 behavior while reducing peak memory exposure.

### Reviewed areas with no code change required

- AEAD: ChaCha20-Poly1305 uses random 96-bit AEAD nonces and authenticates the fixed header as associated data.
- Replay: replay insertion occurs after AEAD authentication and timestamp validation, matching the intended design.
- MsgPack schema: strict map keys, exact field sets, primitive type checks, and dataclass validation reject malformed messages.
- HTTP parser: rejects CONNECT, non-HTTP/1.1 requests, transfer encoding, duplicate Content-Length, invalid Content-Length, overlarge headers, and overlarge bodies.
- Header handling: removes hop-by-hop and proxy-only headers and rejects CR/LF in serialized header values.
- Logging: structured logging excludes configured secret fields and operational logs do not include request/response bodies, bearer tokens, or encryption keys.
- Error packets: server-side exception mapping returns generic RelayError messages and does not include raw exception text.
- Defaults: request, response, carrier, decompressed, header, timeout, replay-window, replay-cache, compression-threshold, and logging defaults are conservative for a buffered relay.

## Authentication review

Carrier authentication uses a bearer token and constant-time comparison. Invalid or missing credentials receive a generic 401 response. Operators must use strong random tokens and TLS; bearer authentication alone does not protect credentials on plaintext networks.

## Crypto review

Packets use ChaCha20-Poly1305 with authenticated associated data covering magic, version, type, flags, reserved byte, timestamp, replay nonce id, and AEAD nonce. Ciphertext length is outside AEAD but is independently validated against the actual packet length and configured maximum. The encryption key is provided by configuration as a base64-encoded 32-byte value and is rejected if it equals the bearer token.

## Replay review

The replay cache validates nonce size, timestamp window, future skew, duplicates, and maximum entries. The cache is in-memory and per process. Multi-process or multi-node deployments require sticky routing or an external replay-coordination design; otherwise replay detection is scoped to each process.

## Compression review

Compression is optional and threshold based. Decompression uses a configured maximum output size. Invalid or oversized compressed data is mapped to a generic packet-processing error. Operators should keep decompressed and carrier limits aligned with available memory.

## HTTP parser review

The local parser is intentionally small and fully buffered. It supports HTTP/1.1 request messages, rejects CONNECT and transfer encoding, requires Host for origin-form targets, enforces header and body limits, and rejects duplicate Content-Length. It is not a general-purpose browser proxy and should be bound to loopback unless local network clients are intentionally trusted.

## Header filtering review

RelayX strips hop-by-hop headers, proxy-only headers, and tokens nominated by the Connection header. This reduces request smuggling and proxy confusion risk. Application headers remain end-to-end and are subject to RelayRequest/RelayResponse validation.

## Configuration review

Required secrets have no built-in defaults. Numeric limits must be positive, compression threshold and clock skew must be non-negative, ports must be valid, and log levels are constrained. Default bind addresses are loopback. Production deployments should set explicit limits that match available memory and expected payload sizes.

## Logging review

Structured logs are suitable for operational telemetry and avoid secrets by construction when data is supplied via the `relayx` extra mapping. Operators should still restrict log access because request identifiers, paths, status, and error classes can reveal operational metadata.

## Known limitations and remaining risks

- RelayX is not a VPN, CONNECT tunnel, SOCKS proxy, streaming proxy, WebSocket transport, HTTP/2 transport, or TCP tunnel.
- The server forwards requests to destinations supplied by authenticated clients; deploy firewall and egress policy if SSRF-style access to internal networks is not acceptable.
- Replay cache state is process-local and not durable across restarts.
- Fully buffered operation means concurrent large requests and responses consume memory.
- If both bearer token and encryption key are compromised, an attacker can create valid carrier traffic.
- Carrier metadata such as destination IP of the relay server, timing, and approximate packet sizes can remain visible to network observers.

## Recommended deployment practices

- Terminate TLS at nginx or another hardened reverse proxy and forward only HTTP/1.1 POST carrier traffic to RelayX.
- Bind RelayX server to loopback behind the reverse proxy where possible.
- Use strong independent secrets for `RELAYX_AUTH_TOKEN` and `RELAYX_ENCRYPTION_KEY`.
- Use firewall egress rules to restrict which upstream networks the RelayX server may reach.
- Keep conservative body and decompression limits unless memory sizing justifies larger values.
- Run as a non-root user with systemd or Docker restart policies and log rotation.

## Independent production-readiness audit update (2026-07-26)

This audit reviewed the full repository, including runtime modules, tests, benchmarks, Docker, CI, and operator documentation. The v1 wire protocol remains unchanged: encrypted RelayRequest/RelayResponse/RelayError msgpack payloads carried as HTTP/1.1 POST `application/octet-stream` packets.

### Fixes implemented in this audit

- Hardened local HTTP request parsing by validating methods and header fields before constructing RelayRequest objects, rejecting obsolete folded headers, enforcing exactly one Host header, rejecting invalid Host ports, and rejecting absolute-form targets whose authority does not match Host. This reduces request-smuggling and authority-confusion risk at the client proxy boundary.
- Hardened RelayRequest host validation to reject `@`, preventing userinfo-style authority confusion when the server constructs upstream URLs.
- Filtered hop-by-hop and proxy-only response headers before serializing upstream responses, so RelayX does not relay connection-specific metadata back across the encrypted application relay.
- Added regression tests for userinfo host smuggling, duplicate Host headers, and absolute-form Host mismatches.

### Production-readiness score after fixes

| Area | Score | Deductions |
| --- | ---: | --- |
| Architecture | 8/10 | Clear module separation, but local proxy parsing remains intentionally minimal and fully buffered. |
| Security | 7/10 | AEAD, replay protection, and size bounds are present; remaining risk is broad upstream reach if operators expose credentials to untrusted clients. |
| Protocol | 8/10 | HTTP/1.1 POST carrier is preserved; unsupported streaming, CONNECT, SOCKS, WebSocket, HTTP/2, and transfer-encoding paths are rejected. |
| Performance | 7/10 | Compression and buffering are bounded, but the proxy header reader is conservative and fully buffered by design. |
| Testing | 7/10 | Unit, integration, hardening, and benchmark validation tests exist; more fuzzing and long-running concurrency stress should be added before very high-risk deployments. |
| Documentation | 8/10 | Install, operations, testing, release, and security docs exist; operators still need deployment-specific SSRF policy documentation. |
| Deployment | 7/10 | Docker and CI exist; production reverse-proxy rate limits, WAF policy, and secret rotation are operator responsibilities. |
| Maintainability | 8/10 | Small modules and typed code; additional parser fuzzing would protect future changes. |
| Overall | 7.5/10 | Suitable for controlled production with strict operator controls, not for unauthenticated or untrusted-client public relay service. |

### Final verdict

RelayX is closer to production-ready after this audit, but I would approve public Internet deployment only when operators satisfy these assumptions:

1. Relay server access is restricted to trusted clients with high-entropy bearer tokens and independently rotated 32-byte encryption keys.
2. Operators enforce network egress policy outside the process if clients are not fully trusted, because RelayX intentionally forwards application HTTP requests selected by the authenticated client.
3. Reverse proxies or load balancers enforce request-rate limits, connection limits, TLS, and slow-client protection before traffic reaches the ASGI app.
4. Replay cache sizing is capacity-planned for peak authenticated request rate and replay-window duration.
5. CI security jobs (`bandit`, `pip-audit`, Docker build, and tests) are required before release.

Remaining v1 risks are primarily operational: SSRF-by-design for trusted clients, fully buffered memory use up to configured limits, and limited fuzz/stress coverage. A future v2 should add configurable upstream allow/deny policy, parser fuzz targets, long-running concurrency/stress tests, metrics export, and first-class rate limiting while keeping the v1 wire protocol stable for compatibility.

## RC1 final production hardening audit (2026-07-26)

The RC1 audit re-reviewed runtime code, tests, benchmark tooling, Docker, Compose, nginx, CI, release documentation, and operations guidance. No protocol, packet, AAD, encryption, replay, message-schema, or API behavior changes were made.

### Scores

| Category | Score |
| --- | ---: |
| Security | 82/100 |
| Reliability | 80/100 |
| Maintainability | 84/100 |
| Performance | 78/100 |
| Production Readiness | 81/100 |

### Remaining issues and mitigations

| Priority | Issue | Severity | Likelihood | Impact | Recommended mitigation |
| --- | --- | --- | --- | --- | --- |
| Must fix before v1 public operation | Operator egress/SSRF policy must be explicit for less-trusted clients. RelayX intentionally forwards authenticated client-selected HTTP targets. | High | Medium | Internal service exposure if credentials are given to untrusted clients. | Enforce firewall, cloud security-group, Kubernetes NetworkPolicy, or outbound proxy allowlists before Internet-facing deployment. |
| Must fix before v1 public operation | TLS, rate limits, body limits, and slow-client controls are external reverse-proxy responsibilities. | High | Medium | Credential exposure or resource exhaustion if RelayX is exposed directly without equivalent controls. | Deploy behind nginx or equivalent with POST-only `/relay`, TLS, body limits, timeouts, and connection/rate limits. |
| Recommended later | Replay cache is in-memory and single-process. | Medium | Medium | Replays may be accepted after restart or across non-sticky multi-instance routing. | Use sticky routing for v1 HA deployments; design shared replay state only in a future compatible implementation. |
| Recommended later | Parser and codec fuzzing are not yet first-class CI jobs. | Medium | Low | Malformed input edge cases may regress. | Add fuzz/property tests for HTTP parsing, MsgPack validation, decompression bounds, and packet headers. |
| Nice to have | Native metrics export is not included. | Low | Medium | Operators must infer rates and cache pressure from logs and process metrics. | Add Prometheus/OpenTelemetry metrics without changing the v1 wire protocol. |

### RC1 verdict

RelayX v1.0.0 is acceptable as a release candidate for controlled production deployments where authenticated clients are trusted and operators enforce the documented reverse-proxy, TLS, resource-limit, and egress controls. I would not approve a deployment that exposes RelayX directly to the public Internet without those controls, and I would not treat RelayX as safe for arbitrary untrusted clients until configurable upstream policy is added.
