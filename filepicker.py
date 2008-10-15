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

import gtk
import hulahop

import xpcom
from xpcom import components
from xpcom.components import interfaces
from xpcom.server.factory import Factory

from sugar.graphics.objectchooser import ObjectChooser

_temp_files_to_clean = []

def cleanup_temp_files():
    for temp_file in _temp_files_to_clean:
        if os.path.exists(temp_file):
            os.remove(temp_file)
            _temp_files_to_clean.remove(temp_file)
        else:
            logging.debug('filepicker.cleanup_temp_files: no file %r' 
                          % temp_file)

class FilePicker:
    _com_interfaces_ = interfaces.nsIFilePicker

    cid = '{57901c41-06cb-4b9e-8258-37323327b583}'
    description = 'Sugar File Picker'

    def __init__(self):
        self._title = None
        self._parent = None
        self._file = None
    
    def appendFilter(self, title, filter):
        logging.warning('FilePicker.appendFilter: UNIMPLEMENTED')

    def appendFilters(self, filterMask):
        logging.warning('FilePicker.appendFilters: UNIMPLEMENTED')

    def init(self, parent, title, mode):
        self._title = title
        self._file = None
        self._parent = hulahop.get_view_for_window(parent)
        
        if mode != interfaces.nsIFilePicker.modeOpen:
            raise xpcom.COMException(NS_ERROR_NOT_IMPLEMENTED)

    def show(self):
        chooser = ObjectChooser(parent=self._parent)
        try:
            result = chooser.run()
            if result == gtk.RESPONSE_ACCEPT:
                logging.debug('FilePicker.show: %r' % 
                              chooser.get_selected_object())
                jobject = chooser.get_selected_object()
                if jobject and jobject.file_path:
                    ext = os.path.splitext(jobject.file_path)[1]
                    f, new_temp = tempfile.mkstemp(ext)
                    del f

                    global _temp_files_to_clean
                    _temp_files_to_clean.append(new_temp)
                    shutil.copy(jobject.file_path, new_temp)

                    self._file = new_temp
        finally:
            chooser.destroy()
            del chooser

        if self._file:
            return interfaces.nsIFilePicker.returnOK
        else:
            return interfaces.nsIFilePicker.returnCancel

    def set_defaultExtension(self, default_extension):
        logging.warning('FilePicker.set_defaultExtension: UNIMPLEMENTED')

    def get_defaultExtension(self):
        logging.warning('FilePicker.get_defaultExtension: UNIMPLEMENTED')
        return None

    def set_defaultString(self, default_string):
        logging.warning('FilePicker.set_defaultString: UNIMPLEMENTED')

    def get_defaultString(self):
        logging.warning('FilePicker.get_defaultString: UNIMPLEMENTED')
        return None

    def set_displayDirectory(self, display_directory):
        logging.warning('FilePicker.set_displayDirectory: UNIMPLEMENTED')

    def get_displayDirectory(self):
        logging.warning('FilePicker.get_displayDirectory: UNIMPLEMENTED')
        return None

    def set_filterIndex(self, filter_index):
        logging.warning('FilePicker.set_filterIndex: UNIMPLEMENTED')

    def get_filterIndex(self):
        logging.warning('FilePicker.get_filterIndex: UNIMPLEMENTED')
        return None

    def get_file(self):
        logging.debug('FilePicker.get_file: %r' % self._file)
        if self._file:
            cls = components.classes["@mozilla.org/file/local;1"]
            local_file = cls.createInstance(interfaces.nsILocalFile)
            local_file.initWithPath(self._file)
            return local_file
        else:
            return None

    def get_Files(self):
        logging.warning('FilePicker.get_Files: UNIMPLEMENTED')
        return None

    def get_FileURL(self):
        logging.warning('FilePicker.get_FileURL: UNIMPLEMENTED')
        return None

components.registrar.registerFactory(FilePicker.cid,
                                        FilePicker.description,
                                        '@mozilla.org/filepicker;1',
                                        Factory(FilePicker))
