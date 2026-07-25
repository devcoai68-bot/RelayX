"""HTTP/1.1 carrier client for RelayX packets."""
from __future__ import annotations
import httpx
from relayx.config import RelaySettings
from relayx.constants import RELAY_CONTENT_TYPE
from relayx.pipeline import decode_message, encode_message
from relayx.protocol.models import RelayError, RelayRequest, RelayResponse
from relayx.protocol.replay import ReplayCache

class RelayClient:
    def __init__(self, settings: RelaySettings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.key = settings.encryption_key_bytes
        self.client = client or httpx.AsyncClient(http1=True, http2=False, timeout=settings.timeout_seconds)
        self.replay_cache = ReplayCache(settings.replay_window_seconds, settings.replay_cache_max_entries, settings.allowed_clock_skew_seconds)

    async def send(self, message: RelayRequest) -> RelayResponse | RelayError:
        packet = encode_message(message, self.key, compression_enabled=self.settings.compression_enabled, compression_threshold=self.settings.compression_threshold_bytes)
        response = await self.client.post(self.settings.relay_url, content=packet, headers={"content-type": RELAY_CONTENT_TYPE, "authorization": f"Bearer {self.settings.auth_token}"})
        response.raise_for_status()
        reply = decode_message(response.content, self.key, replay_cache=self.replay_cache, max_ciphertext_bytes=self.settings.max_carrier_body_bytes, max_decompressed_bytes=self.settings.max_decompressed_bytes, max_request_body_bytes=self.settings.max_request_body_bytes, max_response_body_bytes=self.settings.max_response_body_bytes)
        if not isinstance(reply, RelayResponse | RelayError):
            raise ValueError("unexpected relay response")
        if reply.request_id is not None and reply.request_id != message.request_id:
            raise ValueError("relay response request_id mismatch")
        return reply

    async def aclose(self) -> None:
        await self.client.aclose()
