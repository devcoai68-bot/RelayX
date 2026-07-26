"""RelayX protocol constants."""

MAGIC = b"RLX1"
VERSION = 1
TYPE_REQUEST = 1
TYPE_RESPONSE = 2
TYPE_ERROR = 3
TYPE_NAMES = {TYPE_REQUEST: "request", TYPE_RESPONSE: "response", TYPE_ERROR: "error"}
NAME_TYPES = {value: key for key, value in TYPE_NAMES.items()}
FLAG_COMPRESSED = 0x01
ALLOWED_FLAGS = FLAG_COMPRESSED
RESERVED = 0
NONCE_ID_SIZE = 16
AEAD_NONCE_SIZE = 12
AAD_SIZE = 44
HEADER_SIZE = 48
DEFAULT_RELAY_PATH = "/relay"
RELAY_CONTENT_TYPE = "application/octet-stream"
DEFAULT_REPLAY_WINDOW_SECONDS = 300
DEFAULT_ALLOWED_CLOCK_SKEW_SECONDS = 30
DEFAULT_REPLAY_CACHE_MAX_ENTRIES = 100_000
DEFAULT_COMPRESSION_THRESHOLD_BYTES = 1024
DEFAULT_MAX_HEADER_BYTES = 64 * 1024
DEFAULT_MAX_REQUEST_BODY_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_RESPONSE_BODY_BYTES = 64 * 1024 * 1024
DEFAULT_MAX_DECOMPRESSED_BYTES = 128 * 1024 * 1024
DEFAULT_MAX_CARRIER_BODY_BYTES = 128 * 1024 * 1024
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "content-length",
}
PROXY_ONLY_HEADERS = {"proxy-connection", "proxy-authorization", "proxy-authenticate"}
