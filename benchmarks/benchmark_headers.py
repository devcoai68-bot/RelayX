from __future__ import annotations

import time

from relayx.http.headers import filter_forward_headers
from benchmarks.common import BenchmarkResult, format_bytes, parse_common_args, run_profile


def _headers(count: int, size: int, duplicate: bool = False, cookie: bool = False) -> tuple[tuple[str, str], ...]:
    if cookie:
        return (("cookie", "x" * size),) + tuple((f"x-header-{i}", "v") for i in range(max(0, count - 1)))
    if duplicate:
        return tuple(("x-duplicate", "x" * size) for _ in range(count))
    return tuple((f"x-header-{i}", "x" * size) for i in range(count))


def benchmark(iterations: int, warmup: int) -> BenchmarkResult:
    scenarios = (
        (10, 32, False, False, "small"),
        (100, 32, False, False, "many"),
        (100, 512, False, False, "large-values"),
        (100, 32, True, False, "duplicates"),
        (10, 8192, False, True, "large-cookie"),
    )
    rows = []
    for count, size, duplicate, cookie, label in scenarios:
        headers = _headers(count, size, duplicate, cookie)
        for _ in range(warmup):
            tuple(filter_forward_headers(headers))
        start = time.perf_counter()
        filtered_count = 0
        for _ in range(iterations):
            filtered_count = len(tuple(filter_forward_headers(headers)))
        seconds = time.perf_counter() - start
        rows.append((label, str(count), format_bytes(size), str(filtered_count), f"{iterations / seconds:.2f}", f"{seconds / iterations * 1000:.4f}"))
    return BenchmarkResult("headers", ("scenario", "headers", "value size", "forwarded", "ops/s", "ms/op"), tuple(rows))


def main() -> None:
    args = parse_common_args("Benchmark RelayX HTTP header filtering", default_iterations=50_000)
    runner = lambda: benchmark(args.iterations, args.warmup)
    result = run_profile(runner, args.profile_output) if args.profile else runner()
    print(result.as_table())


if __name__ == "__main__":
    main()
