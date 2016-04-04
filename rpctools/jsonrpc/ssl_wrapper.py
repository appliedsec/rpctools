#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""
Extensions to allow HTTPS requests with SSL certificate validation.

Adapted from `http://code.google.com/p/googleappengine/source/browse/trunk/python/google/appengine/tools/https_wrapper.py`
"""

import re
import socket
import ssl

from rpctools import six
from rpctools.six.moves import http_client as httplib
from rpctools.six.moves.urllib.error import URLError

if six.PY2:
    from urllib2 import AbstractHTTPHandler
elif six.PY3:
    from urllib.request import AbstractHTTPHandler

__license__ = """Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License."""


class InvalidCertificateException(httplib.HTTPException):
    """Raised when a certificate is provided with an invalid hostname."""

    def __init__(self, host, cert, reason):
        """Constructor.

        Args:
            host: The hostname the connection was made to.
            cert: The SSL certificate (as a dictionary) the host returned.
        """
        httplib.HTTPException.__init__(self)
        self.host = host
        self.cert = cert
        self.reason = reason

    def __str__(self):
        return ('Host %s returned an invalid certificate (%s): %s\n'
                        'To learn more, see '
                        'http://code.google.com/appengine/kb/general.html#rpcssl' %
                        (self.host, self.reason, self.cert))


class CertValidatingHTTPSConnection(httplib.HTTPConnection):
    """An HTTPConnection that connects over SSL and validates certificates."""

    default_port = httplib.HTTPS_PORT

    def __init__(self, host, port=None, ssl_opts=None, validate_cert_hostname=True, strict=None, **kwargs):
        """Constructor.

        Args:
            host: The hostname. Can be in 'host:port' form.
            port: The port. Defaults to 443.
            ssl_opts: Options passed to ssl.wrap_socket
            strict: When true, causes BadStatusLine to be raised if the status line
                    can't be parsed as a valid HTTP/1.0 or 1.1 status line.
        """
        httplib.HTTPConnection.__init__(self, host, port, strict, **kwargs)
        self.validate_cert_hostname = validate_cert_hostname
        self.ssl_opts = ssl_opts or {}
        self.ssl_opts.setdefault('cert_reqs', ssl.CERT_REQUIRED if self.ssl_opts.get('ca_certs') else ssl.CERT_NONE)

    def _GetValidHostsForCert(self, cert):
        """Returns a list of valid host globs for an SSL certificate.

        Args:
            cert: A dictionary representing an SSL certificate.
        Returns:
            list: A list of valid host globs.
        """
        if 'subjectAltName' in cert:
            return [x[1] for x in cert['subjectAltName'] if x[0].lower() == 'dns']
        else:
            return [x[0][1] for x in cert['subject']
                            if x[0][0].lower() == 'commonname']

    def _ValidateCertificateHostname(self, cert, hostname):
        """Validates that a given hostname is valid for an SSL certificate.

        Args:
            cert: A dictionary representing an SSL certificate.
            hostname: The hostname to test.
        Returns:
            bool: Whether or not the hostname is valid for this certificate.
        """
        hosts = self._GetValidHostsForCert(cert)
        for host in hosts:
            host_re = host.replace('.', '\.').replace('*', '[^.]*')
            if re.search('^%s$' % (host_re,), hostname, re.I):
                return True
        return False

    def connect(self):
        "Connect to a host on a given (SSL) port."
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.host, self.port))
        self.sock = ssl.wrap_socket(sock, **self.ssl_opts)
        if (self.ssl_opts['cert_reqs'] & ssl.CERT_REQUIRED) and self.validate_cert_hostname:
            cert = self.sock.getpeercert()
            hostname = self.host.split(':', 0)[0]
            if not self._ValidateCertificateHostname(cert, hostname):
                raise InvalidCertificateException(hostname, cert, 'hostname mismatch')


class CertValidatingHTTPSHandler(AbstractHTTPHandler):
    """An HTTPHandler that validates SSL certificates."""

    def __init__(self, **kwargs):
        """Constructor. Any keyword args are passed to the httplib handler."""
        AbstractHTTPHandler.__init__(self)
        self._connection_args = kwargs

    def https_open(self, req):
        def http_class_wrapper(host, **kwargs):
            full_kwargs = dict(self._connection_args)
            full_kwargs.update(kwargs)
            return CertValidatingHTTPSConnection(host, **full_kwargs)
        try:
            return self.do_open(http_class_wrapper, req)
        except URLError as e:
            if type(e.reason) == ssl.SSLError and e.reason.args[0] == 1:
                raise InvalidCertificateException(req.host, '', e.reason.args[1])
            raise

    https_request = AbstractHTTPHandler.do_request_
