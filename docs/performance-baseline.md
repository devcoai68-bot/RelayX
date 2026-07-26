# RelayX Performance Baseline

Generated: `2026-07-26T11:41:51+00:00`

## Environment

- OS: `Linux-6.12.13-x86_64-with-glibc2.39`
- Machine: `x86_64`
- CPU: `x86_64`
- CPU count: `3`
- RAM: `17.93 GiB`
- Python: `3.14.4`
- RelayX commit: `4d3a84b2095df993243968e6b5d32566cb261397`

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
| 1.00 KiB | 90.259 | 90.259 | 90.259 | 90.259 | 90.259 | 90.259 |
| 10.00 KiB | 2.879 | 2.879 | 2.879 | 2.879 | 2.879 | 2.879 |
| 100.00 KiB | 6.410 | 6.410 | 6.410 | 6.410 | 6.410 | 6.410 |

### throughput

| concurrency | requests | payload | requests/s | MiB/s |
| --- | --- | --- | --- | --- |
| 1 | 1 | 64.00 KiB | 200.92 | 12.56 |
| 10 | 10 | 64.00 KiB | 406.35 | 25.40 |
| 50 | 50 | 64.00 KiB | 281.96 | 17.62 |
| 100 | 100 | 64.00 KiB | 287.21 | 17.95 |
| 200 | 200 | 64.00 KiB | 324.71 | 20.29 |
| 500 | 500 | 64.00 KiB | 308.24 | 19.26 |

### compression

| payload | threshold | ratio | compress ms | decompress ms | compressed |
| --- | --- | --- | --- | --- | --- |
| 1.00 KiB | 0.00 B | 0.0332 | 0.034 | 0.020 | True |
| 10.00 KiB | 0.00 B | 0.0034 | 0.059 | 0.019 | True |
| 100.00 KiB | 0.00 B | 0.0004 | 0.084 | 0.065 | True |
| 1.00 KiB | 1.00 KiB | 0.0332 | 0.016 | 0.013 | True |
| 10.00 KiB | 1.00 KiB | 0.0034 | 0.021 | 0.018 | True |
| 100.00 KiB | 1.00 KiB | 0.0004 | 0.038 | 0.063 | True |
| 1.00 KiB | 64.00 KiB | 1.0000 | 0.001 | 0.001 | False |
| 10.00 KiB | 64.00 KiB | 1.0000 | 0.001 | 0.001 | False |
| 100.00 KiB | 64.00 KiB | 0.0004 | 0.038 | 0.063 | True |

### AEAD

| payload | encrypt MiB/s | decrypt MiB/s | encrypt ms | decrypt ms |
| --- | --- | --- | --- | --- |
| 1.00 KiB | 23.38 | 50.59 | 0.042 | 0.019 |
| 10.00 KiB | 587.23 | 634.09 | 0.017 | 0.015 |
| 100.00 KiB | 1723.46 | 1706.95 | 0.057 | 0.057 |

### replay

| entries | insert ops/s | lookup ops/s | preload s | purge s | rss growth |
| --- | --- | --- | --- | --- | --- |
| 10,000 | 2141.88 | 223513.63 | 2.273 | 0.001 | 0.00 B |

### headers

| scenario | headers | value size | forwarded | ops/s | ms/op |
| --- | --- | --- | --- | --- | --- |
| small | 10 | 32.00 B | 10 | 62617.41 | 0.0160 |
| many | 100 | 32.00 B | 100 | 23835.06 | 0.0420 |
| large-values | 100 | 512.00 B | 100 | 31388.30 | 0.0319 |
| duplicates | 100 | 32.00 B | 100 | 33497.47 | 0.0299 |
| large-cookie | 10 | 8.00 KiB | 10 | 30749.36 | 0.0325 |

### memory

| payload | peak allocations | allocation count | temporary growth |
| --- | --- | --- | --- |
| 1.00 MiB | 3.00 MiB | 9 | 2.00 MiB |

### large-payloads

| request body | median ms | p95 ms | max ms |
| --- | --- | --- | --- |
| 1.00 MiB | 7.703 | 7.703 | 7.703 |

## Limitations

- Results are comparable only across runs with the same benchmark command, host class, CPU limits, Python version, dependency versions, and RelayX settings.
- Timing benchmarks are measurements, not pass/fail tests; use repeated runs to identify meaningful changes.
- In-process ASGI benchmarks remove external network variability and are best for RelayX baseline comparisons, not public internet latency estimates.
- Replay-cache and large-payload results depend strongly on available memory and host load.
