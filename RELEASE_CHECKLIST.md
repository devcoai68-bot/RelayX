# Release Checklist

Use this checklist before publishing a RelayX release.

## Validation

- [ ] Install dependencies with Python 3.12: `python -m pip install -e '.[dev]'`.
- [ ] Run linting: `ruff check relayx benchmarks tests`.
- [ ] Run formatting checks: `black --check relayx benchmarks tests`.
- [ ] Run import-order checks: `isort --check-only relayx benchmarks tests`.
- [ ] Run type checking: `mypy relayx benchmarks tests`.
- [ ] Run compileall: `python -m compileall relayx benchmarks tests`.
- [ ] Run all tests: `pytest`.
- [ ] Generate coverage: `pytest --cov=relayx --cov=benchmarks --cov-report=xml:coverage.xml --cov-report=html`.
- [ ] Run benchmark validation: `pytest tests/benchmark_validation`.
- [ ] Capture or compare benchmark baselines as appropriate: `python -m benchmarks.run_baseline --iterations 5 --warmup 1`.
- [ ] Build Docker image: `docker build -t relayx:<version> .`.
- [ ] Run security checks: `bandit -r relayx benchmarks tests` and `pip-audit`.

## Documentation

- [ ] Update `README.md` if operations or quality tooling changed.
- [ ] Update `CHANGELOG.md` with the release date and notable changes.
- [ ] Confirm `CONTRIBUTING.md`, `SECURITY.md`, and deployment examples are current.

## Version and release

- [ ] Update the version in `pyproject.toml`.
- [ ] Commit release changes.
- [ ] Create an annotated tag: `git tag -a v<version> -m "RelayX v<version>"`.
- [ ] Push the branch and tag.
- [ ] Create a GitHub Release from the tag.
- [ ] Attach or link benchmark and coverage artifacts when useful.
