# Copyright (C) 2007, One Laptop Per Child
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import logging
import os
import tempfile
import shutil

from gi.repository import Gtk

from sugar3.graphics.objectchooser import ObjectChooser
from sugar3.activity.activity import get_activity_root


_temp_dirs_to_clean = []


def cleanup_temp_files():
    while _temp_dirs_to_clean:
        temp_dir = _temp_dirs_to_clean.pop()
        if os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        else:
            logging.debug('filepicker.cleanup_temp_files: no file %r',
                          temp_dir)


class FilePicker(ObjectChooser):
    def __init__(self, parent):
        ObjectChooser.__init__(self, parent)

    def run(self):
        jobject = None
        _file = None
        try:
            result = ObjectChooser.run(self)
            if result == Gtk.ResponseType.ACCEPT:
                jobject = self.get_selected_object()
                logging.debug('FilePicker.show: %r', jobject)

                if jobject and jobject.file_path:
                    tmp_dir = tempfile.mkdtemp(
                        prefix='',
                        dir=os.path.join(get_activity_root(), 'tmp'))
                    _file = os.path.join(tmp_dir, _basename_strip(jobject))

                    os.rename(jobject.file_path, _file)

                    global _temp_dirs_to_clean
                    _temp_dirs_to_clean.append(tmp_dir)

                    logging.debug('FilePicker.show: file=%r', _file)
        finally:
            if jobject is not None:
                jobject.destroy()

        return _file


def _basename_strip(jobject):
    name = jobject.metadata.get('title', 'untitled')
    name = name.replace(os.sep, ' ').strip()

    root_, mime_extension = os.path.splitext(jobject.file_path)

    if not name.endswith(mime_extension):
        name += mime_extension

    return name
