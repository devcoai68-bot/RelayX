# RelayX Performance Baseline

Generated: `2026-07-25T21:21:35+00:00`

## Environment

- OS: `Linux-6.12.13-x86_64-with-glibc2.39`
- Machine: `x86_64`
- CPU: `x86_64`
- CPU count: `3`
- RAM: `17.93 GiB`
- Python: `3.14.4`
- RelayX commit: `1c95fca44584b0a7be3094e8121c5a00826556cc`

### Package Versions

- `fastapi`: `0.140.0`
- `uvicorn`: `0.51.0`
- `httpx`: `0.28.1`
- `cryptography`: `49.0.0`
- `msgpack`: `1.2.1`
- `zstandard`: `0.25.0`
- `pydantic-settings`: `2.14.2`

## Methodology

These benchmarks run from the isolated `benchmarks/` package and measure existing RelayX behavior without changing production code or protocol semantics.
Common iterations: `1`
Common warmup iterations: `0`
Mode: `quick`

## Results

### latency

| payload | avg ms | median ms | p95 ms | p99 ms | min ms | max ms |
| --- | --- | --- | --- | --- | --- | --- |
| 1.00 KiB | 14.560 | 14.560 | 14.560 | 14.560 | 14.560 | 14.560 |
| 10.00 KiB | 3.245 | 3.245 | 3.245 | 3.245 | 3.245 | 3.245 |
| 100.00 KiB | 7.570 | 7.570 | 7.570 | 7.570 | 7.570 | 7.570 |

### throughput

| concurrency | requests | payload | requests/s | MiB/s |
| --- | --- | --- | --- | --- |
| 1 | 1 | 64.00 KiB | 161.97 | 10.12 |
| 10 | 10 | 64.00 KiB | 411.78 | 25.74 |
| 50 | 50 | 64.00 KiB | 395.30 | 24.71 |
| 100 | 100 | 64.00 KiB | 375.43 | 23.46 |
| 200 | 200 | 64.00 KiB | 393.69 | 24.61 |
| 500 | 500 | 64.00 KiB | 406.86 | 25.43 |

### compression

| payload | threshold | ratio | compress ms | decompress ms | compressed |
| --- | --- | --- | --- | --- | --- |
| 1.00 KiB | 0.00 B | 0.0332 | 0.035 | 0.016 | True |
| 10.00 KiB | 0.00 B | 0.0034 | 0.056 | 0.015 | True |
| 100.00 KiB | 0.00 B | 0.0004 | 0.081 | 0.053 | True |
| 1.00 KiB | 1.00 KiB | 0.0332 | 0.012 | 0.009 | True |
| 10.00 KiB | 1.00 KiB | 0.0034 | 0.015 | 0.013 | True |
| 100.00 KiB | 1.00 KiB | 0.0004 | 0.027 | 0.051 | True |
| 1.00 KiB | 64.00 KiB | 1.0000 | 0.001 | 0.001 | False |
| 10.00 KiB | 64.00 KiB | 1.0000 | 0.000 | 0.001 | False |
| 100.00 KiB | 64.00 KiB | 0.0004 | 0.027 | 0.051 | True |

### AEAD

| payload | encrypt MiB/s | decrypt MiB/s | encrypt ms | decrypt ms |
| --- | --- | --- | --- | --- |
| 1.00 KiB | 19.97 | 53.96 | 0.049 | 0.018 |
| 10.00 KiB | 499.72 | 553.07 | 0.020 | 0.018 |
| 100.00 KiB | 1785.34 | 2242.08 | 0.055 | 0.044 |

### replay

| entries | insert ops/s | lookup ops/s | preload s | purge s | rss growth |
| --- | --- | --- | --- | --- | --- |
| 10,000 | 2672.75 | 210703.76 | 1.647 | 0.001 | 0.00 B |

### headers

| scenario | headers | value size | forwarded | ops/s | ms/op |
| --- | --- | --- | --- | --- | --- |
| small | 10 | 32.00 B | 10 | 58930.99 | 0.0170 |
| many | 100 | 32.00 B | 100 | 28219.89 | 0.0354 |
| large-values | 100 | 512.00 B | 100 | 46481.36 | 0.0215 |
| duplicates | 100 | 32.00 B | 100 | 46707.15 | 0.0214 |
| large-cookie | 10 | 8.00 KiB | 10 | 222617.98 | 0.0045 |

### memory

| payload | peak allocations | allocation count | temporary growth |
| --- | --- | --- | --- |
| 1.00 MiB | 3.00 MiB | 9 | 2.00 MiB |

### large-payloads

| request body | median ms | p95 ms | max ms |
| --- | --- | --- | --- |
| 1.00 MiB | 29.299 | 29.299 | 29.299 |

## Limitations

- Results are comparable only across runs with the same benchmark command, host class, CPU limits, Python version, dependency versions, and RelayX settings.
- Timing benchmarks are measurements, not pass/fail tests; use repeated runs to identify meaningful changes.
- In-process ASGI benchmarks remove external network variability and are best for RelayX baseline comparisons, not public internet latency estimates.
- Replay-cache and large-payload results depend strongly on available memory and host load.
