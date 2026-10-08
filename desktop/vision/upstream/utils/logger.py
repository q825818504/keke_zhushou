from loguru import logger
logger.remove()
logger.add(lambda message: None,level='WARNING')
