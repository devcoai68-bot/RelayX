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
