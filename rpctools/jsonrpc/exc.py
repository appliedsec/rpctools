"""
Exception class hierarchy.
"""

__license__ = """Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License."""


class JsonRpcError(Exception):
    """
    Base class for *errors* (not faults) in jsonrpclib.

    "Errors" are distinguished by "faults" in that errors are problems in communicating
    with the server, whereas faults are problems reported back from the remote server.
    """

class ConnectionError(JsonRpcError):
    """
    Indicates an error at the TCP connection level.

    This exception is raised when a socket.error is raised from the underlying httplib layer.
    """

class ProtocolError(JsonRpcError):
    """
    Indicates an HTTP protocol error.

    This exception is raised when a non-200 response is received from the server.
    """
    def __init__(self, url, errcode, errmsg, headers):
        JsonRpcError.__init__(self, url, errcode, errmsg, headers)
        self.url = url
        self.errcode = errcode
        self.errmsg = errmsg
        self.headers = headers
    def __repr__(self):
        return (
            "<ProtocolError for %s: %s %s>" %
            (self.url, self.errcode, self.errmsg)
            )

class ResponseError(JsonRpcError):
    """
    Indicates an invalid JSON response format.

    The JSON-RPC spec clearly describes how responses should be structured.  This
    exception will be raised if the response does not match this structure.
    """
    pass

class Fault(Exception):
    """
    Represents an error that happened on the remote application that is being passed
    back over the RPC channel.

    For example, if I request a book with ISBN 12345 from a library API, but the library
    raises an Exception that the book does not exist, that will be represented as a
    Fault in the consumer code.
    """
    def __init__(self, errcode, errmsg, **extra):
        super(Fault, self).__init__(errmsg
                                    )
        self.errcode = errcode
        self.errmsg = errmsg

    def __repr__(self):
        return ("<%s %s: %r>" % (self.__class__.__name__, self.errcode, self.errmsg))
