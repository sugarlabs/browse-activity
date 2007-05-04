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

import gtk
import dbus

import sugar.browser
from sugar.activity import activity
from sugar.datastore import datastore
from sugar.datastore.datastore import WebSession
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

        self._journal_handle = None
        self._last_saved_session = None

        self.set_title(_('Web Activity'))

        if browser:
            self._browser = browser
        else:
            self._browser = WebView()
        self._browser.connect('notify::title', self._title_changed_cb)

        toolbox = activity.ActivityToolbox(self)
        activity_toolbar = toolbox.get_activity_toolbar()
        activity_toolbar.close.connect('clicked', self._close_clicked_cb)

        toolbar = WebToolbar(self._browser)
        toolbox.add_toolbar(_('Browse'), toolbar)
        toolbar.show()

        self.set_toolbox(toolbox)
        toolbox.show()

        self.set_canvas(self._browser)
        self._browser.show()

        if handle.object_id:
            self._journal_handle = handle.object_id
            # Will set the session in the realize callback.
            self._browser.connect('realize', self._realize_cb)
        elif handle.uri:
            self._browser.load_url(handle.uri)
        else:
            self._browser.load_url(_HOMEPAGE)

        self.connect('focus-out-event', self._focus_out_event_cb)

    def _title_changed_cb(self, embed, pspec):
        self.set_title(embed.props.title)

    def _realize_cb(self, browser):
        if self._journal_handle:
            obj = datastore.read(self._journal_handle)
            f = open(obj.get_file_path(), 'r')
            try:
                session_data = f.read()
            finally:
                f.close()
            logging.debug('Trying to set session: %s.' % session_data)
            self._browser.set_session(session_data)

    def _focus_out_event_cb(self, widget, event):
        self._autosave()

    def _close_clicked_cb(self, widget):
        self._autosave()
        return False

    def _autosave(self):
        session_data = self._browser.get_session()
        if not self._journal_handle:
            home_dir = os.path.expanduser('~')
            journal_dir = os.path.join(home_dir, "Journal")
            web_session = WebSession({
                'preview'      : _('No preview'),
                'date'         : str(time.time()),
                'title'        : _('Web session'),
                'icon'         : 'theme:object-link',
                'keep'         : '0',
                'buddies'      : str([ { 'name' : profile.get_nick_name(),
                                        'color': profile.get_color().to_string() }]),
                'icon-color'   : profile.get_color().to_string()})
            f = open(os.path.join(journal_dir, '%i.txt' % time.time()), 'w')
            try:
                f.write(session_data)
            finally:
                f.close()
            web_session.set_file_path(f.name)
            self._journal_handle = datastore.write(web_session)
        elif session_data != self._last_saved_session:
            web_session = datastore.read(self._journal_handle)
            metadata = web_session.get_metadata()
            metadata['date'] = str(time.time())
            f = open(web_session.get_file_path(), 'w')
            try:
                f.write(session_data)
            finally:
                f.close()
            datastore.write(web_session)

        self._last_saved_session = session_data

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
