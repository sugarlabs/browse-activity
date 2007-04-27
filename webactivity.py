# Copyright (C) 2006, Red Hat, Inc.
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
from gettext import gettext as _

import gtk
import dbus

import sugar.browser
from sugar.activity import activity
from sugar.clipboard import clipboardservice
from sugar import env

from webview import WebView
from webtoolbar import WebToolbar

_HOMEPAGE = 'file:///home/olpc/Library/index.html'

class WebActivity(activity.Activity):
    def __init__(self, handle, browser=None):
        activity.Activity.__init__(self, handle)

        logging.debug('Starting the web activity')

        self.set_title(_('Web Activity'))

        if browser:
            self._browser = browser
        else:
            self._browser = WebView()
        self._browser.connect('notify::title', self._title_changed_cb)

        toolbox = activity.ActivityToolbox(self)

        toolbar = WebToolbar(self._browser)
        toolbox.add_toolbar(_('Browse'), toolbar)
        toolbar.show()

        self.set_toolbox(toolbox)
        toolbox.show()

        self.set_canvas(self._browser)
        self._browser.show()

        if handle.uri:
            url = handle.uri
        else:
            url = _HOMEPAGE

        if url:
            self._browser.load_url(url)

    def _title_changed_cb(self, embed, pspec):
        self.set_title(embed.props.title)

def start():
    if not sugar.browser.startup(env.get_profile_path(), 'gecko'):
        raise "Error when initializising the web activity."

    download_manager = sugar.browser.get_download_manager()
    download_manager.connect('download-started', download_started_cb)
    download_manager.connect('download-completed', download_completed_cb)
    download_manager.connect('download-cancelled', download_started_cb)
    download_manager.connect('download-progress', download_progress_cb)

def stop():
    sugar.browser.shutdown()

def download_started_cb(download_manager, download):
    name = download.get_url().rsplit('/', 1)[1]

    cb_service = clipboardservice.get_instance()
    object_id = cb_service.add_object(name)
    download.set_data('object-id', object_id)
    cb_service.add_object_format(object_id,
                                 download.get_mime_type(),
                                 'file://' + download.get_file_name(),
                                 on_disk = True)

def download_completed_cb(download_manager, download):
    object_id = download.get_data('object-id')
    if not object_id:
        logging.debug("Unknown download object %r" % download)
        return
    cb_service = clipboardservice.get_instance()
    cb_service.set_object_percent(object_id, 100)

def download_cancelled_cb(download_manager, download):
    #FIXME: Needs to update the state of the object to 'download stopped'.
    #FIXME: Will do it when we complete progress on the definition of the
    #FIXME: clipboard API.
    raise "Cancelling downloads still not implemented."

def download_progress_cb(download_manager, download):
    object_id = download.get_data('object-id')
    if not object_id:
        logging.debug("Unknown download object %r" % download)
        return

    # don't send 100% unless it's really done, which we handle
    # from download_completed_cb instead
    percent = download.get_percent()
    if percent < 100:
        cb_service = clipboardservice.get_instance()
        cb_service.set_object_percent(object_id, percent)
