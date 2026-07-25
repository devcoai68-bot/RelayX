"""In-memory replay protection for authenticated packets."""
from __future__ import annotations
import time
from relayx.constants import DEFAULT_ALLOWED_CLOCK_SKEW_SECONDS, DEFAULT_REPLAY_CACHE_MAX_ENTRIES, DEFAULT_REPLAY_WINDOW_SECONDS, NONCE_ID_SIZE
from relayx.errors import PacketExpiredError, PacketFromFutureError, ProtocolError, ReplayCacheFullError, ReplayDetectedError

class ReplayCache:
    def __init__(self, window_seconds: int = DEFAULT_REPLAY_WINDOW_SECONDS, max_entries: int = DEFAULT_REPLAY_CACHE_MAX_ENTRIES, allowed_clock_skew_seconds: int = DEFAULT_ALLOWED_CLOCK_SKEW_SECONDS) -> None:
        self.window_ms = window_seconds * 1000
        self.skew_ms = allowed_clock_skew_seconds * 1000
        self.max_entries = max_entries
        self._seen: dict[bytes, int] = {}

    def check_and_store(self, nonce_id: bytes, timestamp_ms: int, now_ms: int | None = None) -> None:
        if not isinstance(nonce_id, bytes) or len(nonce_id) != NONCE_ID_SIZE:
            raise ProtocolError("invalid replay nonce")
        if now_ms is None:
            now_ms = int(time.time() * 1000)
        self._purge(now_ms)
        if timestamp_ms < now_ms - self.window_ms:
            raise PacketExpiredError("packet timestamp is outside replay window")
        if timestamp_ms > now_ms + self.skew_ms:
            raise PacketFromFutureError("packet timestamp is too far in the future")
        if nonce_id in self._seen:
            raise ReplayDetectedError("packet nonce was already used")
        if len(self._seen) >= self.max_entries:
            raise ReplayCacheFullError("replay cache is full")
        self._seen[nonce_id] = timestamp_ms

    def _purge(self, now_ms: int) -> None:
        cutoff = now_ms - self.window_ms
        expired = [nonce for nonce, ts in self._seen.items() if ts < cutoff]
        for nonce in expired:
            del self._seen[nonce]
