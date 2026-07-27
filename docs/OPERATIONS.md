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
