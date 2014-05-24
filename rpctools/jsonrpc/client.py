"""
Client libraries for connecting over JSON-RPC, protocol version 1.0.

These are based on the libraries in xmlrpclib and on code from: U{http://code.activestate.com/recipes/552751/};
however, they also add support for using keep-alive connections.
"""
from __future__ import absolute_import

import logging
import urllib
import json
import base64
import string

from rpctools.six.moves.http_cookies import SimpleCookie
from rpctools.six.moves.urllib.parse import urlparse, unquote
from rpctools.jsonrpc.transport import Transport, SafeTransport, TLSConnectionPoolSafeTransport, TLSConnectionPoolTransport
from rpctools.jsonrpc.exc import JsonRpcError, ResponseError, Fault

__license__ = """Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License."""

# -----------------------------------------------------------------------------
# "INTERNAL" CLASSES
# -----------------------------------------------------------------------------

class _Method(object):
    """
    Some magic to bind an JSON-RPC method to an RPC server.

    Supports "nested" methods (e.g. examples.getStateName).
    """
    def __init__(self, send, name):
        """
        Initialize this proxy callable with send function and method name.

        :param send: A callable that will perform the actual request.
        :type send: C{callable}

        :param name: The method name.
        :type name: C{str}
        """
        self._send = send
        self._name = name

    def __getattr__(self, name):
        """
        Dereferences this callable to support "nested" methods.

        This supports having a "module" on server that contains
        methods of its own.  (E.g. "examples.getStateName")

        :rtype: L{_Method}
        """
        return _Method(self._send, "%s.%s" % (self._name, name))

    def __call__(self, *args, **kwargs):
        """
        Performs the actual request, using the configured request sender.
        """
        if args and kwargs:
            raise JsonRpcError('JSON-RPC 2.0 spec does not allow both positional and keyword arguments.')
        return self._send(self._name, args if args else kwargs)

    def __repr__(self):
        return '<%s name=%s>' % (self.__class__.__name__, self._name)

# -----------------------------------------------------------------------------
# PUBLIC CLASSES
# -----------------------------------------------------------------------------

