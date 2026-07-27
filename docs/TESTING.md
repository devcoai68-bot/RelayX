# RelayX Testing Guide

## Local development setup

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e . -r requirements-dev.txt
```

Expected result: the package installs with pytest, pytest-asyncio, pytest-cov, Ruff, Black, isort, mypy, Bandit, and pip-audit.

## Static checks

```sh
ruff check relayx benchmarks tests
black --check relayx benchmarks tests
isort --check-only relayx benchmarks tests
mypy relayx benchmarks tests
python -m compileall relayx benchmarks tests
```

Expected result: each command exits with status 0.

## Unit tests

```sh
pytest tests/unit
```

Unit tests cover protocol validation, compression, HTTP header handling, parser hardening, replay errors, bounded body handling, and request correlation behavior.

## Integration tests

```sh
pytest tests/integration
```

Integration tests exercise in-process client/server/upstream round trips, health and readiness endpoints, large body handling, and graceful shutdown behavior.

## Benchmark validation tests

```sh
pytest tests/benchmark_validation
```

These tests validate benchmark helpers and baseline export shape without relying on performance thresholds.

## Full test suite

```sh
pytest
```

Expected result: all tests pass when development dependencies are installed from `requirements-dev.txt`. Async tests require `pytest-asyncio`; if it is missing, pytest reports unknown `asyncio` marks and async test failures before RelayX code runs.

## Coverage

```sh
pytest tests/unit --cov=relayx --cov=benchmarks --cov-report=xml:coverage.xml --cov-report=html:htmlcov
```

Expected outputs:

- `coverage.xml`
- `htmlcov/index.html`
- terminal coverage summary

Open the HTML report:

```sh
python -m webbrowser htmlcov/index.html
```

## CI coverage artifact validation

GitHub Actions verifies both coverage artifact paths before upload:

```sh
test -f coverage.xml && test -d htmlcov
```

This keeps coverage reporting mandatory while failing with a clear error if pytest-cov does not produce reports.

## Benchmark suite

Quick baseline:

```sh
python -m benchmarks.run_baseline --iterations 5 --warmup 1
```

Individual benchmarks:

```sh
python -m benchmarks.benchmark_latency --iterations 20 --warmup 3
python -m benchmarks.benchmark_throughput --iterations 500 --warmup 3
python -m benchmarks.benchmark_compression --iterations 20 --warmup 3
python -m benchmarks.benchmark_crypto --iterations 20 --warmup 3
python -m benchmarks.benchmark_replay --iterations 10000 --warmup 3
python -m benchmarks.benchmark_headers --iterations 50000 --warmup 3
python -m benchmarks.benchmark_memory --iterations 3 --warmup 1
python -m benchmarks.benchmark_large_payloads --iterations 5 --warmup 1
```

Benchmark results are measurements, not pass/fail assertions. Compare runs only on similar hosts with the same Python version, dependency versions, and RelayX configuration.

## Manual end-to-end testing

Terminal 1, start an upstream application:

```sh
python - <<'PY'
from fastapi import FastAPI, Response
import uvicorn
app = FastAPI()
@app.get('/hello')
def hello():
    return Response(b'hello from upstream', media_type='text/plain')
uvicorn.run(app, host='127.0.0.1', port=9000)
PY
```

Terminal 2, start RelayX server:

```sh
export RELAYX_AUTH_TOKEN='dev-token-change-me'
export RELAYX_ENCRYPTION_KEY='<base64-32-byte-key>'
relayx server
```

Terminal 3, start local client proxy:

```sh
export RELAYX_AUTH_TOKEN='dev-token-change-me'
export RELAYX_ENCRYPTION_KEY='<same-base64-32-byte-key>'
export RELAYX_RELAY_URL='http://127.0.0.1:8000/relay'
relayx client
```

Terminal 4, send a request through the local proxy:

```sh
curl -i --proxy http://127.0.0.1:8080 http://127.0.0.1:9000/hello
```

Expected body: `hello from upstream`.

## Docker testing

```sh
docker build -t relayx:test .
docker run --rm --env-file .env -p 8000:8000 relayx:test
curl -i http://127.0.0.1:8000/health
```

Expected health response: HTTP 200 and `{"status":"ok"}`.

## Real server deployment testing

```sh
curl -i https://relay.example.com/health
curl -i https://relay.example.com/ready
journalctl -u relayx -n 100 --no-pager
tail -n 100 /var/log/nginx/error.log
```

Expected result: health and readiness return HTTP 200, RelayX logs contain structured JSON, and nginx shows no upstream errors.

## Failure diagnosis

- Missing async plugin: install dev dependencies and confirm `python -m pip show pytest-asyncio`.
- Coverage flags not recognized: install `pytest-cov`.
- Import errors: run tests from the repository root or install the package editable.
- Docker unavailable: install Docker Engine or run Docker checks in CI.
- Benchmark variance: rerun on an idle host and compare medians rather than one-off samples.
