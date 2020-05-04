# -*- coding: utf-8 -*-
__author__ = "jmrbcu"
import logging
from plugin_manager import Plugin, extends

logger = logging.getLogger(__name__)


class DummyPlugin(Plugin):

    id = "dummy"
    name = "Dummy"
    version = "0.1"
    description = "Just a dummy plugin"
    platform = "all"
    author = ['Jon Doe']
    author_email = "jon@doe.com"
    depends = []
    enabled = True