class ServerProxy(object):
    """
    The ServerProxy provides a proxy to the remote JSON-RPC service methods and performs the
    request encoding and decoding.

    This class uses instance variables to save state and is NOT THREAD-SAFE.

    :ivar type: The scheme we're using for connection: 'http' or 'https'
    :type type: C{str}

    :ivar host: The host we're connecting to (may include port, e.g. "foobar.com:8080")
    :type host: C{str}

    :ivar transport: A L{Transport} instance to use.
    :type transport: L{Transport}

    :ivar id: The JSON-RPC 'id' field (incrementing integer).
    :type id: C{int}

    :ivar extra_headers: Any HTTP request headers that should be sent with every request.
    :type extra_headers: C{dict}

    :ivar method_class: The proxy class for the remote methods (default is L{_Method}).
    :type method_class: C{type}
    """

    method_class = _Method

    def __init__(self, uri, key_file=None, cert_file=None, ca_certs=None, validate_cert_hostname=True,
                 extra_headers=None, timeout=None, pool_connections=False):
        """
        :param uri: The endpoint JSON-RPC server URL.
        :param key_file: Secret key to use for ssl connection.
        :param cert_file: Cert to send to server for ssl connection.
        :param ca_certs: File containing concatenated list of certs to validate server cert against.
        :param extra_headers: Any additional headers to include with all requests.
        :param pool_connections: Whether to use a thread-local connection pool for connections.
        """
        self.logger = logging.getLogger('{0.__module__}.{0.__name__}'.format(self.__class__))
        if extra_headers is None:
            extra_headers = {}

        parsed_uri = urlparse(uri)

        self.type = parsed_uri.scheme
        if self.type not in ("http", "https"):
            raise JsonRpcError("unsupported JSON-RPC uri: %s" % uri)

        self.handler = parsed_uri.path
        self.host = parsed_uri.hostname

        if parsed_uri.username and parsed_uri.password:
            auth = '{}:{}'.format(parsed_uri.username, parsed_uri.password)
            auth = base64.encodestring(unquote(auth).encode('ascii'))
            auth = auth.strip()
            extra_headers.update({"Authorization": b"Basic " + auth})

        self.key_file = key_file
        self.cert_file = cert_file
        self.ca_certs = ca_certs
        self.validate_cert_hostname = validate_cert_hostname

        # TODO: This could probably be a little cleaner :)
        if pool_connections:
            if self.type == "https":
                self.transport = TLSConnectionPoolSafeTransport(timeout=timeout)
            else:
                self.transport = TLSConnectionPoolTransport(timeout=timeout)
        else:
            if self.type == "https":
                self.transport = SafeTransport(key_file=self.key_file, cert_file=self.cert_file,
                    ca_certs=self.ca_certs, validate_cert_hostname=self.validate_cert_hostname)
            else:
                self.transport = Transport(timeout=timeout)

        self.extra_headers = extra_headers
        self.id = 0 # Initialize our request ID (gets incremented for every request)

    def _request(self, methodname, params):
        """
        Overriden __request method which introduced the request_cookie parameter
        that allows cookie headers to propagated through JSON-RPC requests.

        :param methodname: Name of method to be called.
        :type methodname: C{str}

        :param params: Parameters list to send to method.
        :type params: C{list}

        :return: The decoded result.

        :raise ResponseError: If the response cannot be parsed or is not proper JSON-RPC 1.0 response format.
        :raise ProtocolError: Re-raises exception if non-200 response received.
        :raise Fault: If the response is an error message from remote application.
        """
        self.id += 1 # Increment our "unique" identifier for every request.

        data = dict(id=self.id, method=methodname, params=params)

        headers = self.extra_headers

        self._prepare_request(data, headers)

        body = json.dumps(data)

        response = self.transport.request(self.host, self.handler, body, headers=headers)

        self._handle_response(response)

        data = response.read()

        try:
            decoded = json.loads(data)
        except Exception as x:
            raise ResponseError("Unable to parse response data as JSON: %s" % x)

        # This special casing for non-compliant systems like DD that sometimes
        # just return NULL from actions and think they're communicating w/ valid
        # JSON-RPC.
        if decoded is None:
            return None

        if not (('result' in decoded) or ('error' in decoded)):
            # Include the decoded result (or part of it) in the error we raise
            r = repr(decoded)
            if len(r) > 256: # a hard-coded value to keep the exception message to a sane length
                r = r[0:255] + '...'
            raise ResponseError('Malformed JSON-RPC response to %s: %s' % (methodname, r))

        if 'error' in decoded and decoded['error']:
            raise Fault(decoded['error']['code'], decoded['error']['message'])

        if not 'result' in decoded:
            raise ResponseError('Malformed JSON-RPC response: %r' % decoded)

        return decoded['result']

    def _prepare_request(self, data, headers):
        """
        An extension point hook for preparing the request data before it is encoded
        and sent to server.

        This method may modify the body (C{dict}) and headers (C{dict}).  Note
        that some headers (e.g. Content-Length) may be added by the underlying
        libraries (e.g. httplib).

        :param data: The request data (C{dict}) that will be sent to server.
        :type data: C{dict}

        :param headers: Headers that will be sent with the request.  This includes
                        any headers from the extra_headers instance var.
        :type headers: C{dict}
        """
        pass

    def _handle_response(self, response):
        """
        An extension point hook for processing the raw response objects from the server.

        :param response: The HTTP response object.
        :type response: C{httplib.HTTPResponse}
        """
        pass

    def __getattr__(self, name):
        """
        Does the proxy magic: returns a proxy callable that will perform request (when called).

        :return: The callable method object which will perform the request to JSON-RPC server.
        :rtype: L{_Method}
        """
        return self.method_class(self._request, name)

    def __repr__(self):
        return ("<%s for %s%s>" % (self.__class__.__name__, self.host, self.handler))


