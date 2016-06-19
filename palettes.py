# Copyright (C) 2008, One Laptop Per Child
# Copyright (C) 2009, Tomeu Vizoso, Simon Schampijer
# Copyright (C) 2015, Sam Parkinson
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
import os
import tempfile
import urllib2

from gettext import gettext as _

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import SugarGestures

from sugar3.graphics.palette import Palette, Invoker
from sugar3.graphics.palettemenu import PaletteMenuItem
from sugar3.graphics.palettemenu import PaletteMenuItemSeparator
from sugar3 import profile


class ContentInvoker(Invoker):
    def __init__(self, browser):
        Invoker.__init__(self)
        self._position_hint = self.AT_CURSOR
        self._browser = browser
        self._browser.connect('context-menu', self.__context_menu_cb)
        self._browser.connect('realize', self.__browser_realize_cb)

    def __browser_realize_cb(self, browser):
        x11_window = browser.get_window()
        x11_window.set_events(x11_window.get_events() |
                              Gdk.EventMask.POINTER_MOTION_MASK |
                              Gdk.EventMask.TOUCH_MASK)

        lp = SugarGestures.LongPressController()
        lp.connect('pressed', self.__long_pressed_cb)
        lp.attach(browser, SugarGestures.EventControllerFlags.NONE)

    def __long_pressed_cb(self, controller, x, y):
        # We can't force a context menu, but we can fake a right mouse click
        event = Gdk.Event()
        event.type = Gdk.EventType.BUTTON_PRESS

        b = event.button
        b.type = Gdk.EventType.BUTTON_PRESS
        b.window = self._browser.get_window()
        b.time = Gtk.get_current_event_time()
        b.button = 3  # Right
        b.x = x
        b.y = y
        b.x_root, b.y_root = self._browser.get_window().get_root_coords(x, y)

        Gtk.main_do_event(event)
        return True

    def get_default_position(self):
        return self.AT_CURSOR

    def get_rect(self):
        allocation = self._browser.get_allocation()
        window = self._browser.get_window()
        if window is not None:
            res, x, y = window.get_origin()
        else:
            logging.warning(
                "Trying to position palette with invoker that's not realized.")
            x = 0
            y = 0

        x += allocation.x
        y += allocation.y

        width = allocation.width
        height = allocation.height

        rect = Gdk.Rectangle()
        rect.x = x
        rect.y = y
        rect.width = width
        rect.height = height
        return rect

    def get_toplevel(self):
        return None

    def __context_menu_cb(self, webview, context_menu, event, hit_test):
        self.palette = BrowsePalette(self._browser, hit_test)
        self.notify_right_click()

        # Don't show the default menu
        return True


