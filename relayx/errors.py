"""RelayX exception types."""

class RelayXError(Exception):
    """Base RelayX error."""

class ConfigError(RelayXError): pass
class ProtocolError(RelayXError): pass
class SerializationError(RelayXError): pass
class CompressionError(RelayXError): pass
class CryptoError(RelayXError): pass
class AuthenticationError(RelayXError): pass
class ReplayError(RelayXError): pass
class ReplayDetectedError(ReplayError): pass
class PacketExpiredError(ReplayError): pass
class PacketFromFutureError(ReplayError): pass
class ReplayCacheFullError(ReplayError): pass
class TransportError(RelayXError): pass
class UpstreamHTTPError(RelayXError): pass
class RequestTooLargeError(RelayXError): pass
class ResponseTooLargeError(RelayXError): pass
