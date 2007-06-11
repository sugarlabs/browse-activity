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
import promptservice
import securitydialogs

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
        elif not self._jobject.file_path and not browser:
            # TODO: we need this hack until we extend the activity API for
            # opening URIs and default docs.
            self._browser.load_uri(_HOMEPAGE)

    def _title_changed_cb(self, embed, pspec):
        self.set_title(embed.props.title)

    def read_file(self, file_path):
        f = open(file_path, 'r')
        try:
            session_data = f.read()
        finally:
            f.close()
        logging.debug('Trying to set session: %s.' % session_data)
        self._browser.set_session(session_data)

    def write_file(self, file_path):
        session_data = self._browser.get_session()
        if self._browser.props.title:
            self.metadata['preview'] = self._browser.props.title
        else:
            self.metadata['preview'] = ''
        self.metadata['icon'] = 'theme:object-link'
        f = open(file_path, 'w')
        try:
            f.write(session_data)
        finally:
            f.close()

