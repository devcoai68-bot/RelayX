# RelayX Installation Guide

This guide installs RelayX for a production-style HTTP/1.1 POST relay deployment.

## System requirements

- Linux server with Python 3.12 or newer.
- 1 CPU and 512 MiB RAM minimum for small tests; size RAM for concurrent fully buffered request and response bodies.
- TLS certificate for the public relay hostname.
- nginx or another HTTP/1.1 reverse proxy.
- Outbound network access from the RelayX server to intended upstream applications.

## Supported operating systems

RelayX is expected to run on current Linux distributions that provide Python 3.12, systemd, and nginx, including Ubuntu 24.04 LTS, Debian 12 with a Python 3.12 package source, Fedora, and recent container hosts. Docker deployment works on any Linux host with a current Docker Engine and Compose plugin.

## Python installation

Ubuntu example:

```sh
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv python3-pip nginx ufw
python3.12 --version
```

Expected output includes `Python 3.12`.

## Create a system user and directories

```sh
sudo useradd --system --home /opt/relayx --shell /usr/sbin/nologin relayx
sudo mkdir -p /opt/relayx /etc/relayx /var/log/relayx
sudo chown relayx:relayx /opt/relayx /var/log/relayx
```

## Install from a checkout

```sh
sudo git clone https://github.com/<owner>/<repo>.git /opt/relayx/app
cd /opt/relayx/app
sudo python3.12 -m venv /opt/relayx/venv
sudo /opt/relayx/venv/bin/python -m pip install --upgrade pip
sudo /opt/relayx/venv/bin/python -m pip install .
```

## Environment variables

Create `/etc/relayx/server.env`:

```sh
sudo install -m 0600 -o relayx -g relayx /dev/null /etc/relayx/server.env
sudo tee /etc/relayx/server.env >/dev/null <<'EOF_ENV'
RELAYX_AUTH_TOKEN=replace-with-a-long-random-bearer-token
RELAYX_ENCRYPTION_KEY=replace-with-base64-encoded-32-byte-key
RELAYX_SERVER_HOST=127.0.0.1
RELAYX_SERVER_PORT=8000
RELAYX_RELAY_URL=https://relay.example.com/relay
RELAYX_LOG_LEVEL=INFO
RELAYX_TIMEOUT_SECONDS=30
RELAYX_MAX_REQUEST_BODY_BYTES=16777216
RELAYX_MAX_RESPONSE_BODY_BYTES=67108864
RELAYX_MAX_CARRIER_BODY_BYTES=134217728
RELAYX_MAX_DECOMPRESSED_BYTES=134217728
EOF_ENV
sudo chown relayx:relayx /etc/relayx/server.env
sudo chmod 0600 /etc/relayx/server.env
```

Generate an encryption key:

```sh
python3.12 - <<'PY'
import base64, os
print(base64.b64encode(os.urandom(32)).decode())
PY
```

## TLS certificate generation

For public hosts, use ACME/Let's Encrypt:

```sh
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d relay.example.com
```

For a private test certificate:

```sh
sudo openssl req -x509 -newkey rsa:3072 -nodes -days 30 \
  -keyout /etc/ssl/private/relayx.key \
  -out /etc/ssl/certs/relayx.crt \
  -subj '/CN=relay.example.com'
```

## systemd service

Create `/etc/systemd/system/relayx.service`:

```ini
[Unit]
Description=RelayX HTTP application relay
After=network-online.target
Wants=network-online.target

[Service]
User=relayx
Group=relayx
WorkingDirectory=/opt/relayx/app
EnvironmentFile=/etc/relayx/server.env
ExecStart=/opt/relayx/venv/bin/relayx server
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/var/log/relayx
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
```

Enable it:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now relayx
sudo systemctl status relayx --no-pager
```

## nginx reverse proxy configuration

Use `examples/nginx-relayx.conf` as the baseline. Minimal server block:

```nginx
server {
    listen 443 ssl http2;
    server_name relay.example.com;

    ssl_certificate /etc/letsencrypt/live/relay.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/relay.example.com/privkey.pem;

    client_max_body_size 128m;

    location = /relay {
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header Content-Type $content_type;
        proxy_request_buffering on;
        proxy_buffering off;
        proxy_read_timeout 30s;
        proxy_send_timeout 30s;
        proxy_pass http://127.0.0.1:8000;
    }

    location = /health { proxy_pass http://127.0.0.1:8000; }
    location = /ready { proxy_pass http://127.0.0.1:8000; }
}
```

Validate and reload:

```sh
sudo nginx -t
sudo systemctl reload nginx
```

## Firewall configuration

```sh
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status verbose
```

Restrict RelayX server egress with host firewall rules if authenticated clients must not reach internal networks.

## Health and startup verification

```sh
curl -i https://relay.example.com/health
curl -i https://relay.example.com/ready
journalctl -u relayx -n 50 --no-pager
```

Expected health body:

```json
{"status":"ok"}
```

Expected readiness body includes `"status":"ready"`.

## Docker deployment

```sh
docker build -t relayx:latest .
docker run --rm --env-file .env -p 8000:8000 relayx:latest
```

## Docker Compose deployment

```sh
cp .env.example .env
# edit .env and set independent production secrets
docker compose up --build -d
docker compose ps
docker compose logs --tail=50 relayx
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
