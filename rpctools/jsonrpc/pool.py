"""
Support for connection pooling.  (BETA!)
"""
from __future__ import absolute_import
from threading import local as ThreadLocal

__license__ = """Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License."""

class Pool(ThreadLocal):
    """
    A thread-local subclass that is responsible for managing a pool of connections,
    indexed by host name.

    @ivar connections: Thread-local connection pool.
    :type connections: C{dict} of C{str} to C{httplib.HTTPConnection}
    """
    def __init__(self):
        self.connections = {}

pool = Pool()

class TLSConnectionPoolMixin(object):
    """
    A mixin for Transport classes that attempts to use connections from a thread-local-storage
    pool before creating new connections.

    The connections are indexed by host.  This will NOT work if you are mixing HTTP and
    HTTPS connections to the same host!!!

    :param host: The host for which connection is being requested.
    :type host: C{str}

    :return: An existing or new C{httplib.HTTPConnection}
    :rtype: C{httplib.HTTPConnection}
    """

    def request(self, host, handler, body, headers=None, verbose=False):
        """
        Override to add Connection: keep-alive header to request.
        """
        if headers is None:
            headers = {}
        headers['Connection'] = 'keep-alive'
        return super(TLSConnectionPoolMixin, self).request(host, handler, body, headers=headers, verbose=verbose)

    def connect(self, host):
        """
        Overrides method to return an existing connection from thread-local pool
        instead of creating a new one.
        """
        if not host in pool.connections:
            self.logger.debug("No connection in pool for %s, creating." % host)
            conn = super(TLSConnectionPoolMixin, self).connect(host)
            pool.connections[host] = conn
        else:
            self.logger.debug("Found EXISTING connection in pool for %s." % host)
            conn = pool.connections[host]
        return conn

    def handle_connection_error(self, host, x):
        """
        Remove the offending connection from the pool.
        """
        self.logger.info('Deleting bad connection to host %s' % host)
        del pool.connections[host]
