"""Strict msgpack schema codec for RelayX v1 messages."""
from __future__ import annotations
from dataclasses import asdict
from typing import Any
import msgpack
from relayx.constants import NAME_TYPES, TYPE_NAMES, VERSION
from relayx.errors import SerializationError
from relayx.protocol.models import HeaderList, RelayError, RelayRequest, RelayResponse

_REQUEST_KEYS = {"version","type","request_id","method","scheme","host","port","path","query","headers","body"}
_RESPONSE_KEYS = {"version","type","request_id","status_code","reason_phrase","headers","body"}
_ERROR_KEYS = {"version","type","request_id","error_code","message","retryable"}

def dumps(message: RelayRequest | RelayResponse | RelayError) -> bytes:
    data = asdict(message)
    data["headers"] = [list(pair) for pair in data.get("headers", ())]
    try:
        return msgpack.packb(data, use_bin_type=True, strict_types=True)
    except Exception as exc:
        raise SerializationError("failed to serialize message") from exc

def loads(data: bytes, expected_type: int | None = None) -> RelayRequest | RelayResponse | RelayError:
    try:
        raw = msgpack.unpackb(data, raw=False, strict_map_key=True)
    except Exception as exc:
        raise SerializationError("failed to deserialize message") from exc
    if not isinstance(raw, dict): raise SerializationError("message must be a map")
    if raw.get("version") != VERSION: raise SerializationError("unsupported version")
    type_name = raw.get("type")
    if expected_type is not None and TYPE_NAMES.get(expected_type) != type_name:
        raise SerializationError("outer and inner types do not match")
    try:
        if type_name == "request": return _request(raw)
        if type_name == "response": return _response(raw)
        if type_name == "error": return _error(raw)
    except Exception as exc:
        if isinstance(exc, SerializationError):
            raise
        raise SerializationError("message schema validation failed") from exc
    raise SerializationError("invalid message type")

def message_type(message: RelayRequest | RelayResponse | RelayError) -> int:
    return NAME_TYPES[message.type]

def _check_keys(raw: dict[str, Any], keys: set[str]) -> None:
    if set(raw) != keys:
        raise SerializationError("message has missing or unknown fields")

def _require_str(raw: dict[str, Any], key: str) -> str:
    value = raw[key]
    if not isinstance(value, str): raise SerializationError(f"{key} must be a string")
    return value

def _require_optional_str(raw: dict[str, Any], key: str) -> str | None:
    value = raw[key]
    if value is not None and not isinstance(value, str): raise SerializationError(f"{key} must be a string or nil")
    return value

def _require_int(raw: dict[str, Any], key: str) -> int:
    value = raw[key]
    if type(value) is not int: raise SerializationError(f"{key} must be an integer")
    return value

def _require_optional_int(raw: dict[str, Any], key: str) -> int | None:
    value = raw[key]
    if value is not None and type(value) is not int: raise SerializationError(f"{key} must be an integer or nil")
    return value

def _require_bool(raw: dict[str, Any], key: str) -> bool:
    value = raw[key]
    if type(value) is not bool: raise SerializationError(f"{key} must be a boolean")
    return value

def _require_body(raw: dict[str, Any]) -> bytes:
    value = raw["body"]
    if not isinstance(value, bytes): raise SerializationError("body must be binary")
    return value

def _headers(value: Any) -> HeaderList:
    if not isinstance(value, list): raise SerializationError("headers must be an array")
    out = []
    for item in value:
        if not (isinstance(item, list) and len(item) == 2 and isinstance(item[0], str) and isinstance(item[1], str)):
            raise SerializationError("headers must contain string pairs")
        out.append((item[0], item[1]))
    return tuple(out)

def _request(raw: dict[str, Any]) -> RelayRequest:
    _check_keys(raw, _REQUEST_KEYS)
    return RelayRequest(_require_str(raw, "request_id"), _require_str(raw, "method"), _require_str(raw, "scheme"), _require_str(raw, "host"), _require_optional_int(raw, "port"), _require_str(raw, "path"), _require_str(raw, "query"), _headers(raw["headers"]), _require_body(raw))

def _response(raw: dict[str, Any]) -> RelayResponse:
    _check_keys(raw, _RESPONSE_KEYS)
    return RelayResponse(_require_str(raw, "request_id"), _require_int(raw, "status_code"), _require_optional_str(raw, "reason_phrase"), _headers(raw["headers"]), _require_body(raw))

def _error(raw: dict[str, Any]) -> RelayError:
    _check_keys(raw, _ERROR_KEYS)
    request_id = raw["request_id"]
    if request_id is not None and not isinstance(request_id, str): raise SerializationError("request_id must be a string or nil")
    return RelayError(request_id, _require_str(raw, "error_code"), _require_str(raw, "message"), _require_bool(raw, "retryable"))
