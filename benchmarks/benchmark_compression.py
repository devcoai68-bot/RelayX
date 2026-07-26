from __future__ import annotations

import time

from relayx.compression import maybe_compress, maybe_decompress
from benchmarks.common import PAYLOAD_SIZES, BenchmarkResult, deterministic_payload, format_bytes, parse_common_args, run_profile


def benchmark(iterations: int, warmup: int) -> BenchmarkResult:
    rows = []
    thresholds = (0, 1024, 64 * 1024)
    for threshold in thresholds:
        for size in PAYLOAD_SIZES:
            payload = deterministic_payload(size)
            for _ in range(warmup):
                compressed, flag = maybe_compress(payload, True, threshold)
                maybe_decompress(compressed, flag, size * 2)
            start = time.perf_counter()
            compressed_results = [maybe_compress(payload, True, threshold) for _ in range(iterations)]
            compression_seconds = time.perf_counter() - start
            start = time.perf_counter()
            for compressed, flag in compressed_results:
                maybe_decompress(compressed, flag, size * 2)
            decompression_seconds = time.perf_counter() - start
            compressed_size = len(compressed_results[-1][0])
            rows.append((format_bytes(size), format_bytes(threshold), f"{compressed_size / size:.4f}", f"{compression_seconds / iterations * 1000:.3f}", f"{decompression_seconds / iterations * 1000:.3f}", str(compressed_results[-1][1])))
    return BenchmarkResult("compression", ("payload", "threshold", "ratio", "compress ms", "decompress ms", "compressed"), tuple(rows))


def main() -> None:
    args = parse_common_args("Benchmark RelayX optional zstd compression")
    runner = lambda: benchmark(args.iterations, args.warmup)
    result = run_profile(runner, args.profile_output) if args.profile else runner()
    print(result.as_table())


if __name__ == "__main__":
    main()
