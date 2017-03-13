# -*- coding: utf-8 -*-
# std lib
import logging

# 3rd parties
from flask import Flask
from flask_socketio import SocketIO, emit

# local
from sentinel_gui.core import models


def setup_logging(app):
    logger = logging.getLogger('sentinel_gui')
    logger.setLevel(logging.DEBUG)
    lh = logging.StreamHandler()
    lh.setLevel(logging.DEBUG)
    lh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s'))
    logger.addHandler(lh)

    app.logger.addHandler(lh)

app = Flask(__name__)
app.config.from_object('sentinel_gui.settings')
setup_logging(app)
socketio = SocketIO(app)

sentinel_manager = models.SentinelManager()
#sentinel_manager.add_sentinel_node(host=os.getenv('SENTINEL_SERVER', 'localhost'), port=os.getenv('SENTINEL_PORT', 26379))

from sentinel_gui import views

if __name__ == '__main__':
    socketio.run(app)