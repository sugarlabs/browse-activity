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

_browser = None
def init(browser):
    global _browser
    _browser = browser

class DownloadManager:
    _com_interfaces_ = interfaces.nsIHelperAppLauncherDialog

    def promptForSaveToFile(self, launcher, window_context,
                            default_file, suggested_file_extension):
        file_class = components.classes["@mozilla.org/file/local;1"]
        dest_file = file_class.createInstance(interfaces.nsILocalFile)

        if default_file:
            file_path = os.path.join(tempfile.gettempdir(), default_file)
        else:
            f, file_path = tempfile.mkstemp(suggested_file_extension)
            del f

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
        self._mime_info = mime_info
        self._temp_file = temp_file
        self._target_file = target.queryInterface(interfaces.nsIFileURL).file
        self._jobject = None
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
                pass
            else:
                path, file_name = os.path.split(self._target_file.path)

                self._jobject['title'] = _('File %s downloaded from\n%s.') % \
                    (file_name, self._source.spec)
                self._jobject.file_path = self._target_file.path
                datastore.write(self._jobject)

                cb_service = clipboardservice.get_instance()
                cb_service.set_object_percent(self._cb_object_id, 100)

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
            self._jobject['title'] = _('Downloading %s from\n%s. Progress %i%%.') % \
                (file_name, self._source.spec, percent)
            datastore.write(self._jobject)

            cb_service = clipboardservice.get_instance()
            cb_service.set_object_percent(self._cb_object_id, percent)

    def _create_journal_object(self):
        path, file_name = os.path.split(self._target_file.path)
        mime_type = self._mime_info.MIMEType

        self._jobject = datastore.create()
        self._jobject['title'] = _('Downloading %s from \n%s.') % \
            (file_name, self._source.spec)

        if mime_type in ['application/pdf', 'application/x-pdf']:
            self._jobject['activity'] = 'org.laptop.sugar.Xbook'
            self._jobject['icon'] = 'theme:object-text'
        else:
            self._jobject['activity'] = ''
            self._jobject['icon'] = 'theme:object-link'

        self._jobject['date'] = str(time.time())
        self._jobject['keep'] = '0'
        self._jobject['buddies'] = ''
        self._jobject['preview'] = ''
        self._jobject['icon-color'] = profile.get_color().to_string()
        self._jobject.file_path = ''
        datastore.write(self._jobject)

    def _create_clipboard_object(self):
        path, file_name = os.path.split(self._target_file.path)
        mime_type = self._mime_info.MIMEType

        cb_service = clipboardservice.get_instance()
        self._cb_object_id = cb_service.add_object(file_name)
        cb_service.add_object_format(self._cb_object_id,
                                     mime_type,
                                     'file://' + self._target_file.path.encode('utf8'),
                                     on_disk = True)

components.registrar.registerFactory('{23c51569-e9a1-4a92-adeb-3723db82ef7c}"',
                                     'Sugar Download',
                                     '@mozilla.org/transfer;1',
                                     Factory(Download))

