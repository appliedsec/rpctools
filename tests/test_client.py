import pytest

from rpctools.jsonrpc.client import (
    CookieKeeperMixin, RawServerProxy, ServerProxy)
from rpctools.jsonrpc.exc import JsonRpcError


class TestCookieKeeperMixin(object):

    def test_constructor(self):
        CookieKeeperMixin()


class TestRawServerProxy(object):

    def test_constructor(self):
        RawServerProxy('http://google.com/')


class TestServerProxy(object):

    @pytest.mark.parametrize('uri', [
        'http://foo.com/',
        'https://foo.com/'
    ])
    def test_constructor(self, uri):
        ServerProxy(uri)

    @pytest.mark.parametrize('uri', [
        'gopher://foo.com/',
        'ftp://foo.com/',
    ])
    def test_constructor_unsupported_transport(self, uri):
        with pytest.raises(JsonRpcError):
            ServerProxy(uri)
