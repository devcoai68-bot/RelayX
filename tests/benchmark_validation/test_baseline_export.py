from argparse import Namespace

from benchmarks.common import BenchmarkResult
from benchmarks.export import report_to_markdown, result_to_dict
from benchmarks.run_baseline import run_baseline


def test_result_to_dict_is_machine_readable():
    result = BenchmarkResult("sample", ("payload", "latency"), (("1 KiB", "1.0"),))

    assert result_to_dict(result) == {
        "name": "sample",
        "columns": ["payload", "latency"],
        "rows": [["1 KiB", "1.0"]],
    }


def test_report_to_markdown_contains_environment_methodology_and_results():
    report = {
        "generated_at_utc": "2026-07-25T00:00:00+00:00",
        "parameters": {"iterations": 1, "warmup": 0, "mode": "quick"},
        "environment": {
            "os": "TestOS",
            "machine": "x86_64",
            "cpu": "Test CPU",
            "cpu_count": 1,
            "ram": "1.00 GiB",
            "python": "3.12.0",
            "relayx_git_commit": "abc123",
            "packages": {"httpx": "1.0.0"},
        },
        "results": [{"name": "sample", "columns": ["payload"], "rows": [["1 KiB"]]}],
    }

    markdown = report_to_markdown(report)

    assert "## Environment" in markdown
    assert "## Methodology" in markdown
    assert "### sample" in markdown
    assert "| payload |" in markdown


def test_quick_baseline_runner_returns_all_benchmark_sections(monkeypatch):
    monkeypatch.setattr(
        "benchmarks.run_baseline.capture_environment",
        lambda: {
            "os": "test",
            "machine": "test",
            "cpu": "test",
            "cpu_count": 1,
            "ram": "1.00 GiB",
            "python": "3.12",
            "packages": {},
            "relayx_git_commit": "abc",
        },
    )
    args = Namespace(
        iterations=1,
        warmup=0,
        throughput_iterations=1,
        replay_iterations=1,
        memory_iterations=1,
        full=False,
    )

    report = run_baseline(args)

    assert report["parameters"]["mode"] == "quick"
    assert [result["name"] for result in report["results"]] == [
        "latency",
        "throughput",
        "compression",
        "AEAD",
        "replay",
        "headers",
        "memory",
        "large-payloads",
    ]
