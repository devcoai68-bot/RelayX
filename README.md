# RelayX

RelayX is a message-oriented encrypted HTTP request relay for restrictive HTTP/1.1-only environments. Version 1 is fully buffered and is not a TCP tunnel, SOCKS proxy, or CONNECT proxy.

## Protocol v1

Packets use a 48-byte outer header. The first 44 bytes are AEAD associated data: magic, version, type, flags, reserved byte, millisecond timestamp, 16-byte replay nonce id, and 12-byte AEAD nonce. The final 4 fixed-header bytes encode ciphertext length. The payload is ChaCha20-Poly1305 ciphertext containing msgpack bytes, optionally compressed with zstd when the configured threshold is met.

Replay cache insertion happens only after AEAD authentication succeeds and timestamp validation passes. Default memory limits are intentionally conservative: 16 MiB request bodies, 64 MiB response bodies, and 128 MiB carrier/decompressed packet bounds.

## Production deployment

RelayX server mode exposes `POST /relay` plus unauthenticated `GET /health` and `GET /ready` operational endpoints. `/health` confirms the application process is running. `/ready` confirms the replay cache is initialized and the upstream forwarder is available.

### Configuration

All settings are environment variables with the `RELAYX_` prefix. See `.env.example` for a complete documented template, including authentication, encryption, replay-cache sizing, request/response limits, compression, timeouts, bind addresses, and structured log level.

Secrets are split intentionally: `RELAYX_AUTH_TOKEN` is only the bearer token used by the HTTP carrier, while `RELAYX_ENCRYPTION_KEY` is the independent base64-encoded 32-byte ChaCha20-Poly1305 key. They must not be the same value.

### Docker and single-node compose

Build and run the server image with Python 3.12 slim:

```sh
docker build -t relayx .
docker run --env-file .env -p 8000:8000 relayx
```

For a single-node deployment, copy `.env.example` to `.env`, set production secrets, then run:

```sh
docker compose up --build
```

The container runs as a non-root user and starts `relayx server`.

### Reverse proxy assumptions

RelayX v1 expects HTTP/1.1 POST carrier requests with `Content-Type: application/octet-stream`. A reverse proxy must preserve the `Authorization` header and content type, must allow carrier bodies up to `RELAYX_MAX_CARRIER_BODY_BYTES`, and should disable response buffering for predictable latency. An example nginx configuration is provided in `examples/nginx-relayx.conf` with `client_max_body_size`, `proxy_read_timeout`, `proxy_send_timeout`, `proxy_buffering off`, HTTP/1.1 proxying, forwarded headers, Authorization forwarding, and Content-Type preservation.

### Resource sizing and timeouts

Default limits are conservative and fully buffered: 16 MiB request bodies, 64 MiB response bodies, and 128 MiB carrier/decompressed packet bounds. Size memory for concurrent requests as roughly the sum of accepted carrier payloads plus upstream response buffers. `RELAYX_TIMEOUT_SECONDS` controls upstream HTTP timeouts and the graceful shutdown drain window.

### Graceful shutdown

During FastAPI lifespan shutdown, RelayX stops after allowing outstanding relay requests up to the configured timeout window, then closes the managed `httpx.AsyncClient` cleanly.

### Security considerations and limitations

RelayX is not a VPN, SOCKS proxy, CONNECT tunnel, TCP tunnel, WebSocket transport, or streaming relay. It relays complete HTTP requests and responses only. Structured logs intentionally exclude bearer tokens, encryption keys, Authorization headers, and request/response bodies. The replay cache is in memory and single-process only; do not run multiple independent server processes behind one endpoint unless you accept that replay detection is scoped to each process or provide sticky routing at a higher layer.

## Performance validation

Phase 5 benchmark code lives under `benchmarks/` and is intentionally separate from production RelayX modules. The scripts import RelayX to measure current behavior but do not change protocol encoding, encryption, compression, replay protection, forwarding, parsing, or server/client behavior.

### Running benchmarks

Run benchmark scripts from the repository root with Python's module runner:

```sh
python -m benchmarks.benchmark_latency --iterations 20 --warmup 3
python -m benchmarks.benchmark_throughput --iterations 500 --warmup 3
python -m benchmarks.benchmark_compression --iterations 20 --warmup 3
python -m benchmarks.benchmark_crypto --iterations 20 --warmup 3
python -m benchmarks.benchmark_replay --iterations 10000 --warmup 3
python -m benchmarks.benchmark_headers --iterations 50000 --warmup 3
python -m benchmarks.benchmark_memory --iterations 3 --warmup 1
python -m benchmarks.benchmark_large_payloads --iterations 5 --warmup 1
```

The latency, crypto, compression, and large-payload benchmarks cover the standard RelayX payload sizes: 1 KiB, 10 KiB, 100 KiB, 1 MiB, 4 MiB, 8 MiB, and 16 MiB where applicable. Throughput reports requests/second and MiB/second for concurrency levels 1, 10, 50, 100, 200, and 500. Replay-cache measurements cover 10,000, 100,000, 500,000, and 1,000,000 entries, so run that benchmark on a host sized for the target cache.

Each script prints a human-readable table with the key baseline dimensions for that area, such as payload size, latency percentiles, throughput, memory, compression ratio, and crypto speed. Benchmark timings are measurements, not pass/fail assertions; compare results on the same host class, Python version, dependency versions, and environment settings.


### Capturing the official baseline

Use the baseline runner to execute every benchmark and export both machine-readable JSON and Markdown reports:

```sh
python -m benchmarks.run_baseline --iterations 5 --warmup 1
```

By default, the runner uses quick mode so routine baseline captures complete on small CI workers. Add `--full` to use the full Phase 5 payload and replay-cache sizes. JSON results are written to `benchmarks/results/baseline-YYYY-MM-DD.json`, and the Markdown report is written to `docs/performance-baseline.md`.

### Profiling

Every benchmark accepts `--profile` and `--profile-output` to produce a cProfile text report sorted by cumulative time:

```sh
python -m benchmarks.benchmark_latency --iterations 20 --warmup 3 --profile --profile-output latency.prof.txt
```

Optional external profilers such as `py-spy` can also be used around the same commands, but they are not required project dependencies.

### Comparing future optimizations

To establish a baseline, save the full command, Git commit, Python version, dependency versions, host shape, and benchmark output. Future optimization work should run the same benchmark command set before and after changes and compare table outputs for regressions or improvements. Avoid mixing results from different machines, container CPU limits, or debug logging levels.
