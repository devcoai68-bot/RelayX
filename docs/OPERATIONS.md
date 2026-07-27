# RelayX Operations

RelayX operational commands do not change the v1 protocol, packet format, crypto, replay protection, parser behavior, or benchmark methodology.

## CLI commands

- `relayx server` and `relayx client` remain backward compatible.
- `relayx config init|show|validate` manages `.env` configuration.
- `relayx generate-secret` creates an auth token and 32-byte base64 encryption key.
- `relayx install service` installs a hardened systemd unit.
- `relayx service status|start|stop|restart` delegates to `systemctl`.
- `relayx uninstall service` removes only the unit unless `--purge` is supplied.
- `relayx doctor` reports PASS, WARNING, and ERROR diagnostics.
- `relayx version` prints RelayX, Python, OpenSSL, Git, and platform details.

## Service upgrade

```sh
python -m pip install --upgrade 'git+https://github.com/devcoai68-bot/RelayX.git'
sudo systemctl restart relayx.service
relayx version
```

## Service uninstall

```sh
sudo relayx uninstall service
```

Configuration is retained. To intentionally delete the default environment file and working directory:

```sh
sudo relayx uninstall service --purge
```

## Secret rotation

Generate new values:

```sh
relayx generate-secret
```

Edit the environment file, update `RELAYX_AUTH_TOKEN` and `RELAYX_ENCRYPTION_KEY`, deploy the matching client values, then restart:

```sh
sudo systemctl restart relayx.service
```

## Changing ports

Update `RELAYX_SERVER_PORT` in the environment file or reinstall the unit with an override:

```sh
sudo relayx install service --port 8179
sudo systemctl restart relayx.service
```

## Changing keys

RelayX does not negotiate keys. Update both server and clients atomically during a maintenance window, then restart processes that consume the environment.

## Config migration

Create a fresh template, compare it with the deployed file, copy any new non-secret limits, and keep production secrets unless rotating them:

```sh
relayx config init --output relayx.new.env --generate-secrets
relayx config validate --config relayx.new.env
relayx config validate --config /etc/relayx/relayx.env
```

## Diagnostics

```sh
relayx doctor --config /etc/relayx/relayx.env
relayx service status
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

## Operational CLI reference

The operational CLI preserves `relayx server` and `relayx client` while adding administrator commands:

- `relayx init` creates a first-run configuration with generated secrets and prints next steps.
- `relayx generate-secret` prints an auth token and independent base64 encryption key.
- `relayx config init|show|validate` manages environment-file based configuration.
- `relayx install service` writes a hardened systemd unit, reloads systemd, enables the service, and optionally starts it.
- `relayx service status|start|stop|restart` delegates to systemd for the configured service name.
- `relayx uninstall service` stops/disables the service, removes the unit, reloads systemd, and only deletes config/working paths when `--purge` is explicit.
- `relayx doctor` reports PASS/WARNING/ERROR diagnostics for runtime dependencies, config, secrets, permissions, systemd, Docker, and nginx.
- `relayx version` prints RelayX, Python, OpenSSL, Git commit, and platform information.

### Service upgrade

```sh
python -m pip install --upgrade 'git+https://github.com/devcoai68-bot/RelayX.git'
sudo systemctl restart relayx.service
relayx version
```

### Service uninstall

```sh
sudo relayx uninstall service
```

Configuration is retained. To intentionally delete the default environment file and working directory:

```sh
sudo relayx uninstall service --purge
```

### Secret rotation

Generate new values:

```sh
relayx generate-secret
```

Edit the server environment file, deploy matching client values, then restart the processes that consume those variables:

```sh
sudo systemctl restart relayx.service
```

### Changing ports

Update `RELAYX_SERVER_PORT` in the environment file or reinstall with a unit-level override:

```sh
sudo relayx install service --port 8179
sudo systemctl restart relayx.service
```

### Changing keys

RelayX does not negotiate keys. Update server and clients atomically during a maintenance window, then restart each process using the environment.

### Config migration

Create a fresh template, compare it with the deployed file, copy new non-secret limits, and keep production secrets unless rotating them:

```sh
relayx config init --output relayx.new.env --generate-secrets
relayx config validate --config relayx.new.env
relayx config validate --config /etc/relayx/relayx.env
```
