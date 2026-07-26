"""Export helpers for RelayX benchmark baselines."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from benchmarks.common import BenchmarkResult


def result_to_dict(result: BenchmarkResult) -> dict[str, Any]:
    return {
        "name": result.name,
        "columns": list(result.columns),
        "rows": [list(row) for row in result.rows],
    }


def write_json_report(report: Mapping[str, Any], path: str | Path) -> None:
    Path(path).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def report_to_markdown(report: Mapping[str, Any]) -> str:
    environment = report["environment"]
    results = report["results"]
    lines = [
        "# RelayX Performance Baseline",
        "",
        f"Generated: `{report['generated_at_utc']}`",
        "",
        "## Environment",
        "",
        f"- OS: `{environment['os']}`",
        f"- Machine: `{environment['machine']}`",
        f"- CPU: `{environment['cpu']}`",
        f"- CPU count: `{environment['cpu_count']}`",
        f"- RAM: `{environment['ram']}`",
        f"- Python: `{environment['python']}`",
        f"- RelayX commit: `{environment['relayx_git_commit']}`",
        "",
        "### Package Versions",
        "",
    ]
    for name, version in environment["packages"].items():
        lines.append(f"- `{name}`: `{version}`")
    lines.extend(
        [
            "",
            "## Methodology",
            "",
            "These benchmarks run from the isolated `benchmarks/` package and measure existing RelayX behavior without changing production code or protocol semantics.",
            f"Common iterations: `{report['parameters']['iterations']}`",
            f"Common warmup iterations: `{report['parameters']['warmup']}`",
            f"Mode: `{report['parameters']['mode']}`",
            "",
            "## Results",
            "",
        ]
    )
    for result in results:
        lines.extend(
            [
                f"### {result['name']}",
                "",
                _markdown_table(tuple(result["columns"]), result["rows"]),
                "",
            ]
        )
    lines.extend(
        [
            "## Limitations",
            "",
            "- Results are comparable only across runs with the same benchmark command, host class, CPU limits, Python version, dependency versions, and RelayX settings.",
            "- Timing benchmarks are measurements, not pass/fail tests; use repeated runs to identify meaningful changes.",
            "- In-process ASGI benchmarks remove external network variability and are best for RelayX baseline comparisons, not public internet latency estimates.",
            "- Replay-cache and large-payload results depend strongly on available memory and host load.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_markdown_report(report: Mapping[str, Any], path: str | Path) -> None:
    Path(path).write_text(report_to_markdown(report))


def _markdown_table(columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    header = "| " + " | ".join(str(column) for column in columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join([header, divider, *body])
