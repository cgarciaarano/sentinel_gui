
# std lib
from contextlib import contextmanager
import logging

# 3rd parties
from redis.exceptions import ConnectionError

# local

logger = logging.getLogger('sentinel_gui')


@contextmanager
def redis_warn(redis_instance):
    try:
        yield
    except ConnectionError:
        logger.warn("Can't connect to redis instance {}".format(redis_instance))
