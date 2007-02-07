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

from gettext import gettext as _
import hippo
import logging
import dbus

import _sugar
from sugar.activity.Activity import Activity
from sugar.clipboard import clipboardservice
from sugar import env

from webview import WebView
from webtoolbar import WebToolbar
from linksmodel import LinksModel
from linksview import LinksView
from linkscontroller import LinksController

_HOMEPAGE = 'file:///home/olpc/Library/index.html'

class WebActivity(Activity):
    def __init__(self, browser=None):
        Activity.__init__(self)

        logging.debug('Starting the web activity')

        self.set_title(_('Web Activity'))

        canvas = hippo.Canvas()
        self.add(canvas)
        canvas.show()
        
        vbox = hippo.CanvasBox()
        canvas.set_root(vbox)

        if browser:
            self._browser = browser
        else:
            self._browser = WebView()
        self._browser.connect('notify::title', self._title_changed_cb)

        self._toolbar = WebToolbar(self._browser)
        vbox.append(self._toolbar)

        self._hbox = hippo.CanvasBox(orientation=hippo.ORIENTATION_HORIZONTAL)
        vbox.append(self._hbox, hippo.PACK_EXPAND)

        self._links_model = LinksModel()
        self._links_view = LinksView(self._links_model, self._browser)
        self._hbox.append(self._links_view)
        self._hbox.set_child_visible(self._links_view, False)
            
        self._links_model.connect('link_added', self._link_added_cb)
        self._links_model.connect('link_removed', self._link_removed_cb)

        browser_widget = hippo.CanvasWidget()
        browser_widget.props.widget = self._browser
        self._hbox.append(browser_widget, hippo.PACK_EXPAND)

        self._browser.load_url(_HOMEPAGE)

    def _link_added_cb(self, model, link):
        if self._links_view.get_link_count() > 0:
            self._hbox.set_child_visible(self._links_view, True)

    def _link_removed_cb(self, model, link):
        if self._links_view.get_link_count() == 0:
            self._hbox.set_child_visible(self._links_view, False)

    def _setup_links_controller(self):
        links_controller = LinksController(self._service, self._links_model)
        self._toolbar.set_links_controller(links_controller)

    def join(self, activity_ps):
        Activity.join(self, activity_ps)

        self._setup_links_controller()

        url = self._service.get_published_value('URL')
        if url:
            self._browser.load_url(url)

    def share(self):
        Activity.share(self)

        self._setup_links_controller()

        url = self._browser.get_location()
        if url:
            self._service.set_published_value('URL', url)

    def execute(self, command, args):
        if command == "load-uri":
            self._browser.load_url(args[0])

    def _title_changed_cb(self, embed, pspec):
        self.set_title(embed.props.title)

def start():
    if not _sugar.browser_startup(env.get_profile_path(), 'gecko'):
        raise "Error when initializising the web activity."

    download_manager = _sugar.get_download_manager()
    download_manager.connect('download-started', download_started_cb)
    download_manager.connect('download-completed', download_completed_cb)
    download_manager.connect('download-cancelled', download_started_cb)
    download_manager.connect('download-progress', download_progress_cb)

def stop():
    _sugar.browser_shutdown()

def download_started_cb(download_manager, download):
    name = download.get_url().rsplit('/', 1)[1]
    object_id = download.get_file_name() # The file name passed is already unique.

    cb_service = clipboardservice.get_instance()
    cb_service.add_object(object_id, name)
    cb_service.add_object_format(object_id,
                                 download.get_mime_type(),
                                 download.get_file_name(),
                                 on_disk = True)

def download_completed_cb(download_manager, download):
    cb_service = clipboardservice.get_instance()
    cb_service.set_object_percent(download.get_file_name(), 100)

def download_cancelled_cb(download_manager, download):
    #FIXME: Needs to update the state of the object to 'download stopped'.
    #FIXME: Will do it when we complete progress on the definition of the
    #FIXME: clipboard API.
    raise "Cancelling downloads still not implemented."

def download_progress_cb(download_manager, download):
    cb_service = clipboardservice.get_instance()
    cb_service.set_object_percent(download.get_file_name(), download.get_percent())
