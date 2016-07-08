# http-server

A simple HTTP server in Python, written to learn about the HTTP protocol and networking. It lacks almost all the features seen in modern servers, but it can actually be used to serve files.

To use it simply inherit from `server.BaseServer` and implement the HTTP methods you need. See the `StaticFileServer` and `Pastebin`/`PersistentPastebin` classes for examples.