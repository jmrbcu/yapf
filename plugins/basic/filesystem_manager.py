# -*- coding: utf-8 -*-
__author__ = "jmrbcu"
try:
    import pathlib
except:
    import pathlib2 as pathlib


class FileSystemManager(object):

    def __init__(self, archivers):
        self.archivers = {archiver.file_type: archiver for archiver in archivers}

    def compress(self, filename, file_type):
        filename = str(pathlib.Path(filename).expanduser())
        archiver = self.archivers.get(file_type)
        if not archiver:
            return False
        return archiver.compress(filename)

    def touch(self, filename):
        pathlib.Path(filename).expanduser().touch()

    def remove(self, filename):
        pathlib.Path(filename).expanduser().unlink()

    def mkdir(self, options):
        pathlib.Path(options.path).mkdir()

    def rmdir(self, options):
        pathlib.Path(options.path).rmdir()

