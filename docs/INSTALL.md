# RelayX Installation

RelayX is a PEP 517/518 Python package. Package metadata and console scripts are defined in `pyproject.toml`; no `setup.py` is required.

## Requirements

- Python 3.12 or newer
- OpenSSL supported by `cryptography`
- systemd for native service installation (optional)
- Docker or Docker Compose for container deployment (optional)

## Install from GitHub without cloning

```sh
python -m pip install 'git+https://github.com/devcoai68-bot/RelayX.git'
```

For isolated application installs:

```sh
pipx install 'git+https://github.com/devcoai68-bot/RelayX.git'
```

## Local and editable installs

```sh
python -m pip install .
python -m pip install -e .
```

## Build and package checks

```sh
python -m build
python -m twine check dist/*
```

## First-run setup

```sh
relayx init --output .env --force
relayx config validate --config .env
relayx server --config .env
```

## systemd install

Preview the service file and system changes:

```sh
relayx install service --dry-run --host 0.0.0.0 --port 8179 --environment-file /etc/relayx/relayx.env
```

Install and start:

```sh
sudo install -d -m 700 /etc/relayx
sudo relayx config init --output /etc/relayx/relayx.env --generate-secrets --port 8179
sudo relayx install service --host 0.0.0.0 --port 8179 --create-user --start
```

## Docker

```sh
relayx config init --output .env --generate-secrets
docker build -t relayx .
docker run --env-file .env -p 8000:8000 relayx
```

## Docker Compose

```sh
relayx config init --output .env --generate-secrets
docker compose up --build -d
```

## Production checklist

- [ ] TLS enabled and tested.
- [ ] Strong independent bearer token and encryption key configured.
- [ ] RelayX bound to loopback behind nginx or intentionally firewalled.
- [ ] Body, carrier, decompression, replay, and timeout limits sized for host memory.
- [ ] Health and readiness checks monitored.
- [ ] Log retention configured.
- [ ] Docker or systemd restart strategy configured.
- [ ] Egress firewall rules reviewed.

## Log locations

- systemd: `journalctl -u relayx`
- nginx: `/var/log/nginx/access.log` and `/var/log/nginx/error.log`
- Docker: `docker compose logs relayx`

## Upgrade procedure

```sh
cd /opt/relayx/app
sudo git fetch --tags
sudo git checkout v<version>
sudo /opt/relayx/venv/bin/python -m pip install .
sudo systemctl restart relayx
curl -f https://relay.example.com/ready
```

## Backup procedure

Back up deployment configuration and release metadata:

```sh
sudo tar -czf relayx-backup-$(date +%F).tgz /etc/relayx /etc/nginx/sites-enabled /etc/systemd/system/relayx.service
```

Do not store backups containing secrets in public artifact systems.

## Rollback procedure

```sh
cd /opt/relayx/app
sudo git checkout v<previous-version>
sudo /opt/relayx/venv/bin/python -m pip install .
sudo systemctl restart relayx
curl -f https://relay.example.com/ready
```

## Common troubleshooting

- `401 Unauthorized`: verify the client and server use the same bearer token.
- `415 Unsupported Media Type`: ensure carrier requests use `Content-Type: application/octet-stream`.
- `502 Bad Gateway` from the local client: inspect RelayError text and server logs.
- `/ready` returns 503: confirm the RelayX process initialized and the forwarder client is open.
- Large transfers fail: compare nginx `client_max_body_size` with RelayX carrier and body limits.
- Timeouts: check `RELAYX_TIMEOUT_SECONDS`, nginx proxy timeouts, and upstream responsiveness.

## Dependency files

RelayX keeps canonical dependency ranges in `pyproject.toml`. The `requirements.txt` file mirrors runtime dependencies for scanners, Docker-adjacent tooling, and operators that prefer requirements-based installation. The `requirements-dev.txt` file adds CI and local development tools. A fully pinned lock file is intentionally not committed for v1.0.0 because RelayX is a library-style Python package intended to be resolved by the target environment; deployment operators may generate their own lock with their approved index and platform constraints.

## Direct GitHub and pipx installation

RelayX is packaged through `pyproject.toml` using the PEP 517 `setuptools.build_meta` backend, and package metadata remains authoritative there. The repository intentionally does not require a legacy `setup.py` wrapper.

Install directly from GitHub without cloning:

```sh
python -m pip install 'git+https://github.com/devcoai68-bot/RelayX.git'
```

Install as an isolated CLI application with pipx:

```sh
pipx install 'git+https://github.com/devcoai68-bot/RelayX.git'
```

Local and editable installs remain supported:

```sh
python -m pip install .
python -m pip install -e .
```

Build and verify distribution artifacts:

```sh
python -m build
python -m twine check dist/*
```

## First-run installer workflow

Generate a production-ready `.env`, validate it, and start a local server:

```sh
relayx init --output .env --force
relayx config validate --config .env
relayx server --config .env
```

Preview a hardened systemd service installation:

```sh
relayx install service --dry-run --host 0.0.0.0 --port 8179 --environment-file /etc/relayx/relayx.env --memory-max 512M
```

Install and start the systemd service on a host where you have root privileges:

```sh
sudo install -d -m 700 /etc/relayx
sudo relayx config init --output /etc/relayx/relayx.env --generate-secrets --port 8179
sudo relayx install service --host 0.0.0.0 --port 8179 --create-user --start
```
