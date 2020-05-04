# -*- coding: utf-8 -*-
__author__ = "jmrbcu"
import logging
from plugin_manager import Plugin, ExtensionPoint, extends

logger = logging.getLogger(__name__)


class BasicPlugin(Plugin):

    id = "basic"
    name = "Basic commands"
    version = "0.1"
    description = "Basic commands"
    platform = "all"
    author = ['Jon Doe']
    author_email = "jon@doe.com"
    depends = []
    enabled = True

    # other plugins can add archivers extending this extension point, look at plugin: 'archiver' for an example
    archivers = ExtensionPoint("archivers")

    @extends("application.arguments")
    def _commands(self):
        from args import Command, Argument

        filesystem_manager = self.plugin_manager.get_service("filesystem_manager")

        return [
            Command("touch", lambda o: filesystem_manager.touch(o.filename), "create a new file", (
                Argument("filename", help="path to the filename"),
            )),
            Command("remove", lambda o: filesystem_manager.remove(o.filename), "removes a file", (
                Argument("filename", help="path to the filename"),
            )),
            Command("compress", lambda o: filesystem_manager.compress(o.filename, o.file_type), "removes a file", (
                Argument("filename", help="path to the filename"),
                Argument("file_type", help="file type", choices=[archiver.file_type for archiver in self.archivers]),
            )),
        ]

    def configure(self):
        logger.debug("Running 'configure', this method will be run before enabling the plugin")

    def enable(self):
        logger.debug("Running 'enable', this method will be run when its time to enable the plugin")

        # This ia how you register a service. A service could be anything, functions, classes, objects.
        # Its basically something you can request later by name, not needing to know the import path.
        # Services can be requested by any plugin or anyone with access to the plugin manager.
        #
        # Here we register a filesystem service instance as a service
        from .filesystem_manager import FileSystemManager
        self.plugin_manager.register_service("filesystem_manager", FileSystemManager(self.archivers))
