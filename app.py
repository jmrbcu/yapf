# -*- coding: utf-8 -*-
__author__ = "jmrbcu"
import sys
import argparse
import logging.config
try:
    import pathlib
except:
    import pathlib2 as pathlib

import plugins
from args import Command, Argument
from plugin_manager import PluginManager, ExtensionPoint, extends

LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s [%(levelname)s] %(name)s.%(funcName)s:%(lineno)d %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "level": "DEBUG",
            "stream": "ext://sys.stdout"
        },
    },
    "loggers": {
        "": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True
        },
    },
}
logging.config.dictConfig(LOG_CONFIG)
logger = logging.getLogger(__name__)


class Application(object):

    # example extension point: any plugin can extend this extension point with new commands
    # extension points are lazy, meaning all extenders to this extension point will be evaluated
    # the first time someone access the extension point, after that, the value is cached.
    arguments = ExtensionPoint("application.arguments")

    def __init__(self, search_path):
        super(Application, self).__init__()
        self.commands = {}
        self.disabled_plugins = ["dummy"]
        self.plugin_manager = PluginManager(str(search_path))

    @extends("application.arguments")
    def default_commands(self):
        return [
            Command("list", self.list, "list a directory", [
                Argument("path", help="path to list", nargs="?", default="."),
            ]),
            Command("list-plugins", self.list_plugins, "list all available plugins (not including disabled ones)"),
        ]

    def start(self):
        # add pluing package to the top level import so we can do this inside the plugins:
        # from plugin_abc import xyz
        # instead of:
        # from plugins.plugin_abc import xyz
        sys.path.append(str(pathlib.Path(plugins.__file__).parent))

        exit_code = 0
        try:
            # This is an example of how to register an extension point and extender manually.
            # In normal cases, when a plugin is loaded by the plugin manager all
            # its extension points and extenders are automatically loaded.
            self.plugin_manager.register_extension_point(Application.arguments)
            self.plugin_manager.register_extender(self.default_commands)

            # start finding plugins in the search path, also, do not load any disabled plugins
            self.plugin_manager.find_plugins(self.disabled_plugins)
            self.plugin_manager.configure_plugins()
            self.plugin_manager.enable_plugins()

            # configure the argument parser
            option_parser = argparse.ArgumentParser(prog="fstool")
            command_parser = option_parser.add_subparsers(help="commands", dest="command")

            # extension point usage example: all plugins will extend this extension point if they
            # want to add new commands to the application
            for item in self.arguments:
                if isinstance(item, Argument):
                    option_parser.add_argument(*item.args, **item.kwargs)
                elif isinstance(item, Command):
                    if item.name in self.commands:
                        raise ValueError("We have a command with the same name: %s", item.name)

                    # add sub command
                    parser = command_parser.add_parser(item.name, help=item.help)
                    for argument in item.arguments:
                        parser.add_argument(*argument.args, **argument.kwargs)

                    # store the command so we can later execute it by name
                    self.commands[item.name] = item

            # now that everything is setup, we can parse the command line
            options = option_parser.parse_args()

            # execute the command
            logger.debug("Executing command: %s with options: %s", options.command, options)
            exit_code = self.commands[options.command].run(options)
        except SystemExit as e:
            exit_code = e.code
        except:
            logger.critical("Houston, we have a problem!", exc_info=True)
            exit_code = 1
        finally:
            sys.exit(0 if exit_code is None else exit_code)

    def list(self, options):
        for entry in pathlib.Path(options.path).expanduser().glob("*"):
            print(entry)

    def list_plugins(self, options):
        for plugin in self.plugin_manager.plugins:
            print("%s: %s" % (plugin.name, plugin.description))
            print("Dependencies: %s" % plugin.depends)
            print("")


def main():
    search_path = pathlib.Path(plugins.__file__).parent
    application = Application(search_path)
    application.start()


if __name__ == "__main__":
    main()