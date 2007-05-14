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
import os
import logging
import time
from gettext import gettext as _
import urlparse

import gtk
import dbus

import sugar.browser
from sugar.activity import activity
from sugar.datastore import datastore
from sugar import profile
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
        activity_toolbar = toolbox.get_activity_toolbar()

        toolbar = WebToolbar(self._browser)
        toolbox.add_toolbar(_('Browse'), toolbar)
        toolbar.show()

        self.set_toolbox(toolbox)
        toolbox.show()

        self.set_canvas(self._browser)
        self._browser.show()

        if handle.uri:
            self._browser.load_url(handle.uri)
        else:
            self._browser.load_url(_HOMEPAGE)

        if not self.jobject['title']:
            self.jobject['title'] = _('Web session')

        # FIXME: this should be done in activity.Activity
        self._browser.connect('realize', self._realize_cb)

    def _realize_cb(self, browser):
        if self.jobject.file_path:
            self.read_file()

    def _title_changed_cb(self, embed, pspec):
        self.set_title(embed.props.title)

    def read_file(self):
        f = open(self.jobject.file_path, 'r')
        try:
            session_data = f.read()
        finally:
            f.close()
        logging.debug('Trying to set session: %s.' % session_data)
        self._browser.set_session(session_data)

    def write_file(self):
        session_data = self._browser.get_session()
        self.jobject['preview'] = self._browser.props.title
        self.jobject['icon'] = 'theme:object-link'
        f = open(self.jobject.file_path, 'w')
        try:
            f.write(session_data)
        finally:
            f.close()
        return f.name

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

def get_download_file_name(download):
    uri = urlparse.urlparse(download.get_url())
    path, file_name = os.path.split(uri[2])
    return file_name

def download_started_cb(download_manager, download):
    jobject = datastore.create()
    jobject['title'] = _('Downloading %s from \n%s.') % \
        (get_download_file_name(download), download.get_url())

    if download.get_mime_type() in ['application/pdf', 'application/x-pdf']:
        jobject['activity'] = 'org.laptop.sugar.Xbook'
        jobject['icon'] = 'theme:object-text'
    else:
        jobject['activity'] = ''
        jobject['icon'] = 'theme:object-link'

    jobject['date'] = str(time.time())
    jobject['keep'] = '0'
    jobject['buddies'] = ''
    jobject['preview'] = ''
    jobject['icon-color'] = profile.get_color().to_string()
    jobject.file_path = ''
    datastore.write(jobject)
    download.set_data('jobject-id', jobject.object_id)

    cb_service = clipboardservice.get_instance()
    object_id = cb_service.add_object(get_download_file_name(download))
    download.set_data('object-id', object_id)
    cb_service.add_object_format(object_id,
                                 download.get_mime_type(),
                                 'file://' + download.get_file_name(),
                                 on_disk = True)

def download_completed_cb(download_manager, download):
    jobject = datastore.get(download.get_data('jobject-id'))
    jobject['title'] = _('File %s downloaded from\n%s.') % \
        (get_download_file_name(download), download.get_url())
    jobject.file_path = download.get_file_name()
    datastore.write(jobject)

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
    object_id = download.get_data('jobject-id')
    if not object_id:
        logging.debug("Unknown download object %r" % download)
        return

    # don't send 100% unless it's really done, which we handle
    # from download_completed_cb instead
    percent = download.get_percent()
    if percent < 100:
        """
        jobject = datastore.get(download.get_data('jobject-id'))
        jobject['title'] = _('Downloading %s from\n%s.\nProgress %i%%.') % \
            (get_download_file_name(download), download.get_url(), percent)
        datastore.write(jobject)
        """

        cb_service = clipboardservice.get_instance()
        cb_service.set_object_percent(download.get_data('object-id'), percent)
