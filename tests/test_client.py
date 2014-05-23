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


class TestUrllibImplementation(object):
    """urllib in Python 2.7 has non-public functions of the form split*,
    which don't appear in Python 3. These are tests of the implementation
    details so we can refactor to a Python 3-compatible implementation.
    """

    @pytest.mark.parametrize('uri,type', [
        ('http://foo.com/', 'http'),
        ('https://foo.com/', 'https'),
    ])
    def test_type(self, uri, type):
        proxy = ServerProxy(uri)
        assert proxy.type == type

    @pytest.mark.parametrize('uri,handler', [
        ('http://myusername:mypassword@myhostname.com/foo/bar/baz.html',
         '/foo/bar/baz.html'),
        ('http://foo.com/monkey/butler.html?one=foo&two=bar',
         '/monkey/butler.html?one=foo&two=bar'),
    ])
    def test_handler(self, uri, handler):
        proxy = ServerProxy(uri)
        assert proxy.handler == handler

    @pytest.mark.parametrize('uri,host', [
        ('http://myusername:mypassword@myhostname.com/foo/bar/baz.html',
         'myhostname.com'),
    ])
    def test_host(self, uri, host):
        proxy = ServerProxy(uri)
        assert proxy.host == host

    def test_no_auth(self):
        uri = 'http://foo.com/'
        proxy = ServerProxy(uri)
        assert 'Authorization' not in proxy.extra_headers

    def test_auth(self):
        uri = 'http://myusername:mypassword@myhostname.com/foo/bar/baz.html'
        proxy = ServerProxy(uri)
        assert proxy.extra_headers['Authorization'] == \
            'Basic bXl1c2VybmFtZTpteXBhc3N3b3Jk'  # Urlencoded.
