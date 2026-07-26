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
