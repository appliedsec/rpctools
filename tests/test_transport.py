import pytest

from rpctools.jsonrpc.transport import (
    Transport, SafeTransport, TLSConnectionPoolTransport,
    TLSConnectionPoolSafeTransport)


@pytest.mark.parametrize('cls', [
    Transport,
    SafeTransport,
    TLSConnectionPoolTransport,
    TLSConnectionPoolSafeTransport,
])
def test_constructor(cls):
    cls()
