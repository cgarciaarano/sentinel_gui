# -*- coding: utf-8 -*-
from flask import Flask
from sentinel_gui.core import models
import os

sentinel_manager = models.SentinelManager()
sentinel_manager.add_sentinel_node(host=os.getenv('SENTINEL_SERVER', 'localhost'), port=os.getenv('SENTINEL_PORT', 26379))

app = Flask(__name__)

from sentinel_gui import views
