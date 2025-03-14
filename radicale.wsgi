"""
Radicale WSGI file (mod_wsgi and uWSGI compliant).

"""

import os
from radicale import application

# set an environment variable
os.environ.setdefault('SERVER_GATEWAY_INTERFACE', 'Web')
