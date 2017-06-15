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

## Logging to a file

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

The parent folder of the log files must exist and must be writable by Radicale.

**Security:** The log files should not be readable by unauthorized users. Set
permissions accordingly.

### Timed rotation of disk log files

An example **handler** configuration to write the log output to the file `/var/log/radicale/log` and rotate it .
Replace the section `handle_file` from the file logging example:
```ini
[handler_file]
class = handlers.TimedRotatingFileHandler
# Specify the output file and parameter for rotation here.
# See https://docs.python.org/3/library/logging.handlers.html#logging.handlers.TimedRotatingFileHandler
# Example: rollover at midnight and keep 7 files (means one week)
args = ('/var/log/radicale/log', when='midnight', interval=1, backupCount=7)
formatter = full
```

### Rotation of disk log files based on size

An example **handler** configuration to write the log output to the file `/var/log/radicale/log` and rotate it .
Replace the section `handle_file` from the file logging example:
```ini
[handler_file]
class = handlers.RotatingFileHandler
# Specify the output file and parameter for rotation here.
# See https://docs.python.org/3/library/logging.handlers.html#logging.handlers.RotatingFileHandler
# Example: rollover at 100000 kB and keep 10 files (means 1 MB)
args = ('/var/log/radicale/log', 'a', 100000, 10)
formatter = full
```
