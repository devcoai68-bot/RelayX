from relayx.http.headers import filter_forward_headers


def test_filters_hop_by_hop_proxy_only_and_connection_tokens():
    headers = (
        ("Host", "example.com"),
        ("Connection", "X-Test, keep-alive"),
        ("X-Test", "no"),
        ("Proxy-Connection", "keep-alive"),
        ("Content-Type", "text/plain"),
        ("Content-Length", "2"),
    )
    assert filter_forward_headers(headers) == (
        ("Host", "example.com"),
        ("Content-Type", "text/plain"),
    )
