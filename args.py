# -*- coding: utf-8 -*-
__author__ = "jmrbcu"


class Argument(object):

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class Command(object):

    def __init__(self, name, cmd, help, arguments=None):
        self.name = name
        self.run = cmd
        self.help = help
        self.arguments = arguments if arguments else []

    def __str__(self):
        return "Command(%s)" % self.name