class RawServerProxy(ServerProxy):
    """
    An "extension" of L{ServerProxy} that does not attempt to parse the response as a JSON-RPC
    message, but simply returns the response data and file-like object.
    """

    def _request(self, methodname, params):
        """
        Overriden __request method which stops short of performing any parsing of the response.

        :param methodname: Name of method to be called.
        :type methodname: C{str}

        :param params: Parameters list to send to method.
        :type params: C{list}

        :return: The C{httplib.HTTPResponse} object (which contains headers, body, etc.)
        :rtype: C{httplib.HTTPResponse}
        :raise ProtocolError: Re-raises exception if non-200 response received.
        """
        self.id += 1 # Increment our "unique" identifier for every request.

        data = dict(id=self.id, method=methodname, params=params)

        headers = self.extra_headers

        self._prepare_request(data, headers)

        body = json.dumps(data)

        response = self.transport.request(self.host, self.handler, body, headers=headers)

        self._handle_response(response)

        return response

class CookieKeeperMixin(object):
    """
    A L{ServerProxy} that supports receiving and setting cookies.

    IMPORTANT: If this class is being used to support cookie-based sessions,
    it should be noted that it will only support a single session.  I.e. a
    single instance of this class should only pool connections for a single
    session!

    THIS CLASS IS NOT THREAD SAFE.

    :ivar response_cookies: A dict of all cookies sent from server (Set-Cookie headers), indexed by cookie name.
    :type response_cookies: C{dict} of C{str} to C{Cookie.SimpleCookie}

    :ivar request_cookies: A dict of all cookies that will be sent to server, indexed by cookie name.
    :type request_cookies: C{dict} of C{str} to C{Cookie.SimpleCookie}

    :ivar auto_add_cookies: Whether to automatically append any received response cookies to requests.
    :type auto_add_cookies: C{bool}
    """
    auto_add_cookies = False

    def __init__(self, *args, **kwargs):
        """
        :keyword request_cookies: A dict of request cookies that should be included.
        :type request_cookies: C{dict}
        """
        self.response_cookies = {}
        self.request_cookies = {}
        if 'request_cookies' in kwargs:
            self.request_cookies = kwargs.pop('request_cookies')
        super(CookieKeeperMixin, self).__init__(*args, **kwargs)

    def add_cookie(self, cookie):
        """
        Adds a *copy* of specified cookie to the request.

        Note that a single C{Cookie.SimpleCookie} instance can actually hold multiple cookie
        names/values.  If this is the case, the cookie will be broken into individual
        cookies for each "morsel".

        :param cookie: The cookie to add to the request.
        :type cookie: C{Cookie.SimpleCookie}
        """
        for (name, morsel) in cookie.items():
            self.request_cookies[name] = SimpleCookie(morsel.output())

    def _prepare_request(self, data, headers):
        """
        Extends base implementation to add any saved cookies to the request headers.

        :param data: The request data (C{dict}) that will be sent to server.
        :type data: C{dict}

        :param headers: Headers that will be sent with the request.  This includes
                        any headers from the extra_headers instance var.
        :type headers: C{dict}
        """
        super(CookieKeeperMixin, self)._prepare_request(data, headers)

        req_cookies = {}
        if self.auto_add_cookies and self.response_cookies:
            req_cookies.update(self.response_cookies)

        if self.request_cookies:
            req_cookies.update(self.request_cookies)

        for cookie in req_cookies.values():
            for name, morsel in cookie.items():
                headers["Cookie"] = "%s=%s" % (name, morsel.value)

    def _handle_response(self, response):
        """
        Extends base implementation to extract any cookies from the response.

        :param response: The HTTP response object.
        :type response: C{httplib.HTTPResponse}
        """
        super(CookieKeeperMixin, self)._handle_response(response)
        if len(response.msg.getheaders("Set-Cookie")):
            # Build a dict of cookies; we only want to keep the *last* cookie
            # set with a specific name.
            cookies = {}
            for hdr in response.msg.getheaders("Set-Cookie"):
                cookie = SimpleCookie(hdr)
                # XXX: This is a bit ugly looking.  Basically we are only going to
                # get one cookie at a time from this header; however, the SimpleCookie

                # object is designed to support multiple cookie names/values.
                key = cookie.keys()[0]
                cookies[key] = cookie

            self.response_cookies = cookies


class CookieAwareServerProxy(CookieKeeperMixin, ServerProxy):
    pass

class CookieAwareRawServerProxy(CookieKeeperMixin, RawServerProxy):
    pass
