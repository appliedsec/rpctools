from __future__ import absolute_import

import sys
import socket
import logging

from rpctools.six import reraise
from rpctools.six.moves import http_client as httplib
from rpctools.jsonrpc import ssl_wrapper
from rpctools.jsonrpc.exc import ConnectionError, ProtocolError
from rpctools.jsonrpc.pool import TLSConnectionPoolMixin

__license__ = """Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License."""

class Transport(object):
    """
    Handles an HTTP transaction to a JSON-RPC server.

    :ivar user_agent: The user agent to report when connecting to server.
    :type user_agent: C{str}

    :ivar timeout: The socket timeout (in seconds) to use on httplib connections.
                        (defaults to socket._GLOBAL_DEFAULT_TIMEOUT)
    :type timeout: C{int}
    """

    user_agent = "JSON-RPC Client"
    timeout = socket._GLOBAL_DEFAULT_TIMEOUT

    def __init__(self, timeout=None):
        self.logger = logging.getLogger('{0.__name__}.{0.__module__}'.format(self.__class__))
        if timeout is not None:
            self.timeout = timeout

    def request(self, host, handler, body, headers=None, verbose=False):
        """
        Send a complete request, and parse the response.

        :param host: Target host (may include port, e.g. 'example.com:8080')
        :type host: C{str}

        :param handler: Target PRC handler (e.g. '/jsonrpc').
        :type handler: C{str}

        :param body: Request body. (Assumes it is already correctly formatted/encoded.)
        :type body: C{str}

        :param headers: HTTP headers to send with request.
        :type headers: C{dict}

        :param verbose: Debugging flag.
        :type verbose: C{bool}

        :return: The response to the request.
        :rtype: C{httplib.HTTPResponse}

        :raise ProtocolError: If the response status is not 200.
        """
        if headers is None:
            headers = {}

        conn = self.connect(host)

        if verbose:
            conn.set_debuglevel(1)

        header_keys_lower = set(k.lower() for k in headers.keys())

        # Add headers
        headers['User-Agent'] = self.user_agent
        if not 'content-type' in header_keys_lower:
            headers['Content-Type'] = 'application/json'
        headers['Content-Length'] = len(body) if body is not None else 0

        try:
            conn.request("POST", handler, body, headers)
            response = conn.getresponse()

            if response.status != 200:
                raise ProtocolError(host + handler, response.status, response.reason, headers)

            return response
        except (socket.error, httplib.HTTPException) as x:
            self.handle_connection_error(host, x)
            exc_class, exc, tb = sys.exc_info()
            cerror = ConnectionError("Error connecting to host %s: %r" % (host, x))
            reraise(ConnectionError, cerror, tb)

    def handle_connection_error(self, host, x):
        """
        Stub method to handle connection errors for specified host.

        (This exists to support removing things from pool, etc.)

        :param host: The host associated with the error.
        :type host: str
        """

    def connect(self, host):
        """
        Connect to specified server.

        This method returns a new connection.  (It should be overridden if you would like
        to change that behavior -- e.g. to re-use existing connections.)

        :param host: The host (optionally in "host:port" syntax).
        :type host: C{str}

        :return: A connection handle.
        :rtype: C{httplib.HTTPConnection}
        """
        return httplib.HTTPConnection(host, timeout=self.timeout)


class SafeTransport(Transport):
    """
    Extends/overrides Transport to use HTTPS connections.
    """

    def __init__(self, key_file=None, cert_file=None, ca_certs=None, validate_cert_hostname=True, timeout=None):
        super(SafeTransport, self).__init__(timeout=timeout)
        self.key_file = key_file
        self.cert_file = cert_file
        self.ca_certs = ca_certs
        self.validate_cert_hostname = validate_cert_hostname

    def connect(self, host):
        """
        Connect securely (HTTPS) to host.
        """
        return ssl_wrapper.CertValidatingHTTPSConnection(host, key_file=self.key_file, cert_file=self.cert_file,
                   ca_certs=self.ca_certs, validate_cert_hostname=self.validate_cert_hostname)


class TLSConnectionPoolTransport(TLSConnectionPoolMixin, Transport):
    pass


class TLSConnectionPoolSafeTransport(TLSConnectionPoolMixin, SafeTransport):
    pass
