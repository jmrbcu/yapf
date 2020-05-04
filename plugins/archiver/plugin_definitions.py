# -*- coding: utf-8 -*-
__author__ = "jmrbcu"
import logging
from plugin_manager import Plugin, extends

logger = logging.getLogger(__name__)


class ArchiverPlugin(Plugin):

    id = "archiver"
    name = "Archiver"
    version = "0.1"
    description = "Archiver plugin"
    platform = "all"
    author = ['Jon Doe']
    author_email = "jon@doe.com"
    depends = ["basic"]
    enabled = True

    @extends("archivers")
    def _commands(self):
        from .zip_archiver import ZipArchiver
        from .tgz_archiver import TgzArchiver
        return [ZipArchiver(), TgzArchiver()]
