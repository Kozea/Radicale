# -*- coding: utf-8 -*-

import logging, sys
from radicale import config

class log:
	def __init__(self):
		self.logger=logging.getLogger("radicale")
		self.logger.setLevel(config.get("logging", "facility"))
		
		handler=logging.FileHandler(config.get("logging", "logfile"))
		
		formatter = logging.Formatter('%(name)s %(asctime)s %(levelname)s %(message)s')
		handler.setFormatter(formatter)

		self.logger.addHandler(handler)
	def log(self, level, msg):
		self.logger.log(level, msg)

_LOGGING = log()

sys.modules[__name__] = _LOGGING