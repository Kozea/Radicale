#!/usr/bin/env python3

"""
Radicale FastCGI Example.

Launch a Radicale FastCGI server according to configuration.

This script relies on flup but can be easily adapted to use another
WSGI-to-FastCGI mapper.

"""

from flup.server.fcgi import WSGIServer
from radicale import application

if __name__ == "__main__":
    WSGIServer(application).run()
