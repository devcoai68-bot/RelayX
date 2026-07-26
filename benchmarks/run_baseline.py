"""Run all RelayX benchmarks and export reproducible baseline reports."""
from __future__ import annotations

import argparse
import contextlib
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from benchmarks import benchmark_compression, benchmark_crypto, benchmark_headers, benchmark_large_payloads, benchmark_latency, benchmark_memory, benchmark_replay, benchmark_throughput
from benchmarks.common import LARGE_PAYLOAD_SIZES, PAYLOAD_SIZES, REPLAY_CACHE_SIZES, BenchmarkResult, run_async
from benchmarks.environment import capture_environment
from benchmarks.export import result_to_dict, write_json_report, write_markdown_report


QUICK_PAYLOAD_SIZES = (1024, 10 * 1024, 100 * 1024)
QUICK_LARGE_PAYLOAD_SIZES = (1024 * 1024,)
QUICK_REPLAY_CACHE_SIZES = (10_000,)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the RelayX performance baseline suite and export JSON/Markdown reports.")
    parser.add_argument("--iterations", type=int, default=5, help="Measured iterations for most benchmarks.")
    parser.add_argument("--warmup", type=int, default=1, help="Warmup iterations for most benchmarks.")
    parser.add_argument("--throughput-iterations", type=int, default=None, help="Measured requests for throughput; defaults to --iterations.")
    parser.add_argument("--replay-iterations", type=int, default=None, help="Measured replay cache operations; defaults to --iterations.")
    parser.add_argument("--memory-iterations", type=int, default=1, help="Measured iterations for allocation-heavy memory benchmark.")
    parser.add_argument("--output-dir", default="benchmarks/results", help="Directory for machine-readable JSON results.")
    parser.add_argument("--markdown-output", default="docs/performance-baseline.md", help="Markdown baseline report path.")
    parser.add_argument("--date", default=date.today().isoformat(), help="Date stamp for JSON filename in YYYY-MM-DD format.")
    parser.add_argument("--full", action="store_true", help="Use full Phase 5 payload and replay-cache sizes. Defaults to quick mode for routine reproducible runs.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_baseline(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"baseline-{args.date}.json"
    markdown_path = Path(args.markdown_output)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_report(report, json_path)
    write_markdown_report(report, markdown_path)
    print(f"Wrote JSON baseline: {json_path}")
    print(f"Wrote Markdown baseline: {markdown_path}")


def run_baseline(args: argparse.Namespace) -> dict[str, Any]:
    mode = "full" if args.full else "quick"
    with _benchmark_size_mode(full=args.full):
        results = _run_all(args)
    return {
        "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "parameters": {
            "iterations": args.iterations,
            "warmup": args.warmup,
            "throughput_iterations": args.throughput_iterations or args.iterations,
            "replay_iterations": args.replay_iterations or args.iterations,
            "memory_iterations": args.memory_iterations,
            "mode": mode,
        },
        "environment": capture_environment(),
        "results": [result_to_dict(result) for result in results],
    }


def _run_all(args: argparse.Namespace) -> tuple[BenchmarkResult, ...]:
    throughput_iterations = args.throughput_iterations or args.iterations
    replay_iterations = args.replay_iterations or args.iterations
    return (
        run_async(benchmark_latency.benchmark_async(args.iterations, args.warmup)),
        run_async(benchmark_throughput.benchmark_async(throughput_iterations, args.warmup)),
        benchmark_compression.benchmark(args.iterations, args.warmup),
        benchmark_crypto.benchmark(args.iterations, args.warmup),
        benchmark_replay.benchmark(replay_iterations, args.warmup),
        benchmark_headers.benchmark(args.iterations, args.warmup),
        benchmark_memory.benchmark(args.memory_iterations, args.warmup),
        run_async(benchmark_large_payloads.benchmark_async(args.iterations, args.warmup)),
    )


@contextlib.contextmanager
def _benchmark_size_mode(full: bool) -> Iterator[None]:
    if full:
        yield
        return
    original_values = {
        benchmark_latency: ("PAYLOAD_SIZES", benchmark_latency.PAYLOAD_SIZES, QUICK_PAYLOAD_SIZES),
        benchmark_compression: ("PAYLOAD_SIZES", benchmark_compression.PAYLOAD_SIZES, QUICK_PAYLOAD_SIZES),
        benchmark_crypto: ("PAYLOAD_SIZES", benchmark_crypto.PAYLOAD_SIZES, QUICK_PAYLOAD_SIZES),
        benchmark_large_payloads: ("LARGE_PAYLOAD_SIZES", benchmark_large_payloads.LARGE_PAYLOAD_SIZES, QUICK_LARGE_PAYLOAD_SIZES),
        benchmark_memory: ("LARGE_PAYLOAD_SIZES", benchmark_memory.LARGE_PAYLOAD_SIZES, QUICK_LARGE_PAYLOAD_SIZES),
        benchmark_replay: ("REPLAY_CACHE_SIZES", benchmark_replay.REPLAY_CACHE_SIZES, QUICK_REPLAY_CACHE_SIZES),
    }
    try:
        for module, (name, _original, quick_value) in original_values.items():
            setattr(module, name, quick_value)
        yield
    finally:
        for module, (name, original, _quick_value) in original_values.items():
            setattr(module, name, original)


if __name__ == "__main__":
    main()
