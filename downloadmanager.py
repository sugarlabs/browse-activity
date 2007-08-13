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

import os
import logging
import tempfile
from gettext import gettext as _
import time

from xpcom.nsError import *
from xpcom import components
from xpcom.components import interfaces
from xpcom.server.factory import Factory

from sugar.datastore import datastore
from sugar.clipboard import clipboardservice
from sugar import profile
from sugar import objects

_browser = None
_temp_path = '/tmp'
def init(browser, temp_path):
    global _browser
    _browser = browser

    global _temp_path
    _temp_path = temp_path

_active_ds_writes = 0
_quit_callback = None

def can_quit():
    return _active_ds_writes == 0

def set_quit_callback(callback):
    _quit_callback = callback

class DownloadManager:
    _com_interfaces_ = interfaces.nsIHelperAppLauncherDialog

    def promptForSaveToFile(self, launcher, window_context,
                            default_file, suggested_file_extension):
        file_class = components.classes["@mozilla.org/file/local;1"]
        dest_file = file_class.createInstance(interfaces.nsILocalFile)

        if not default_file:
            default_file = time.time()
            if suggested_file_extension:
                default_file = '%s.%s' % (default_file, suggested_file_extension)

        global _temp_path
        if not os.path.exists(_temp_path):
            os.makedirs(_temp_path)
        file_path = os.path.join(_temp_path, default_file)

        dest_file.initWithPath(file_path)
        
        return dest_file
                            
    def show(self, launcher, context, reason):
        launcher.saveToDisk(None, False)
        return NS_OK

components.registrar.registerFactory('{64355793-988d-40a5-ba8e-fcde78cac631}"',
                                     'Sugar Download Manager',
                                     '@mozilla.org/helperapplauncherdialog;1',
                                     Factory(DownloadManager))

class Download:
    _com_interfaces_ = interfaces.nsITransfer

    def init(self, source, target, display_name, mime_info, start_time, temp_file,
             cancelable):
        self._source = source
        self._mime_type = mime_info.MIMEType
        self._temp_file = temp_file
        self._target_file = target.queryInterface(interfaces.nsIFileURL).file
        self._dl_jobject = None
        self._cb_object_id = None
        self._last_update_time = 0
        self._last_update_percent = 0

        return NS_OK

    def onStateChange(self, web_progress, request, state_flags, status):
        if state_flags == interfaces.nsIWebProgressListener.STATE_START:
            self._create_journal_object()
            self._create_clipboard_object()
        elif state_flags == interfaces.nsIWebProgressListener.STATE_STOP:
            if NS_FAILED(status): # download cancelled
                return

            cb_service = clipboardservice.get_instance()
            # Test if the object still exists in the clipboard as it could have 
            # been removed.
            if cb_service.get_object(self._cb_object_id):
                cb_service.set_object_percent(self._cb_object_id, 100)

            path, file_name = os.path.split(self._target_file.path)

            self._dl_jobject.metadata['title'] = _('File %s downloaded from\n%s.') % \
                (file_name, self._source.spec)
            self._dl_jobject.file_path = self._target_file.path

            if self._mime_type == 'application/octet-stream':
                sniffed_mime_type = objects.mime.get_for_file(self._target_file.path)
                self._dl_jobject.metadata['mime_type'] = sniffed_mime_type

            global _active_ds_writes
            _active_ds_writes = _active_ds_writes + 1
            datastore.write(self._dl_jobject,
                            reply_handler=self._internal_save_cb,
                            error_handler=self._internal_save_error_cb,
                            timeout=360000)

    def _cleanup_datastore_write(self):
        global _active_ds_writes
        _active_ds_writes = _active_ds_writes - 1

        os.remove(self._dl_jobject.file_path)
        self._dl_jobject.destroy()
        self._dl_jobject = None

        global _quit_callback
        if _active_ds_writes == 0 and not _quit_callback is None:
            _quit_callback()

    def _internal_save_cb(self):
        self._cleanup_datastore_write()

    def _internal_save_error_cb(self, err):
        logging.debug("Error saving activity object to datastore: %s" % err)
        self._cleanup_datastore_write()

    def onProgressChange64(self, web_progress, request, cur_self_progress,
                           max_self_progress, cur_total_progress,
                           max_total_progress):
        path, file_name = os.path.split(self._target_file.path)
        percent = (cur_self_progress  * 100) / max_self_progress

        if (time.time() - self._last_update_time) < 10 and \
           (percent - self._last_update_percent) < 10:
            return

        self._last_update_time = time.time()
        self._last_update_percent = percent

        if percent < 100:
            self._dl_jobject.metadata['title'] = _('Downloading %s from\n%s. Progress %i%%.') % \
                (file_name, self._source.spec, percent)
            datastore.write(self._dl_jobject)

            cb_service = clipboardservice.get_instance()
            # Test if the object still exists in the clipboard as it could have 
            # been removed.
            if cb_service.get_object(self._cb_object_id):
                cb_service.set_object_percent(self._cb_object_id, percent)

    def _create_journal_object(self):
        path, file_name = os.path.split(self._target_file.path)

        self._dl_jobject = datastore.create()
        self._dl_jobject.metadata['title'] = _('Downloading %s from \n%s.') % \
            (file_name, self._source.spec)

        self._dl_jobject.metadata['keep'] = '0'
        self._dl_jobject.metadata['buddies'] = ''
        self._dl_jobject.metadata['preview'] = ''
        self._dl_jobject.metadata['icon-color'] = profile.get_color().to_string()
        self._dl_jobject.metadata['mime_type'] = self._mime_type
        self._dl_jobject.file_path = ''
        datastore.write(self._dl_jobject)

    def _create_clipboard_object(self):
        path, file_name = os.path.split(self._target_file.path)

        cb_service = clipboardservice.get_instance()
        self._cb_object_id = cb_service.add_object(file_name)
        
        # TODO: avoid by now adding two formats, as they would create two
        # identical files in /tmp
        #cb_service.add_object_format(self._cb_object_id,
        #                             self._mime_type,
        #                             'file://' + self._target_file.path.encode('utf8'),
        #                             on_disk = True)

        # Also add the 'text/uri-list' target for the same file path.
        cb_service.add_object_format(self._cb_object_id,
                                     'text/uri-list',
                                     'file://' + self._target_file.path.encode('utf8'),
                                     on_disk = True)

components.registrar.registerFactory('{23c51569-e9a1-4a92-adeb-3723db82ef7c}"',
                                     'Sugar Download',
                                     '@mozilla.org/transfer;1',
                                     Factory(Download))

