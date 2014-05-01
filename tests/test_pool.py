from rpctools.jsonrpc.pool import Pool, TLSConnectionPoolMixin


def test_pool():
    pool = Pool()
    assert pool.connections == {}


class TestTLSConnectionPoolMixin(object):

    def test_constructor(self):
        TLSConnectionPoolMixin()
