import os

app_prefix = 'SENTINEL_UI_'

DEBUG = os.getenv('FLASK_DEBUG', False)

# WTForms stuff
WTF_CSRF_ENABLED = os.getenv('{prefix}_WTF_CSRF_ENABLED'.format(prefix=app_prefix), True)
SECRET_KEY = os.getenv('{prefix}SECRET_KEY'.format(prefix=app_prefix), 'you-will-never-guess')

# Redis stuff
REDIS_SOCKET_TIMEOUT = os.getenv('{prefix}REDIS_SOCKET_TIMEOUT'.format(prefix=app_prefix), 0.1)
REDIS_POLLING_PERIOD = os.getenv('{prefix}REDIS_POLLING_PERIOD'.format(prefix=app_prefix), 0.01)
