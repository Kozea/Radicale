---
layout: page
title: Logging
permalink: /logging/
---

Radicale logs to `stderr`. The verbosity of the log output can be controlled
with `--debug` command line argument or the `debug` configuration option in
the `logging` section.

This is the recommended configuration for use with modern init systems
(like **systemd**) or if you just test Radicale in a terminal.

You can configure Radicale to write its logging output to files (and even
rotate them).
This is useful if the process daemonizes or if your chosen method of running
Radicale doesn't handle logging output.

A logging configuration file can be specified in the `config` configuration
option in the `logging` section. The file format is explained in the
[Python Logging Module](https://docs.python.org/3/library/logging.config.html#configuration-file-format).

An example configuration to write the log output to the file `/var/log/radicale/log`:
```ini
[loggers]
keys = root

[handlers]
keys = file

[formatters]
keys = full

[logger_root]
# Change this to DEBUG or INFO for higher verbosity.
level = WARNING
handlers = file

[handler_file]
class = FileHandler
# Specify the output file here.
args = ('/var/log/radicale/log',)
formatter = full

[formatter_full]
format = %(asctime)s - [%(thread)x] %(levelname)s: %(message)s
```

You can specify multiple **logger**, **handler** and **formatter** if you want
to have multiple simultaneous log outputs.
