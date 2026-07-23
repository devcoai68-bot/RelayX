"""Local fully buffered HTTP proxy."""
from __future__ import annotations
import asyncio, uuid
from relayx.config import RelaySettings
from relayx.http.headers import filter_forward_headers
from relayx.http.parser import read_request
from relayx.http.writer import write_response
from relayx.protocol.models import RelayError, RelayRequest
from relayx.client.relay_client import RelayClient

class LocalProxy:
    def __init__(self, settings: RelaySettings, relay_client: RelayClient) -> None:
        self.settings = settings
        self.relay_client = relay_client

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            http_request = await read_request(reader, self.settings.max_header_bytes, self.settings.max_request_body_bytes)
            request = RelayRequest(uuid.uuid4().hex, http_request.method, http_request.scheme, http_request.host, http_request.port, http_request.path, http_request.query, filter_forward_headers(http_request.headers), http_request.body)
            response = await self.relay_client.send(request)
        except Exception:
            response = RelayError(None, "bad_request", "Request could not be processed", False)
        await write_response(writer, response)
        writer.close()
        await writer.wait_closed()

    async def serve(self) -> asyncio.AbstractServer:
        return await asyncio.start_server(self.handle, self.settings.proxy_host, self.settings.proxy_port)
