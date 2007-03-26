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

import gobject
import gtk
import logging
from gettext import gettext as _

from sugar.graphics.filechooser import FileChooserDialog
from _sugar import Browser
from _sugar import PushScroller

class _PopupCreator(gobject.GObject):
    __gsignals__ = {
        'popup-created':  (gobject.SIGNAL_RUN_FIRST,
                           gobject.TYPE_NONE, ([])),
    }

    def __init__(self, parent_window):
        gobject.GObject.__init__(self)

        logging.debug('Creating the popup widget')

        self._sized_popup = False
        self._parent_window = parent_window

        self._dialog = gtk.Window()
        self._dialog.set_resizable(True)

        self._dialog.realize()
        self._dialog.window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)

        self._embed = WebView()
        self._size_to_sid = self._embed.connect('size_to', self._size_to_cb)
        self._vis_sid = self._embed.connect('visibility', self._visibility_cb)

        self._dialog.add(self._embed)

    def _size_to_cb(self, embed, width, height):
        logging.debug('Resize the popup to %d %d' % (width, height))
        self._sized_popup = True
        self._dialog.resize(width, height)

    def _visibility_cb(self, embed, visible):
        if visible:
            if self._sized_popup:
                logging.debug('Show the popup')
                self._embed.show()
                self._dialog.set_transient_for(self._parent_window)
                self._dialog.show()
            else:
                logging.debug('Open a new activity for the popup')
                self._dialog.remove(self._embed)

                # FIXME We need a better way to handle this.
                # It seem like a pretty special case though, I doubt
                # other activities will need something similar.
                from webactivity import WebActivity
                from sugar.activity import activityfactory
                from sugar.activity.activityhandle import ActivityHandle
                handle = ActivityHandle(activityfactory.create_activity_id())
                activity = WebActivity(handle, self._embed)
                activity.show()

            self._embed.disconnect(self._size_to_sid)
            self._embed.disconnect(self._vis_sid)

            self.emit('popup-created')

    def get_embed(self):
        return self._embed

class _ImageMenu(gtk.Menu):
    def __init__(self, browser, event):
        gtk.Menu.__init__(self)

        self._browser = browser
        self._image_uri = event.image_uri
        self._image_name = event.image_name

        menu_item = gtk.ImageMenuItem(gtk.STOCK_SAVE)
        menu_item.connect('activate', self._save_activate_cb)
        self.add(menu_item)
        menu_item.show()

    def _save_activate_cb(self, menu_item):
        chooser = FileChooserDialog(title=None,
                                    parent=self._browser.get_toplevel(),
                                    action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                    buttons=(gtk.STOCK_CANCEL,
                                             gtk.RESPONSE_CANCEL,
                                             gtk.STOCK_SAVE,
                                             gtk.RESPONSE_OK))
        chooser.set_default_response(gtk.RESPONSE_OK)
        chooser.set_current_folder(os.path.expanduser('~'))
        if self._image_name:
            chooser.set_current_name(self._image_name)

        file_filter = gtk.FileFilter()
        file_filter.set_name(_("Images"))
        file_filter.add_mime_type("image/png")
        file_filter.add_mime_type("image/jpeg")
        file_filter.add_mime_type("image/gif")
        chooser.add_filter(file_filter)

        file_filter = gtk.FileFilter()
        file_filter.set_name(_("All files"))
        file_filter.add_pattern("*")
        chooser.add_filter(file_filter)
        response = chooser.run()

        if response == gtk.RESPONSE_OK:
            self._browser.save_uri(self._image_uri, chooser.get_filename())

        chooser.destroy()

class WebView(Browser):
    __gtype_name__ = "SugarWebBrowser"

    def __init__(self):
        Browser.__init__(self)
        self._popup_creators = []

        self.connect('mouse-click', self._dom_click_cb)

    def _dom_click_cb(self, browser, event):
        if event.button == 3 and event.image_uri:
            menu = _ImageMenu(browser, event)
            menu.popup(None, None, None, 1, 0)

    def do_create_window(self):
        popup_creator = _PopupCreator(self.get_toplevel())
        popup_creator.connect('popup-created', self._popup_created_cb)

        self._popup_creators.append(popup_creator)

        return popup_creator.get_embed()

    def _popup_created_cb(self, creator):
        self._popup_creators.remove(creator)
