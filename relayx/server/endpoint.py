"""FastAPI RelayX endpoint."""
from __future__ import annotations
import hmac
import logging
from fastapi import APIRouter, Header, HTTPException, Request, Response
from relayx.config import RelaySettings
from relayx.constants import DEFAULT_RELAY_PATH, RELAY_CONTENT_TYPE
from relayx.errors import PacketExpiredError, PacketFromFutureError, ReplayCacheFullError, ReplayDetectedError, RequestTooLargeError, ResponseTooLargeError
from relayx.pipeline import decode_message, encode_message
from relayx.protocol.models import RelayError, RelayRequest
from relayx.protocol.replay import ReplayCache
from relayx.server.forwarder import Forwarder

logger = logging.getLogger("relayx.server")

async def authenticate(auth_header: str | None, token: str) -> None:
    if not auth_header:
        raise HTTPException(status_code=401, detail="Unauthorized")
    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0] != "Bearer" or not parts[1]:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not hmac.compare_digest(parts[1], token):
        raise HTTPException(status_code=401, detail="Unauthorized")

async def read_limited_body(request: Request, max_bytes: int) -> bytes:
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > max_bytes:
            raise HTTPException(status_code=413, detail="Payload Too Large")
    return bytes(body)

def _error_from_exception(exc: Exception, request_id: str | None = None) -> RelayError:
    if isinstance(exc, ReplayDetectedError):
        return RelayError(request_id, "replay_detected", "Replay detected", False)
    if isinstance(exc, PacketExpiredError):
        return RelayError(request_id, "packet_expired", "Packet expired", False)
    if isinstance(exc, PacketFromFutureError):
        return RelayError(request_id, "packet_from_future", "Packet timestamp is too far in the future", False)
    if isinstance(exc, ReplayCacheFullError):
        return RelayError(request_id, "replay_cache_full", "Replay cache is full", True)
    if isinstance(exc, RequestTooLargeError):
        return RelayError(request_id, "request_too_large", "Request body is too large", False)
    if isinstance(exc, ResponseTooLargeError):
        return RelayError(request_id, "response_too_large", "Response body is too large", False)
    return RelayError(request_id, "invalid_packet", "Relay packet could not be processed", False)

def health_router(replay_cache: ReplayCache, forwarder: Forwarder) -> APIRouter:
    api = APIRouter()

    @api.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.get("/ready")
    async def ready() -> dict[str, object]:
        ready_state = replay_cache is not None and forwarder.is_available
        if not ready_state:
            raise HTTPException(status_code=503, detail="RelayX is not ready")
        return {"status": "ready", "replay_cache": "initialized", "forwarder": "available"}

    return api


def router(settings: RelaySettings, replay_cache: ReplayCache, forwarder: Forwarder) -> APIRouter:
    api = APIRouter()
    key = settings.encryption_key_bytes

    @api.post(DEFAULT_RELAY_PATH)
    async def relay(request: Request, authorization: str | None = Header(default=None)) -> Response:
        await authenticate(authorization, settings.auth_token)
        if request.headers.get("content-type", "").split(";")[0].lower() != RELAY_CONTENT_TYPE:
            raise HTTPException(status_code=415, detail="Unsupported Media Type")
        logger.info("relay_request_received", extra={"relayx": {"path": request.url.path}})
        body = await read_limited_body(request, settings.max_carrier_body_bytes)
        message: RelayRequest | None = None
        try:
            decoded = decode_message(body, key, replay_cache=replay_cache, max_ciphertext_bytes=settings.max_carrier_body_bytes, max_decompressed_bytes=settings.max_decompressed_bytes, max_request_body_bytes=settings.max_request_body_bytes, max_response_body_bytes=settings.max_response_body_bytes)
            if not isinstance(decoded, RelayRequest):
                raise ValueError("expected request")
            message = decoded
            reply = await forwarder.forward(message)
            logger.info("relay_request_forwarded", extra={"relayx": {"request_id": message.request_id}})
        except Exception as exc:
            request_id = message.request_id if message is not None else None
            logger.warning("relay_request_failed", extra={"relayx": {"request_id": request_id, "error_type": type(exc).__name__}})
            reply = _error_from_exception(exc, request_id)
        packet = encode_message(reply, key, compression_enabled=settings.compression_enabled, compression_threshold=settings.compression_threshold_bytes)
        return Response(packet, media_type=RELAY_CONTENT_TYPE)
    return api
