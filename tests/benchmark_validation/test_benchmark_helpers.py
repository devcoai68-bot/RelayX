from benchmarks.benchmark_compression import benchmark as compression_benchmark
from benchmarks.benchmark_crypto import benchmark as crypto_benchmark
from benchmarks.common import (
    BenchmarkResult,
    deterministic_payload,
    format_table,
    hex_request_id,
    summarize_latencies,
)


def test_latency_summary_is_deterministic():
    summary = summarize_latencies([5.0, 1.0, 3.0, 2.0, 4.0])

    assert summary["avg_ms"] == 3.0
    assert summary["median_ms"] == 3.0
    assert summary["min_ms"] == 1.0
    assert summary["max_ms"] == 5.0


def test_table_format_contains_headers_and_rows():
    table = format_table(("payload", "latency"), (("1 KiB", "1.0 ms"),))

    assert "payload" in table
    assert "latency" in table
    assert "1 KiB" in table


def test_deterministic_payload_and_request_id_helpers():
    assert deterministic_payload(20) == deterministic_payload(20)
    request_id = hex_request_id(1, 2)
    assert len(request_id) == 32
    assert all(character in "0123456789abcdef" for character in request_id)


def test_small_crypto_benchmark_shape(monkeypatch):
    monkeypatch.setattr("benchmarks.benchmark_crypto.PAYLOAD_SIZES", (128,))
    result = crypto_benchmark(iterations=1, warmup=0)

    assert isinstance(result, BenchmarkResult)
    assert result.columns == (
        "payload",
        "encrypt MiB/s",
        "decrypt MiB/s",
        "encrypt ms",
        "decrypt ms",
    )
    assert len(result.rows) == 1


def test_small_compression_benchmark_shape(monkeypatch):
    monkeypatch.setattr("benchmarks.benchmark_compression.PAYLOAD_SIZES", (128,))
    result = compression_benchmark(iterations=1, warmup=0)

    assert isinstance(result, BenchmarkResult)
    assert result.columns == (
        "payload",
        "threshold",
        "ratio",
        "compress ms",
        "decompress ms",
        "compressed",
    )
    assert len(result.rows) == 3
