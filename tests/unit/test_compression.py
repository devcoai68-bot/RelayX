from relayx.compression import maybe_compress, maybe_decompress

def test_threshold_compression():
    data = b"a" * 100
    raw, flag = maybe_compress(data, True, 101)
    assert raw == data and flag is False
    comp, flag = maybe_compress(data, True, 100)
    assert flag is True
    assert maybe_decompress(comp, True, 1000) == data
