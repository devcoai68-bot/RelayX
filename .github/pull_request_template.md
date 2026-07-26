## Summary
- 

## Testing
- [ ] `pytest`
- [ ] `ruff check relayx benchmarks tests`
- [ ] `black --check relayx benchmarks tests`
- [ ] `isort --check-only relayx benchmarks tests`
- [ ] `mypy relayx benchmarks tests`
- [ ] `bandit -r relayx benchmarks`
- [ ] `pip-audit`
- [ ] `python -m build`
- [ ] `docker build -t relayx:ci .`

## Release impact
- [ ] No RelayX v1 protocol changes
- [ ] No public API or CLI behavioral changes unless documented as a bug fix
- [ ] Documentation updated when operator-facing behavior changed
