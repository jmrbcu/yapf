# -*- coding: utf-8 -*-
__author__ = "jmrbcu"
try:
    import pathlib
except:
    import pathlib2 as pathlib
import tarfile
from basic.archiver import Archiver


class TgzArchiver(Archiver):

    def __init__(self):
        super(TgzArchiver, self).__init__()
        self.file_type = "tar.gz"

    def compress(self, filename):
        dest = str(pathlib.Path(filename).with_suffix(".tar.gz"))
        with tarfile.open(dest, "w:gz") as tar:
            tar.add(str(filename))
        return True
