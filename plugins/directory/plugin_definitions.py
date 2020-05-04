# -*- coding: utf-8 -*-
__author__ = "jmrbcu"
try:
    import pathlib
except:
    import pathlib2 as pathlib
import logging
from plugin_manager import Plugin, extends

logger = logging.getLogger(__name__)


class DirectoryPlugin(Plugin):

    id = "directory"
    name = "Directory commands"
    version = "0.1"
    description = "Directory related commands"
    platform = "all"
    author = ['Jon Doe']
    author_email = "jon@doe.com"
    depends = ["basic"]  # dependency example: this plugin depends on the "basic" plugin so it will be loaded after it
    enabled = True

    @extends("application.arguments")
    def _commands(self):
        from args import Command, Argument

        filesystem_manager = self.plugin_manager.get_service("filesystem_manager")
        return [
            Command("mkdir", lambda o: filesystem_manager.mkdir(o), "create a new directory", (
                Argument("path", help="path to the directory"),
            )),
            Command("rmdir", lambda o: filesystem_manager.rmdir(o), "removes a directory", (
                Argument("path", help="path to the directory"),
            )),
        ]

