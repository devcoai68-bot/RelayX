# RelayX

RelayX is a message-oriented encrypted HTTP request relay for restrictive HTTP/1.1-only environments. Version 1 is fully buffered and is not a TCP tunnel, SOCKS proxy, or CONNECT proxy.

## Protocol v1

Packets use a 48-byte outer header. The first 44 bytes are AEAD associated data: magic, version, type, flags, reserved byte, millisecond timestamp, 16-byte replay nonce id, and 12-byte AEAD nonce. The final 4 fixed-header bytes encode ciphertext length. The payload is ChaCha20-Poly1305 ciphertext containing msgpack bytes, optionally compressed with zstd when the configured threshold is met.

Replay cache insertion happens only after AEAD authentication succeeds and timestamp validation passes. Default memory limits are intentionally conservative: 16 MiB request bodies, 64 MiB response bodies, and 128 MiB carrier/decompressed packet bounds.
