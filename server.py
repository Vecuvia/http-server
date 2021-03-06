import select, socket, time, os, json

def log_response(client, request, response):
    print("[{time}] - {ip} - \"{reqline}\" {status} {length}".format(
        ip=client.address[0],
        time=time.strftime("%Y-%m-%d %H:%M:%S"),
        reqline=request.reqline,
        status=response.status,
        length=response.length))

class Client(object):
    def __init__(self, socket, address):
        self.socket, self.address = socket, address
        self.socket.setblocking(0)
        self.data = b""
    def receive(self, buffer_size):
        """
        Reads data from the socket in the client's buffer, and returns the
        number of bytes read.
        """
        data = self.socket.recv(buffer_size)
        if data:
            self.data += data
        return len(data)
    def send(self, data):
        """
        Sends a response or some raw data to the client's socket.
        """
        if type(data) is Response:
            data = data.make()
        if type(data) is str:
            data = data.encode()
        self.socket.send(data)
    def close(self):
        """
        Closes the client's socket.
        """
        try:
            self.socket.shutdown(socket.SHUT_WR)
        except OSError:
            pass
        self.socket.close()

class Request(object):
    def __init__(self, method=None, uri=None, version=None, headers=None, content=None):
        self.method, self.uri, self.version = method, uri, version
        self.reqline = "{0} {1} {2}".format(self.method, self.uri, self.version)
        self.headers = headers if headers is not None else {}
        self.content = content
        self.malformed = False
    def __str__(self):
        if self.malformed:
            return "<Request MALFORMED>"
        return "<Request {0} {1}>".format(self.method, self.uri)
    @staticmethod
    def parse(data):
        try:
            headers, content = data.split(b"\r\n\r\n", maxsplit=1)
            request, *headers = headers.decode().split("\r\n")
            method, uri, version = request.split()
            headers = dict(line.split(":", 1) for line in headers)
            headers = {k: v.strip() for k, v in headers.items()}
            return Request(method, uri, version, headers, content)
        except ValueError as e:
            request = Request()
            request.malformed = True
            return request

class Response(object):
    def __init__(self, version, status, message, headers=None, content=None):
        self.version, self.status, self.message = version, status, message
        self.headers = headers if headers is not None else {}
        self.content = content if content is not None else b""
        if type(self.content) is str:
            self.content = self.content.encode()
        self.response = self.make()
        self.length = len(self.response)
    def __str__(self):
        return "<Response {0} {1}>".format(self.status, self.message)
    def make(self):
        result = "{0} {1} {2}\r\n".format(self.version, self.status, self.message)
        for header, data in self.headers.items():
            result += "{0}: {1}\r\n".format(header, data)
        result += "\r\n"
        result = result.encode()
        result += self.content
        return result

