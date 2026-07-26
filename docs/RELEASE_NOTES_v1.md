# RelayX v1.0.0 Release Notes

## Major Features

- Encrypted HTTP application relay over HTTP/1.1 POST with `application/octet-stream` carrier bodies.
- Fully buffered RelayRequest and RelayResponse handling for normal HTTP application traffic.
- Local HTTP proxy mode for applications that can speak ordinary HTTP through a proxy.
- FastAPI relay server with `/relay`, `/health`, and `/ready` endpoints.

## Architecture

RelayX v1 serializes strict MsgPack messages, optionally compresses them with zstd, encrypts them with ChaCha20-Poly1305, and sends them as HTTP/1.1 POST bodies. The server authenticates the carrier request with a bearer token, decrypts and validates the packet, checks replay state, forwards a normal upstream HTTP request with `httpx`, and returns an encrypted RelayResponse or RelayError.

RelayX remains intentionally not a VPN, SOCKS proxy, CONNECT tunnel, TCP tunnel, WebSocket transport, HTTP/2 transport, or streaming relay.

## Security Features

- ChaCha20-Poly1305 authenticated encryption with authenticated packet metadata.
- Independent bearer token and encryption key configuration.
- Strict MsgPack schema validation.
- Replay protection with timestamp and nonce tracking.
- Bounded carrier, decompressed, request-body, response-body, and header sizes.
- HTTP parser hardening for methods, headers, transfer-encoding rejection, duplicate `Content-Length`, duplicate `Host`, folded headers, and absolute-form authority mismatches.
- Hop-by-hop and proxy-only header filtering for forwarded requests and responses.
- Structured logging that avoids bearer tokens, encryption keys, authorization headers, and body data.

## Limitations

- No streaming; full request and response bodies are buffered.
- No HTTP/2 carrier support.
- No WebSocket transport.
- No CONNECT, SOCKS, TCP tunnel, or VPN behavior.
- Replay cache is in memory and scoped to one server process.
- Upstream egress policy is an operator responsibility.

## Known Constraints

- Size limits must be capacity-planned for the expected concurrency and payload sizes.
- Multi-process or multi-instance deployments require sticky routing or acceptance that replay protection is per process.
- Authenticated clients can select upstream HTTP targets; use firewall or network policy controls for less-trusted clients.
- Operators must provide TLS at a reverse proxy or equivalent front end for Internet-facing deployments.

## Deployment Notes

- Use Python 3.12 or newer.
- Bind RelayX to loopback behind nginx where possible.
- Preserve `Authorization` and `Content-Type` through the reverse proxy.
- Restrict `/relay` to POST and enforce carrier body limits at the reverse proxy.
- Run as an unprivileged user with systemd or container sandboxing.
- Configure health checks against `/health` and readiness checks against `/ready`.

## Upgrade Notes

- v1.0.0 preserves the v1 packet format, AAD layout, message schema, encryption algorithm, and HTTP/1.1 POST carrier behavior.
- No data migration is required because RelayX has no durable runtime state.
- Restarting clears in-memory replay state; plan maintenance windows or rotate secrets if this affects the deployment threat model.

## Breaking Changes

None for v1 packet compatibility. Local proxy parsing is stricter and rejects malformed or ambiguous HTTP/1.1 requests that were previously accepted.

## Future Roadmap

- Configurable upstream allow/deny policy for deployments with partially trusted clients.
- Parser fuzzing and longer-running concurrency stress tests.
- Metrics export for replay-cache pressure, request counts, error counts, and latency.
- Documented multi-instance replay-cache strategy for high-availability deployments.