class BrowsePalette(Palette):
    def __init__(self, browser, hit):
        Palette.__init__(self)
        self._browser = browser
        self._hit = hit

        # Have to set document.title,
        # see http://comments.gmane.org/gmane.os.opendarwin.webkit.gtk/1981
        self._browser.run_javascript('''
            document.SugarBrowseOldTitle = document.title;
            document.title = (function () {
                if (window.getSelection) {
                    return window.getSelection().toString();
                } else if (document.selection &&
                           document.selection.type != "Control") {
                    return document.selection.createRange().text;
                }
                return '';
            })()''', None, self.__after_get_text_cb, None)

    def __after_get_text_cb(self, browser, async_result, user_data):
        self._all_text = self._browser.props.title
        self._browser.run_javascript(
            'document.title = document.SugarBrowseOldTitle')
        self._link_text = self._hit.props.link_label \
            or self._hit.props.link_title

        self._title = self._link_text or self._all_text
        self._url = self._hit.props.link_uri or self._hit.props.image_uri \
            or self._hit.props.media_uri
        self._image_url = self._hit.props.image_uri \
            or self._hit.props.media_uri

        if self._title not in (None, ''):
            self.props.primary_text = GLib.markup_escape_text(self._title)
            if self._url is not None:
                self.props.secondary_text = GLib.markup_escape_text(self._url)
        else:
            if self._url is not None:
                self.props.primary_text = GLib.markup_escape_text(self._url)

        if not self._all_text and not self._url:
            self.popdown(immediate=True)
            return  # Nothing to see here!

        menu_box = Gtk.VBox()
        self.set_content(menu_box)
        menu_box.show()
        self._content.set_border_width(1)

        first_section_added = False
        if self._hit.context_is_link():
            first_section_added = True

            menu_item = PaletteMenuItem(_('Follow link'), 'browse-follow-link')
            menu_item.connect('activate', self.__follow_activate_cb)
            menu_box.pack_start(menu_item, False, False, 0)
            menu_item.show()

            menu_item = PaletteMenuItem(_('Follow link in new tab'),
                                        'browse-follow-link-new-tab')
            menu_item.connect('activate', self.__follow_activate_cb, True)
            menu_box.pack_start(menu_item, False, False, 0)
            menu_item.show()

            # Add "keep link" only if it is not an image.  "Keep
            # image" will be shown in that case.
            if not self._hit.context_is_image():
                menu_item = PaletteMenuItem(_('Keep link'), 'document-save')
                menu_item.icon.props.xo_color = profile.get_color()
                menu_item.connect('activate', self.__download_activate_cb)
                menu_box.pack_start(menu_item, False, False, 0)
                menu_item.show()

            menu_item = PaletteMenuItem(_('Copy link'), 'edit-copy')
            menu_item.icon.props.xo_color = profile.get_color()
            menu_item.connect('activate', self.__copy_cb, self._url)
            menu_box.pack_start(menu_item, False, False, 0)
            menu_item.show()

            if self._link_text:
                menu_item = PaletteMenuItem(_('Copy link text'), 'edit-copy')
                menu_item.icon.props.xo_color = profile.get_color()
                menu_item.connect('activate', self.__copy_cb, self._link_text)
                menu_box.pack_start(menu_item, False, False, 0)
                menu_item.show()

        if self._hit.context_is_image():
            if not first_section_added:
                first_section_added = True
            else:
                separator = PaletteMenuItemSeparator()
                menu_box.pack_start(separator, False, False, 0)
                separator.show()

            # FIXME: Copy image is broken
            menu_item = PaletteMenuItem(_('Copy image'), 'edit-copy')
            menu_item.icon.props.xo_color = profile.get_color()
            menu_item.connect('activate', self.__copy_image_activate_cb)
            menu_box.pack_start(menu_item, False, False, 0)
            menu_item.show()

            menu_item = PaletteMenuItem(_('Keep image'), 'document-save')
            menu_item.icon.props.xo_color = profile.get_color()
            menu_item.connect('activate', self.__download_activate_cb,
                              self._image_url)
            menu_box.pack_start(menu_item, False, False, 0)
            menu_item.show()

        if self._hit.context_is_selection() and self._all_text:
            if not first_section_added:
                first_section_added = True
            else:
                separator = PaletteMenuItemSeparator()
                menu_box.pack_start(separator, False, False, 0)
                separator.show()

            menu_item = PaletteMenuItem(_('Copy text'), 'edit-copy')
            menu_item.icon.props.xo_color = profile.get_color()
            menu_item.connect('activate', self.__copy_cb, self._all_text)
            menu_box.pack_start(menu_item, False, False, 0)
            menu_item.show()

    def __follow_activate_cb(self, menu_item, new_tab=False):
        if new_tab:
            self._browser.open_new_tab(self._url)
        else:
            self._browser.load_uri(self._url)
            self._browser.grab_focus()

    def __download_activate_cb(self, menu_item, url=None):
        self._browser.download_uri(url or self._url)

    def __copy_image_activate_cb(self, menu_item):
        # Download the image
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        data = urllib2.urlopen(self._image_url).read()
        temp_file.write(data)
        temp_file.close()

        # Copy it inside the clipboard
        image = Gtk.Image.new_from_file(temp_file.name)
        os.unlink(temp_file.name)
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_image(image.get_pixbuf())

    def __copy_cb(self, menu_item, text):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(text, -1)
