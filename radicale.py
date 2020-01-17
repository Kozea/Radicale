#!/usr/bin/env python3

"""
Radicale CalDAV Server.

Launch the server according to configuration and command-line options.

"""

import runpy

if __name__ == "__main__":
    runpy.run_module("radicale", run_name="__main__")
