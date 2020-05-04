# -*- coding: utf-8 -*-
__author__ = "jmrbcu"
import logging
from plugin_manager import Plugin, extends

logger = logging.getLogger(__name__)


class DummyFilePlugin(Plugin):

    id = "dummy_file"
    name = "Dummy File"
    version = "0.1"
    description = "Just a dummy plugin in a file"
    platform = "all"
    author = ['Jon Doe']
    author_email = "jon@doe.com"
    depends = []
    enabled = True
