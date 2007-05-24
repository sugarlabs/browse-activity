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
from gettext import gettext as _

import gtk
import dbus

from sugar.activity import activity
from sugar import env

import hulahop
hulahop.startup(os.path.join(env.get_profile_path(), 'gecko'))

from browser import Browser
from webtoolbar import WebToolbar
import downloadmanager

_HOMEPAGE = 'http://www.google.com'

class WebActivity(activity.Activity):
    def __init__(self, handle, browser=None):
        activity.Activity.__init__(self, handle)

        logging.debug('Starting the web activity')

        self.set_title(_('Web Activity'))

        if browser:
            self._browser = browser
        else:
            self._browser = Browser()

        downloadmanager.init(self._browser)

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
            self._browser.load_uri(handle.uri)
        else:
            self._browser.load_uri(_HOMEPAGE)

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
        if self._browser.props.title:
            self.jobject['preview'] = self._browser.props.title
        else:
            self.jobject['preview'] = ''
        self.jobject['icon'] = 'theme:object-link'
        f = open(self.jobject.file_path, 'w')
        try:
            f.write(session_data)
        finally:
            f.close()
        return f.name

