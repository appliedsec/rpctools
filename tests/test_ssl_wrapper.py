from rpctools.jsonrpc.ssl_wrapper import (
    CertValidatingHTTPSConnection, CertValidatingHTTPSHandler)


def test_connection_constructor():
    CertValidatingHTTPSConnection('foo.com')


def test_handler_constructor():
    CertValidatingHTTPSHandler()
