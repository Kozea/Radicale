# -*- coding: utf-8 -*-

import logging, sys
from logging.handlers import SysLogHandler
from radicale import config

class log:
	def __init__(self):
		self.logger=logging.getLogger("radicale")
		self.logger.setLevel(config.get("logging", "facility"))
		
		loggingType=config.get("logging", "type")
		if loggingType == "stdout": 
			handler=logging.StreamHandler(sys.stdout)
		elif loggingType == "file": 
			handler=logging.FileHandler(config.get("logging", "logfile"))
		else:
			handler=logging.handlers.SysLogHandler("/dev/log")
			
		formatter = logging.Formatter('%(name)s %(asctime)s %(levelname)s %(message)s')
		handler.setFormatter(formatter)

		self.logger.addHandler(handler)
	def log(self, level, msg):
		self.logger.log(level, msg)

_LOGGING = log()

sys.modules[__name__] = _LOGGING

