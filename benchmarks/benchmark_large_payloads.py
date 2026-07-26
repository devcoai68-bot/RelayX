from __future__ import annotations

import time

from benchmarks.common import (
    LARGE_PAYLOAD_SIZES,
    BenchmarkResult,
    deterministic_payload,
    format_bytes,
    hex_request_id,
    parse_common_args,
    run_async,
    run_profile,
    summarize_latencies,
)
from benchmarks.relay_harness import RelayBenchmarkHarness


async def benchmark_async(iterations: int, warmup: int) -> BenchmarkResult:
    rows = []
    async with RelayBenchmarkHarness() as harness:
        for size in LARGE_PAYLOAD_SIZES:
            payload = deterministic_payload(size)
            for index in range(warmup):
                await harness.send(hex_request_id(size + 2, index), payload)
            samples = []
            for index in range(iterations):
                start = time.perf_counter()
                response = await harness.send(hex_request_id(size + 3, index), payload)
                samples.append((time.perf_counter() - start) * 1000)
                if len(response.body) != size:
                    raise RuntimeError("unexpected response size")
            summary = summarize_latencies(samples)
            rows.append(
                (
                    format_bytes(size),
                    f"{summary['median_ms']:.3f}",
                    f"{summary['p95_ms']:.3f}",
                    f"{summary['max_ms']:.3f}",
                )
            )
    return BenchmarkResult(
        "large-payloads", ("request body", "median ms", "p95 ms", "max ms"), tuple(rows)
    )


def main() -> None:
    args = parse_common_args(
        "Benchmark RelayX large request body behavior", default_iterations=5
    )
    runner = lambda: run_async(benchmark_async(args.iterations, args.warmup))
    result = run_profile(runner, args.profile_output) if args.profile else runner()
    print(result.as_table())


if __name__ == "__main__":
    main()
