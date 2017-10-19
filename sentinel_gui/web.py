# -*- coding: utf-8 -*-
# std lib
import logging

# 3rd parties
from flask import Flask
from flask_socketio import SocketIO

# local
from sentinel_gui import settings


def setup_logging(app):
    logger = logging.getLogger('sentinel_gui')
    loglevel = logging.DEBUG if settings.DEBUG else logging.INFO
    logger.setLevel(loglevel)

    lh = logging.StreamHandler()
    lh.setLevel(loglevel)
    lh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s'))

    logger.addHandler(lh)
    app.logger.addHandler(lh)

app = Flask(__name__)
app.config.from_object('sentinel_gui.settings')
setup_logging(app)
socketio = SocketIO(app)

from sentinel_gui.core import models
sentinel_manager = models.SentinelManager()

from sentinel_gui import views

if __name__ == '__main__':
    socketio.run(app)
