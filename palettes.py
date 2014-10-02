# Copyright (C) 2008, One Laptop Per Child
# Copyright (C) 2009, Tomeu Vizoso, Simon Schampijer
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
from gi.repository import WebKit

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
        self._recognized_long_press_event = False
        self._browser.connect('button-press-event', self.__button_press_cb)
        self._browser.connect('button-release-event', self.__button_release_cb)
        self._browser.connect('realize', self.__browser_realize_cb)
        self.attach(self._browser)

    def get_default_position(self):
        return self.AT_CURSOR

    def __long_pressed_cb(self, controller, x, y):
        self._recognized_long_press_event = True

        event = Gdk.EventButton()
        event.type = Gdk.EventType._3BUTTON_PRESS
        gdk_window = self._browser.get_window()
        event.window = gdk_window
        event.time = Gtk.get_current_event_time()
        event.x = x
        event.y = y
        x_root, y_root = gdk_window.get_root_coords(x, y)
        event.x_root = x_root
        event.y_root = y_root

        self._handle_event(event)

        return True

    def __button_release_cb(self, browser, event):
        if self._recognized_long_press_event:
            self._recognized_long_press_event = False
            return True
        else:
            return False

    def __browser_realize_cb(self, browser):
        x11_window = browser.get_window()
        x11_window.set_events(x11_window.get_events() |
                              Gdk.EventMask.POINTER_MOTION_MASK |
                              Gdk.EventMask.TOUCH_MASK)

        lp = SugarGestures.LongPressController()
        lp.connect('pressed', self.__long_pressed_cb)
        lp.attach(browser, SugarGestures.EventControllerFlags.NONE)

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

    def __button_press_cb(self, browser, event):
        if event.button != 3:
            return False
        self._handle_event(event)
        return True

    def _handle_event(self, event):
        hit_test = self._browser.get_hit_test_result(event)
        hit_context = hit_test.props.context
        # FIXME #4638
        logging.error("TEST %r", hit_context)
        hit_info = {
            'is link': hit_context & WebKit.HitTestResultContext.LINK,
            'is image': hit_context & WebKit.HitTestResultContext.IMAGE,
            'is selection': (hit_context &
                             WebKit.HitTestResultContext.SELECTION),
            }

        title = None
        url = None

        if hit_info['is link']:
            if isinstance(hit_test.props.inner_node,
                          WebKit.DOMHTMLImageElement):
                title = hit_test.props.inner_node.get_title()
            elif isinstance(hit_test.props.inner_node, WebKit.DOMNode):
                title = hit_test.props.inner_node.get_text_content()
            url = hit_test.props.link_uri

        if hit_info['is image']:
            title = hit_test.props.inner_node.get_title()
            url = hit_test.props.image_uri

        if hit_info['is selection']:
            # TODO: find a way to get the selected text so we can use
            # it as the title of the Palette.
            # The function webkit_web_view_get_selected_text was removed
            # https://bugs.webkit.org/show_bug.cgi?id=62512
            if isinstance(hit_test.props.inner_node, WebKit.DOMNode):
                title = hit_test.props.inner_node.get_text_content()

        if (hit_info['is link'] or hit_info['is image'] or
                hit_info['is selection']):
            self.palette = BrowsePalette(self._browser, title, url, hit_info)
            self.notify_right_click()


class BrowsePalette(Palette):
    def __init__(self, browser, title, url, hit_info):
        Palette.__init__(self)

        self._browser = browser
        self._url = url

        # FIXME: this sometimes fails for links because Gtk tries
        # to parse it as markup text and some URLs has
        # "?template=gallery&page=gallery" for example
        if title not in (None, ''):
            self.props.primary_text = title
            if url is not None:
                self.props.secondary_text = url
        else:
            if url is not None:
                self.props.primary_text = url

        menu_box = Gtk.VBox()
        self.set_content(menu_box)
        menu_box.show()
        self._content.set_border_width(1)

        first_section_added = False
        if hit_info['is link']:
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
            if not hit_info['is image']:
                menu_item = PaletteMenuItem(_('Keep link'), 'document-save')
                menu_item.icon.props.xo_color = profile.get_color()
                menu_item.connect('activate', self.__download_activate_cb)
                menu_box.pack_start(menu_item, False, False, 0)
                menu_item.show()

            menu_item = PaletteMenuItem(_('Copy link'), 'edit-copy')
            menu_item.icon.props.xo_color = profile.get_color()
            menu_item.connect('activate', self.__copy_link_activate_cb)
            menu_box.pack_start(menu_item, False, False, 0)
            menu_item.show()

        if hit_info['is image']:
            if not first_section_added:
                first_section_added = True
            else:
                separator = PaletteMenuItemSeparator()
                menu_box.pack_start(separator, False, False, 0)
                separator.show()

            menu_item = PaletteMenuItem(_('Copy image'), 'edit-copy')
            menu_item.icon.props.xo_color = profile.get_color()
            menu_item.connect('activate', self.__copy_image_activate_cb)
            menu_box.pack_start(menu_item, False, False, 0)
            menu_item.show()

            menu_item = PaletteMenuItem(_('Keep image'), 'document-save')
            menu_item.icon.props.xo_color = profile.get_color()
            menu_item.connect('activate', self.__download_activate_cb)
            menu_box.pack_start(menu_item, False, False, 0)
            menu_item.show()

        if hit_info['is selection']:
            if not first_section_added:
                first_section_added = True
            else:
                separator = PaletteMenuItemSeparator()
                menu_box.pack_start(separator, False, False, 0)
                separator.show()

            menu_item = PaletteMenuItem(_('Copy text'), 'edit-copy')
            menu_item.icon.props.xo_color = profile.get_color()
            menu_item.connect('activate', self.__copy_activate_cb)
            menu_box.pack_start(menu_item, False, False, 0)
            menu_item.show()

    def __follow_activate_cb(self, menu_item, new_tab=False):
        if new_tab:
            self._browser.open_new_tab(self._url)
        else:
            self._browser.load_uri(self._url)
            self._browser.grab_focus()

    def __copy_link_activate_cb(self, menu_item):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(self._url, -1)

    def __download_activate_cb(self, menu_item):
        nr = WebKit.NetworkRequest()
        nr.set_uri(self._url)
        download = WebKit.Download(network_request=nr)
        self._browser.emit('download-requested', download)

    def __copy_image_activate_cb(self, menu_item):
        # Download the image
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        data = urllib2.urlopen(self._url).read()
        temp_file.write(data)
        temp_file.close()

        # Copy it inside the clipboard
        image = Gtk.Image.new_from_file(temp_file.name)
        os.unlink(temp_file.name)
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_image(image.get_pixbuf())

    def __copy_activate_cb(self, menu_item):
        self._browser.copy_clipboard()
