"""Shared helpers for RelayX benchmark scripts.

The benchmark package is intentionally isolated from production code. It imports
RelayX modules to measure them, but never changes protocol behavior.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import cProfile
import io
import os
import pstats
import resource
import statistics
import time
import tracemalloc
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from relayx.config import RelaySettings

PAYLOAD_SIZES: tuple[int, ...] = (1024, 10 * 1024, 100 * 1024, 1024 * 1024, 4 * 1024 * 1024, 8 * 1024 * 1024, 16 * 1024 * 1024)
LARGE_PAYLOAD_SIZES: tuple[int, ...] = (1024 * 1024, 4 * 1024 * 1024, 8 * 1024 * 1024, 16 * 1024 * 1024)
CONCURRENCY_LEVELS: tuple[int, ...] = (1, 10, 50, 100, 200, 500)
REPLAY_CACHE_SIZES: tuple[int, ...] = (10_000, 100_000, 500_000, 1_000_000)
BENCHMARK_KEY = base64.b64encode(b"b" * 32).decode()


@dataclass(frozen=True)
class BenchmarkResult:
    name: str
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]

    def as_table(self) -> str:
        return format_table(self.columns, self.rows)


def parse_common_args(description: str, default_iterations: int = 20) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--iterations", type=int, default=default_iterations, help="Number of measured iterations per scenario.")
    parser.add_argument("--warmup", type=int, default=3, help="Warmup iterations before measurement.")
    parser.add_argument("--profile", action="store_true", help="Run the benchmark under cProfile and write a .prof text report.")
    parser.add_argument("--profile-output", default="benchmark.prof.txt", help="Path for cProfile text output when --profile is used.")
    return parser.parse_args()


def deterministic_payload(size: int, pattern: bytes = b"relayx-benchmark-") -> bytes:
    repeats, remainder = divmod(size, len(pattern))
    return pattern * repeats + pattern[:remainder]


def incompressible_payload(size: int) -> bytes:
    return bytes((index * 131 + 17) % 256 for index in range(size))


def default_settings(**overrides: Any) -> RelaySettings:
    values: dict[str, Any] = {
        "auth_token": "benchmark-auth-token",
        "encryption_key": BENCHMARK_KEY,
        "max_request_body_bytes": 32 * 1024 * 1024,
        "max_response_body_bytes": 32 * 1024 * 1024,
        "max_carrier_body_bytes": 64 * 1024 * 1024,
        "max_decompressed_bytes": 64 * 1024 * 1024,
        "log_level": "WARNING",
    }
    values.update(overrides)
    return RelaySettings(**values)


def summarize_latencies(samples_ms: Iterable[float]) -> dict[str, float]:
    samples = sorted(samples_ms)
    if not samples:
        raise ValueError("at least one latency sample is required")
    return {
        "avg_ms": statistics.fmean(samples),
        "median_ms": statistics.median(samples),
        "p95_ms": percentile(samples, 95),
        "p99_ms": percentile(samples, 99),
        "min_ms": samples[0],
        "max_ms": samples[-1],
    }


def percentile(sorted_samples: list[float], percentile_value: float) -> float:
    if len(sorted_samples) == 1:
        return sorted_samples[0]
    rank = (len(sorted_samples) - 1) * (percentile_value / 100)
    lower = int(rank)
    upper = min(lower + 1, len(sorted_samples) - 1)
    weight = rank - lower
    return sorted_samples[lower] * (1 - weight) + sorted_samples[upper] * weight


def format_bytes(value: int | float) -> str:
    units = ("B", "KiB", "MiB", "GiB")
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} GiB"


def format_table(columns: tuple[str, ...], rows: Iterable[tuple[Any, ...]]) -> str:
    rendered = [[str(cell) for cell in row] for row in rows]
    widths = [len(column) for column in columns]
    for row in rendered:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row, strict=True)]
    header = " | ".join(column.ljust(width) for column, width in zip(columns, widths, strict=True))
    divider = "-+-".join("-" * width for width in widths)
    body = [" | ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)) for row in rendered]
    return "\n".join([header, divider, *body])


def run_profile(func: Callable[[], Any], output_path: str | os.PathLike[str]) -> Any:
    profiler = cProfile.Profile()
    result = profiler.runcall(func)
    buffer = io.StringIO()
    pstats.Stats(profiler, stream=buffer).strip_dirs().sort_stats("cumtime").print_stats(50)
    Path(output_path).write_text(buffer.getvalue())
    return result


async def measure_async(call: Callable[[], Awaitable[Any]], iterations: int, warmup: int = 0) -> tuple[list[float], list[Any]]:
    for _ in range(warmup):
        await call()
    samples: list[float] = []
    results: list[Any] = []
    for _ in range(iterations):
        start = time.perf_counter()
        results.append(await call())
        samples.append((time.perf_counter() - start) * 1000)
    return samples, results


def current_rss_bytes() -> int:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if os.uname().sysname == "Darwin":
        return int(usage)
    return int(usage * 1024)


def measure_allocations(func: Callable[[], Any]) -> tuple[Any, int, int]:
    tracemalloc.start()
    snapshot_before = tracemalloc.take_snapshot()
    result = func()
    current, peak = tracemalloc.get_traced_memory()
    snapshot_after = tracemalloc.take_snapshot()
    allocation_count = sum(stat.count for stat in snapshot_after.compare_to(snapshot_before, "lineno") if stat.count > 0)
    tracemalloc.stop()
    return result, peak, allocation_count


def run_async(coro: Awaitable[Any]) -> Any:
    return asyncio.run(coro)


def hex_request_id(prefix: int, index: int) -> str:
    return f'{prefix:08x}{index:024x}'[-32:]
