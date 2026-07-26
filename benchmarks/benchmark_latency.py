from __future__ import annotations

from benchmarks.common import hex_request_id, PAYLOAD_SIZES, BenchmarkResult, deterministic_payload, format_bytes, parse_common_args, run_async, run_profile, summarize_latencies
from benchmarks.relay_harness import RelayBenchmarkHarness


async def benchmark_async(iterations: int, warmup: int) -> BenchmarkResult:
    rows = []
    async with RelayBenchmarkHarness() as harness:
        for size in PAYLOAD_SIZES:
            payload = deterministic_payload(size)
            for index in range(warmup):
                await harness.send(hex_request_id(size, index), payload)
            samples = []
            for index in range(iterations):
                import time
                start = time.perf_counter()
                response = await harness.send(hex_request_id(size + 1, index), payload)
                samples.append((time.perf_counter() - start) * 1000)
                if response.body != payload:
                    raise RuntimeError("unexpected relay response body")
            summary = summarize_latencies(samples)
            rows.append((format_bytes(size), f"{summary['avg_ms']:.3f}", f"{summary['median_ms']:.3f}", f"{summary['p95_ms']:.3f}", f"{summary['p99_ms']:.3f}", f"{summary['min_ms']:.3f}", f"{summary['max_ms']:.3f}"))
    return BenchmarkResult("latency", ("payload", "avg ms", "median ms", "p95 ms", "p99 ms", "min ms", "max ms"), tuple(rows))


def main() -> None:
    args = parse_common_args("Benchmark RelayX end-to-end latency")
    runner = lambda: run_async(benchmark_async(args.iterations, args.warmup))
    result = run_profile(runner, args.profile_output) if args.profile else runner()
    print(result.as_table())


if __name__ == "__main__":
    main()
