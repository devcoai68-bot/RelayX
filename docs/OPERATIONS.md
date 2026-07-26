# RelayX Operations Guide

## Monitoring goals

Monitor availability, readiness, latency, error rates, process resource use, replay-cache pressure, and reverse-proxy behavior. RelayX is fully buffered, so memory and timeout monitoring are especially important.

## Health endpoint

`GET /health` confirms the application process is running.

```sh
curl -f http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

Use this endpoint for basic process liveness checks.

## Ready endpoint

`GET /ready` confirms the replay cache is initialized and the forwarder is available.

```sh
curl -f http://127.0.0.1:8000/ready
```

Expected response includes `"status":"ready"`. Use this endpoint for load balancer readiness checks.

## Resource monitoring

### CPU

High CPU may indicate high encryption/decryption throughput, compression work, or benchmark traffic.

```sh
top -p $(pgrep -f 'relayx server')
```

### RAM

Memory use grows with concurrent buffered carrier bodies, decompressed packets, request bodies, and upstream responses.

```sh
ps -o pid,rss,cmd -p $(pgrep -f 'relayx server')
```

Keep `RELAYX_MAX_REQUEST_BODY_BYTES`, `RELAYX_MAX_RESPONSE_BODY_BYTES`, `RELAYX_MAX_CARRIER_BODY_BYTES`, and `RELAYX_MAX_DECOMPRESSED_BYTES` aligned with available RAM and concurrency.

### File descriptors

```sh
cat /proc/$(pgrep -f 'relayx server')/limits | grep 'Max open files'
ls /proc/$(pgrep -f 'relayx server')/fd | wc -l
```

Recommended systemd value: `LimitNOFILE=65536` for production deployments.

## Timeouts

RelayX uses `RELAYX_TIMEOUT_SECONDS` for upstream HTTP operations and graceful shutdown drain. nginx `proxy_read_timeout` and `proxy_send_timeout` should be at least as large as this value. Avoid very large timeout values unless upstream latency requires them.

## Restart strategy

systemd recommendation:

```ini
Restart=on-failure
RestartSec=5
TimeoutStopSec=45
```

Docker Compose recommendation:

```yaml
restart: unless-stopped
```

## Log rotation

For systemd-journald deployments, configure retention in `/etc/systemd/journald.conf`. For nginx logs, use the distribution logrotate package. RelayX logs are structured JSON on stdout/stderr and intentionally avoid bearer tokens, encryption keys, authorization headers, and request/response bodies.

## systemd recommendations

Use a dedicated unprivileged user, read-only filesystem protections, private temporary directories, no new privileges, and explicit environment files with mode `0600`.

## Docker recommendations

- Run with the image's non-root user.
- Pass secrets through an environment file or secret manager.
- Set memory limits that reflect RelayX body limits.
- Publish the RelayX port only to a trusted reverse proxy network when possible.
- Use health checks against `/health` and readiness checks against `/ready` at the orchestrator level.

## nginx recommendations

- Preserve `Authorization` and `Content-Type` headers.
- Force HTTP/1.1 upstream proxying.
- Set `client_max_body_size` to match `RELAYX_MAX_CARRIER_BODY_BYTES`.
- Disable response buffering for predictable relay latency.
- Use TLS and modern cipher settings.
- Restrict `/relay` to POST traffic when practical.

## Backup recommendations

Back up only deployment metadata and secrets that are required for continuity:

- `/etc/relayx/server.env`
- systemd unit files
- nginx site configuration
- release version or container image digest

Protect backups because they contain credentials. Runtime replay-cache contents are intentionally not backed up.

## Recommended production settings

- `RELAYX_SERVER_HOST=127.0.0.1` behind nginx.
- `RELAYX_LOG_LEVEL=INFO` for normal production use.
- `RELAYX_TIMEOUT_SECONDS=30` unless upstream behavior requires a different value.
- Default request, response, carrier, decompressed, replay, and header limits unless capacity planning justifies changes.
- Independent high-entropy values for `RELAYX_AUTH_TOKEN` and `RELAYX_ENCRYPTION_KEY`.
- Host firewall egress rules that prevent unwanted access to metadata services or private networks if authenticated clients are not fully trusted.

## Release-candidate operational hardening

### Reverse proxy and TLS assumptions

RelayX should normally bind to `127.0.0.1` and sit behind nginx or an equivalent TLS terminator. The reverse proxy must preserve `Authorization` and `Content-Type`, must proxy to RelayX with HTTP/1.1, and should restrict `/relay` to POST. Do not expose the ASGI server directly to the Internet unless an equivalent front-end enforces TLS, body limits, connection limits, and slow-client timeouts.

Recommended nginx controls:

- `client_max_body_size` equal to or lower than `RELAYX_MAX_CARRIER_BODY_BYTES`.
- `client_body_timeout`, `proxy_read_timeout`, `proxy_send_timeout`, and `send_timeout` aligned with `RELAYX_TIMEOUT_SECONDS`.
- `proxy_request_buffering on` to keep slow upload handling in nginx rather than the Python process.
- `proxy_buffering off` for predictable relay response latency.
- `limit_except POST { deny all; }` for `/relay`.
- `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer` for operational endpoints.

### Linux resource controls

For systemd deployments, use explicit process limits and sandboxing:

```ini
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
LockPersonality=true
MemoryDenyWriteExecute=true
LimitNOFILE=65536
TasksMax=512
```

Set host or orchestrator memory limits based on worst-case concurrency. RelayX is fully buffered, so a conservative upper bound is approximately concurrent requests multiplied by carrier limit plus response limit plus decompressed limit, plus Python/runtime overhead.

Suggested host-level checks:

```sh
sysctl net.core.somaxconn
ulimit -n
systemctl show relayx -p LimitNOFILE -p TasksMax -p MemoryMax
```

### Egress and SSRF controls

RelayX forwards application HTTP requests selected by authenticated clients. If every authenticated client is fully trusted, this is expected behavior. If clients are less trusted, enforce egress policy outside RelayX with firewall rules, security groups, Kubernetes NetworkPolicy, or a controlled outbound proxy. At minimum, decide whether the relay server may reach metadata services, loopback services, RFC1918 ranges, link-local addresses, and administrative networks.

### Disaster recovery

RelayX has no durable runtime state. Disaster recovery depends on preserving deployment configuration and secrets:

1. Restore the same RelayX release or container image digest.
2. Restore `/etc/relayx/server.env` or equivalent secret-manager entries.
3. Restore reverse-proxy and systemd/orchestrator configuration.
4. Start RelayX and verify `/health` and `/ready`.
5. Run an authenticated client smoke test through `/relay`.

Replay-cache contents are intentionally not restored. After a restart, packets from before the restart are not remembered by the in-memory cache, so operators should rotate secrets or drain clients if this matters for their threat model.

### Troubleshooting FAQ

**Why do async tests fail locally with “async def functions are not natively supported”?** Install development dependencies with `python -m pip install -e '.[dev]'`; the async tests require `pytest-asyncio`.

**Why does `/relay` return 415?** The carrier request must use `Content-Type: application/octet-stream`.

**Why does the client receive `Bad Gateway`?** The local proxy maps RelayError responses to HTTP 502 with a short plaintext error. Check structured server logs for sanitized error type and request id.

**Can RelayX be horizontally scaled?** Only with sticky routing or acceptance that replay detection is per process. The v1 replay cache is intentionally in memory.

**Can I use HTTP/2, WebSocket, CONNECT, or streaming?** No. RelayX v1 is intentionally a fully buffered encrypted HTTP application relay over HTTP/1.1 POST.
