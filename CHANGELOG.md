# Changelog

All notable changes to RelayX will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows semantic versioning where practical.

## [Unreleased]

### Fixed

- Made CI coverage artifact handling deterministic by verifying generated `coverage.xml` and `htmlcov/` before upload.
- Hardened operational CLI subprocess usage for Bandit by resolving executables, validating service/account names, avoiding shell execution, and narrowing exception handling.


## [1.0.0] - 2026-07-26

### Added

- v1.0.0 release notes covering architecture, security features, limitations, deployment notes, upgrade notes, and future roadmap.
- GitHub Actions CI for linting, formatting, type checking, compileall, tests, benchmark validation, security checks, and Docker builds.
- Tooling configuration for Ruff, Black, isort, mypy, coverage, Bandit, pip-audit, and pre-commit.
- Contributor, security, license, and release checklist documentation.

### Changed

- Prepared package metadata for v1.0.0 and added bounded dependency ranges for runtime dependencies.
- Hardened Docker, Docker Compose, nginx, and operations documentation for release-candidate deployments.

### Security

- Documented egress/SSRF controls, Linux resource controls, reverse-proxy requirements, and disaster recovery assumptions for production operators.

## [0.1.0] - 2026-07-25

### Added

- Protocol v1 implementation for encrypted HTTP POST carrier messages.
- ChaCha20-Poly1305 authenticated encryption and strict MsgPack schema validation.
- Replay protection with timestamp and nonce validation.
- HTTP parser hardening and complete request/response relay behavior.
- Production FastAPI server with health/readiness endpoints, structured logging, Docker deployment, nginx example, and graceful shutdown.
- Unit, integration, benchmark-validation tests, benchmark suite, and baseline report generation.
