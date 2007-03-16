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

import hippo
import dbus
import gtk

import _sugar
from sugar.activity import activity
from sugar.graphics.filechooser import FileChooserDialog
from sugar.clipboard import clipboardservice
from sugar import env

from webview import WebView
from webtoolbar import WebToolbar
from linksmodel import LinksModel
from linksview import LinksView
from linkscontroller import LinksController

_HOMEPAGE = 'file:///home/olpc/Library/index.html'

class WebActivity(activity.Activity):
    def __init__(self, handle, browser=None):
        activity.Activity.__init__(self, handle)

        logging.debug('Starting the web activity')

        self.set_title(_('Web Activity'))

        vbox = hippo.CanvasBox()
        self.set_root(vbox)

        if browser:
            self._browser = browser
        else:
            self._browser = WebView()
        self._browser.connect('notify::title', self._title_changed_cb)
        self._browser.connect('mouse-click', self._dom_click_cb)

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

        self._service = handle.get_presence_service() 
        if self._service:
            self._setup_links_controller()
            url = self._service.get_published_value('URL')
        elif handle.uri:
            url = handle.uri
        else:
            url = _HOMEPAGE

        if url:
            self._browser.load_url(url)

    def _link_added_cb(self, model, link):
        if self._links_view.get_link_count() > 0:
            self._hbox.set_child_visible(self._links_view, True)

    def _link_removed_cb(self, model, link):
        if self._links_view.get_link_count() == 0:
            self._hbox.set_child_visible(self._links_view, False)

    def _setup_links_controller(self):
        links_controller = LinksController(self._service, self._links_model)
        self._toolbar.set_links_controller(links_controller)

    def share(self):
        activity.Activity.share(self)

        self._setup_links_controller()

        url = self._browser.get_location()
        if url:
            self._service.set_published_value('URL', url)

    def _title_changed_cb(self, embed, pspec):
        self.set_title(embed.props.title)

    def _get_menu(self, image_uri):
        menu = gtk.Menu()
        menu_item = gtk.ImageMenuItem(gtk.STOCK_SAVE)
        menu_item.connect('activate', self._save_menu_activate_cb, image_uri)
        menu.add(menu_item)
        menu.show_all()
        return menu

    def _dom_click_cb(self, browser, event):
        if event.image_uri:
            self._get_menu(event.image_uri).popup(None, None, None, 1, 0)

    def _save_menu_activate_cb(self, menu_item, image_uri):
        chooser = FileChooserDialog(title=None,
                                    parent=self,
                                    action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                    buttons=(gtk.STOCK_CANCEL,
                                             gtk.RESPONSE_CANCEL,
                                             gtk.STOCK_SAVE,
                                             gtk.RESPONSE_OK))
        chooser.set_default_response(gtk.RESPONSE_OK)
        chooser.set_current_folder(os.path.expanduser('~'))
        response = chooser.run()

        if response == gtk.RESPONSE_OK:
            self.save_uri(image_uri, chooser.get_filename())

        chooser.destroy()

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

    cb_service = clipboardservice.get_instance()
    object_id = cb_service.add_object(name)
    download.set_data('object-id', object_id)
    cb_service.add_object_format(object_id,
                                 download.get_mime_type(),
                                 download.get_file_name(),
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
