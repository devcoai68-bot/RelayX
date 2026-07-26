from __future__ import annotations

import time

from relayx.crypto.aead import open_packet, seal
from relayx.constants import TYPE_REQUEST
from benchmarks.common import PAYLOAD_SIZES, BenchmarkResult, default_settings, deterministic_payload, format_bytes, parse_common_args, run_profile


def benchmark(iterations: int, warmup: int) -> BenchmarkResult:
    key = default_settings().encryption_key_bytes
    rows = []
    for size in PAYLOAD_SIZES:
        payload = deterministic_payload(size)
        for _ in range(warmup):
            packet = seal(payload, key, TYPE_REQUEST, False)
            open_packet(packet, key, size + 1024)
        start = time.perf_counter()
        packets = [seal(payload, key, TYPE_REQUEST, False) for _ in range(iterations)]
        encrypt_seconds = time.perf_counter() - start
        start = time.perf_counter()
        for packet in packets:
            open_packet(packet, key, size + 1024)
        decrypt_seconds = time.perf_counter() - start
        mb = (size * iterations) / (1024 * 1024)
        rows.append((format_bytes(size), f"{mb / encrypt_seconds:.2f}", f"{mb / decrypt_seconds:.2f}", f"{encrypt_seconds / iterations * 1000:.3f}", f"{decrypt_seconds / iterations * 1000:.3f}"))
    return BenchmarkResult("AEAD", ("payload", "encrypt MiB/s", "decrypt MiB/s", "encrypt ms", "decrypt ms"), tuple(rows))


def main() -> None:
    args = parse_common_args("Benchmark RelayX ChaCha20-Poly1305 AEAD")
    runner = lambda: benchmark(args.iterations, args.warmup)
    result = run_profile(runner, args.profile_output) if args.profile else runner()
    print(result.as_table())


if __name__ == "__main__":
    main()
