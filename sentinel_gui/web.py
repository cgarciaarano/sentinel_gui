# -*- coding: utf-8 -*-
from flask import Flask
from sentinel_gui.core import models

app = Flask(__name__)

manager = models.SentinelManager()

from sentinel_gui import views