class BaseServer(object):
    def __init__(self, address="localhost", port=8080, config={}):
        self.config = {
            "ADDRESS": address,
            "PORT": port,
            "BACKLOG": 5,
            "BUFFER_SIZE": 8192,
            "VERSION": "HTTP/1.0",
            "ERROR_PAGE": "error.html",
            "BASE_DIRECTORY": "www"
        }
        self.load_config(config)
        self.bind_socket()
        self.read_list = [self.server]
        self.write_list = []
        self.clients = {}
        if os.path.isabs(self.config["BASE_DIRECTORY"]):
            self.basedir = self.config["BASE_DIRECTORY"]
        else:
            self.basedir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                self.config["BASE_DIRECTORY"])
    def bind_socket(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.config["ADDRESS"], self.config["PORT"]))
        self.server.listen(self.config["BACKLOG"])
    def load_config(self, config):
        """
        Loads a json configuration file or a dictionary into `self.config`.
        """
        if config is None:
            config = {}
        elif type(config) is str:
            try:
                with open(config) as config_file:
                    config = json.load(config_file)
            except FileNotFoundError as e:
                pass
        self.config.update(config)
    def serve_forever(self):
        """
        Starts the server.
        """
        print("Serving on port {0}".format(self.config["PORT"]))
        try:
            while True:
                self.poll()
        except KeyboardInterrupt:
            pass
    def accept(self):
        """
        Accepts a new client, adding it to `read_list`.
        """
        client = Client(*self.server.accept())
        #This is redundant but avoids us having to iterate through the clients
        # list to extract their sockets.
        self.clients[client.socket] = client
        self.read_list.append(client.socket)
    def read_from(self, sock):
        """
        Reads data from a socket, handling (mostly) gracefully a closed 
        connection.
        """
        client = self.clients[sock]
        data_length = client.receive(self.config["BUFFER_SIZE"])
        if data_length == 0:
            self.drop_client(client)
            return
        # We read BUFFER_SIZE bytes at a time - if we get less than that,
        #  then this connection has `no_more_data` for us.
        no_more_data = data_length < self.config["BUFFER_SIZE"]
        if no_more_data:
            # This is possibly redundant
            if socket not in self.write_list:
                # The socket is finished and it's waiting for an answer.
                self.write_list.append(sock)
    def parse_request(self, client):
        return Request.parse(client.data)
    def make_error(self, error_code, error_message):
        """
        Utility function - returns an error response with a lightweight,
        utterly uninformative html page describing it.
        """
        return Response(self.config["VERSION"], error_code, error_message,
            headers={"Content-type": "text/html"},
            content=open(self.config["ERROR_PAGE"]).read().format(
                error_code=error_code, error_message=error_message))
    def make_redirect(self, location):
        """
        Utility function - returns a 303 See Other redirect to `location`.
        """
        return Response(self.config["VERSION"], 303, "See Other",
            headers={"Location": location})
    def serve_file(self, mime_type, content):
        """
        Utility function - returns a 200 Ok response with mime type `mime_type`
        and content `content`.
        """
        return Response(self.config["VERSION"], 200, "Ok",
            headers={"Content-type": mime_type},
            content=content)
    def make_response(self, request):
        """
        Despite the name, it doesn't make any responses but instead
        dispatches the appropriate method, returning a 501 Not Implemented
        error if no such method is found.
        """
        if request.malformed:
            return self.make_error(400, "Bad Request")
        method = "do_" + request.method.upper()
        if hasattr(self, method):
            return getattr(self, method)(request)
        else:
            return self.make_error(501, "Not Implemented")
    def reply_to(self, sock):
        client = self.clients[sock]
        try:
            request = self.parse_request(client)
            response = self.make_response(request)
            client.send(response)
            log_response(client, request, response)
        except (BrokenPipeError, ConnectionResetError) as e:
            pass
        finally:
            #TODO: No keep-alive is implemented yet.
            self.drop_client(client)
    def drop_client(self, client):
        """
        Drops a client, removing all referencies to it and closing its
        socket.
        """
        sock = client.socket
        if sock in self.write_list:
            self.write_list.remove(sock)
        #This could lead to errors if called within the `for in writable`
        # loop. But I didn't see any yet.
        if sock in self.writable:
            self.writable.remove(sock)
        self.read_list.remove(sock)
        client.close()
        del self.clients[sock]
    def poll(self):
        self.readable, self.writable, self.errored = select.select(
            self.read_list, self.write_list, self.read_list)
        for sock in self.readable:
            if sock is self.server:
                # We have a new client - let us `accept` it.
                self.accept()
            else:
                # Otherwise, we still need to get some data from the socket.
                self.read_from(sock)
        for sock in self.writable:
            self.reply_to(sock)
    def sanitize(self, path):
        #TODO: don't do this, it's possibly silly
        return "/".join(filter(lambda p: p not in (".", ".."), path.split("/")[1:]))
    def split_uri(self, uri):
        #TODO: don't do this, it's silly
        uri, _, query_string = uri.partition("?")
        return uri, query_string
    def get_mimetype(self, uri):
        return {
            "html": ("text/html", False),
            "htm": ("text/html", False),
            "txt": ("text/plain", False),
            "js": ("text/javascript", False),
            }.get(uri.rpartition(".")[2].lower(),
                ("application/octet-stream", True))

class StaticFileServer(BaseServer):
    """
    Simple static file server built on top of `BaseServer`, serves files
    from its BASE_DIRECTORY directory.
    """
    def get_file(self, uri):
        """
        Returns what file we need to serve - returns `dir/index.html` if
        `uri` points to a directory.
        """
        uri, query_string = self.split_uri(uri)
        path = self.sanitize(uri)
        path = os.path.join(self.basedir, path)
        #TODO: Could this throw a FileNotFoundError?
        if os.path.isdir(path):
            path = os.path.join(path, "index.html")
        return path, query_string
    def do_HEAD(self, request):
        path, query_string = self.get_file(request.uri)
        try:
            mime_type, is_binary = self.get_mimetype(path)
            return Response(self.config["VERSION"], 200, "OK",
                headers={
                    "Content-type": mime_type,
                    "Content-length": os.path.getsize(path)
                })
        except FileNotFoundError:
            return self.make_error(404, "Not Found")
    def do_GET(self, request):
        path, query_string = self.get_file(request.uri)
        try:
            mime_type, is_binary = self.get_mimetype(path)
            with open(path, "r" + "b"*is_binary) as file:
                content = file.read()
            return Response(self.config["VERSION"], 200, "OK",
                headers={"Content-type": mime_type},
                content=content)
        except FileNotFoundError:
            return self.make_error(404, "Not Found")

if __name__ == "__main__":
    StaticFileServer(address="", port=8888).serve_forever()