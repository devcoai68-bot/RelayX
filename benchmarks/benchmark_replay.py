from __future__ import annotations

import time

from relayx.protocol.replay import ReplayCache
from benchmarks.common import REPLAY_CACHE_SIZES, BenchmarkResult, format_bytes, parse_common_args, run_profile, current_rss_bytes


def _nonce(index: int) -> bytes:
    return index.to_bytes(16, "big")


def benchmark(iterations: int, warmup: int) -> BenchmarkResult:
    rows = []
    now_ms = int(time.time() * 1000)
    for target_size in REPLAY_CACHE_SIZES:
        cache = ReplayCache(window_seconds=300, max_entries=target_size + iterations + warmup + 10, allowed_clock_skew_seconds=30)
        start_rss = current_rss_bytes()
        start = time.perf_counter()
        for index in range(target_size):
            cache.check_and_store(_nonce(index), now_ms, now_ms=now_ms)
        preload_seconds = time.perf_counter() - start
        memory_bytes = max(0, current_rss_bytes() - start_rss)
        insert_start = time.perf_counter()
        for index in range(iterations):
            cache.check_and_store(_nonce(target_size + index), now_ms, now_ms=now_ms)
        insert_seconds = time.perf_counter() - insert_start
        lookup_start = time.perf_counter()
        for index in range(iterations):
            _nonce(index) in cache._seen
        lookup_seconds = time.perf_counter() - lookup_start
        purge_start = time.perf_counter()
        cache._purge(now_ms + 301_000)
        purge_seconds = time.perf_counter() - purge_start
        rows.append((f"{target_size:,}", f"{iterations / insert_seconds:.2f}", f"{iterations / lookup_seconds:.2f}", f"{preload_seconds:.3f}", f"{purge_seconds:.3f}", format_bytes(memory_bytes)))
    return BenchmarkResult("replay", ("entries", "insert ops/s", "lookup ops/s", "preload s", "purge s", "rss growth"), tuple(rows))


def main() -> None:
    args = parse_common_args("Benchmark RelayX replay cache", default_iterations=10_000)
    runner = lambda: benchmark(args.iterations, args.warmup)
    result = run_profile(runner, args.profile_output) if args.profile else runner()
    print(result.as_table())


if __name__ == "__main__":
    main()
