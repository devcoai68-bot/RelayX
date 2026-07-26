# Contributing to RelayX

Thank you for improving RelayX. This project is a secure HTTP application relay that transports complete HTTP requests and responses inside encrypted HTTP POST carrier messages.

## Project structure

- `relayx/`: production package, including crypto, protocol codecs, HTTP parsing/writing, client, server, configuration, logging, and pipeline code.
- `tests/unit/`: unit tests for protocol, compression, headers, and hardening behavior.
- `tests/integration/`: integration tests for relay and production-readiness behavior.
- `tests/benchmark_validation/`: tests that validate benchmark helpers and baseline export behavior.
- `benchmarks/`: benchmark harnesses and baseline generation utilities.
- `docs/`: generated and maintained project documentation.
- `examples/`: deployment examples such as nginx configuration.

## Development workflow

1. Create a branch for your change.
2. Install Python 3.12.
3. Install development dependencies:

   ```sh
   python -m pip install -e . -r requirements-dev.txt
   ```

4. Install pre-commit hooks:

   ```sh
   pre-commit install
   ```

5. Keep changes focused on the intended area. Protocol, packet format, AEAD, replay logic, compression behavior, parser behavior, benchmark logic, and public APIs must not change unless a dedicated protocol-change process explicitly approves it.

## Testing

Run the standard local checks before opening a pull request:

```sh
ruff check relayx benchmarks tests
black --check relayx benchmarks tests
isort --check-only relayx benchmarks tests
mypy relayx benchmarks tests
python -m compileall relayx benchmarks tests
pytest
pytest --cov=relayx --cov=benchmarks --cov-report=xml:coverage.xml --cov-report=html
```

Benchmark validation tests live under `tests/benchmark_validation/`. Full benchmark runs are useful for release validation but are not a substitute for tests.

## Coding standards

- Use Black formatting with the repository settings.
- Use isort with the Black profile.
- Keep Ruff warnings resolved.
- Keep mypy clean for changed code.
- Avoid logging secrets, bearer tokens, encryption keys, authorization headers, or request/response bodies.
- Do not wrap imports in `try`/`except` blocks.

## Pull request process

- Explain the reason for the change and summarize user-visible impact.
- Include test results and any known limitations.
- Link related issues when applicable.
- Keep PRs small enough to review.
- Update documentation and release notes when behavior, operations, or tooling changes.
