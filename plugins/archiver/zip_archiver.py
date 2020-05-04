# -*- coding: utf-8 -*-
__author__ = "jmrbcu"
try:
    import pathlib
except:
    import pathlib2 as pathlib
from zipfile import ZipFile
from basic.archiver import Archiver


class ZipArchiver(Archiver):

    def __init__(self):
        super(ZipArchiver, self).__init__()
        self.file_type = "zip"

    def compress(self, filename):
        dest = str(pathlib.Path(filename).with_suffix(".zip"))
        with ZipFile(dest, "w") as zip:
            zip.write(str(filename))
        return True

