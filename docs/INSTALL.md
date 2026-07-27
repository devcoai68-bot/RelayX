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
