# -*- coding: utf-8 -*-
from flask import Flask
from sentinel_gui.core import models
import os
import logging


def setup_logging(app):
    logger = logging.getLogger('sentinel_gui')
    logger.setLevel(logging.DEBUG)
    lh = logging.StreamHandler()
    lh.setLevel(logging.DEBUG)
    lh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s'))
    logger.addHandler(lh)

    app.logger.addHandler(lh)

app = Flask(__name__)
setup_logging(app)

sentinel_manager = models.SentinelManager()
sentinel_manager.add_sentinel_node(host=os.getenv('SENTINEL_SERVER', 'localhost'), port=os.getenv('SENTINEL_PORT', 26379))

from sentinel_gui import views
