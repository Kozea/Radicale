# -*- coding: utf-8 -*-

import sys
import logging
import os

from radicale import config

LEVELS = {	'debug': logging.DEBUG,
			'info': logging.INFO,
			'warning': logging.WARNING,
			'error': logging.ERROR,
			'critical': logging.CRITICAL}

level=LEVELS.get(config.get("logging", "level"), logging.NOTSET)

logger=logging.getLogger("radicale")
logger.setLevel(level=level)

handler=logging.FileHandler(os.path.expanduser(config.get("logging", "file")))
handler.setLevel(level=level)
		
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
		
handler.setFormatter(formatter)
		
logger.addHandler(handler)

sys.modules[__name__] = logger