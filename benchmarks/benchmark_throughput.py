from __future__ import annotations

import asyncio
import time

from benchmarks.common import hex_request_id, CONCURRENCY_LEVELS, BenchmarkResult, deterministic_payload, format_bytes, parse_common_args, run_async, run_profile
from benchmarks.relay_harness import RelayBenchmarkHarness

PAYLOAD_SIZE = 64 * 1024


async def benchmark_async(iterations: int, warmup: int) -> BenchmarkResult:
    rows = []
    payload = deterministic_payload(PAYLOAD_SIZE)
    async with RelayBenchmarkHarness() as harness:
        for index in range(warmup):
            await harness.send(hex_request_id(0x70000000, index), payload)
        for concurrency in CONCURRENCY_LEVELS:
            total_requests = max(iterations, concurrency)
            batches = (total_requests + concurrency - 1) // concurrency
            completed = 0
            start = time.perf_counter()
            for batch in range(batches):
                batch_size = min(concurrency, total_requests - completed)
                await asyncio.gather(*(harness.send(hex_request_id(concurrency, batch * concurrency + item), payload) for item in range(batch_size)))
                completed += batch_size
            seconds = time.perf_counter() - start
            mb = (completed * PAYLOAD_SIZE) / (1024 * 1024)
            rows.append((str(concurrency), str(completed), format_bytes(PAYLOAD_SIZE), f"{completed / seconds:.2f}", f"{mb / seconds:.2f}"))
    return BenchmarkResult("throughput", ("concurrency", "requests", "payload", "requests/s", "MiB/s"), tuple(rows))


def main() -> None:
    args = parse_common_args("Benchmark RelayX end-to-end throughput", default_iterations=500)
    runner = lambda: run_async(benchmark_async(args.iterations, args.warmup))
    result = run_profile(runner, args.profile_output) if args.profile else runner()
    print(result.as_table())


if __name__ == "__main__":
    main()
