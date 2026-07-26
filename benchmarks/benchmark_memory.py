from __future__ import annotations

from relayx.pipeline import decode_message, encode_message
from relayx.protocol.models import RelayRequest
from relayx.protocol.replay import ReplayCache
from benchmarks.common import LARGE_PAYLOAD_SIZES, BenchmarkResult, default_settings, deterministic_payload, format_bytes, measure_allocations, parse_common_args, run_profile


def benchmark(iterations: int, warmup: int) -> BenchmarkResult:
    settings = default_settings()
    key = settings.encryption_key_bytes
    rows = []
    for size in LARGE_PAYLOAD_SIZES:
        request = RelayRequest("0" * 32, "POST", "https", "example.test", None, "/", "", (), deterministic_payload(size))
        for _ in range(warmup):
            packet = encode_message(request, key, compression_enabled=settings.compression_enabled, compression_threshold=settings.compression_threshold_bytes)
            decode_message(packet, key, replay_cache=ReplayCache(), max_ciphertext_bytes=settings.max_carrier_body_bytes, max_decompressed_bytes=settings.max_decompressed_bytes, max_request_body_bytes=settings.max_request_body_bytes, max_response_body_bytes=settings.max_response_body_bytes)

        def run_once():
            packet = encode_message(request, key, compression_enabled=settings.compression_enabled, compression_threshold=settings.compression_threshold_bytes)
            return decode_message(packet, key, replay_cache=ReplayCache(), max_ciphertext_bytes=settings.max_carrier_body_bytes, max_decompressed_bytes=settings.max_decompressed_bytes, max_request_body_bytes=settings.max_request_body_bytes, max_response_body_bytes=settings.max_response_body_bytes)

        peak_values = []
        allocation_counts = []
        for _ in range(iterations):
            _, peak, allocation_count = measure_allocations(run_once)
            peak_values.append(peak)
            allocation_counts.append(allocation_count)
        rows.append((format_bytes(size), format_bytes(max(peak_values)), str(max(allocation_counts)), format_bytes(max(peak_values) - size)))
    return BenchmarkResult("memory", ("payload", "peak allocations", "allocation count", "temporary growth"), tuple(rows))


def main() -> None:
    args = parse_common_args("Benchmark RelayX memory allocation behavior", default_iterations=3)
    runner = lambda: benchmark(args.iterations, args.warmup)
    result = run_profile(runner, args.profile_output) if args.profile else runner()
    print(result.as_table())


if __name__ == "__main__":
    main()
