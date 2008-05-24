# Copyright (C) 2008, One Laptop Per Child
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
import xpcom
from xpcom.nsError import *
from xpcom import components
from xpcom.components import interfaces

from sugar.graphics.palette import Palette, Invoker
from sugar.graphics.menuitem import MenuItem
from sugar.graphics.icon import Icon
from sugar import profile

class ContentInvoker(Invoker):
    _com_interfaces_ = interfaces.nsIDOMEventListener

    def __init__(self):
        Invoker.__init__(self)
        self._position_hint = self.AT_CURSOR

    def get_default_position(self):
        return self.AT_CURSOR

    def get_rect(self):
        return gtk.gdk.Rectangle()

    def get_toplevel(self):
        return None

    def handleEvent(self, event):
        if event.button != 2:
            return

        target = event.target
        if target.tagName.lower() == 'a':

            if target.firstChild:
                title = target.firstChild.nodeValue
            else:
                title = ''

            self.palette = LinkPalette(title, target.href)
            self.notify_right_click()

class LinkPalette(Palette):
    def __init__(self, title, url):
        Palette.__init__(self)

        self._url = url

        self.props.primary_text = title
        self.props.secondary_text = url

        menu_item = MenuItem(_('Copy'))
        icon = Icon(icon_name='edit-copy', xo_color=profile.get_color(),
                    icon_size=gtk.ICON_SIZE_MENU)
        menu_item.set_image(icon)
        menu_item.connect('activate', self.__copy_activate_cb)
        self.menu.append(menu_item)
        menu_item.show()

    def __copy_activate_cb(self, menu_item):
        clipboard = gtk.Clipboard()
        targets = gtk.target_list_add_uri_targets()
        targets = gtk.target_list_add_text_targets(targets)
        targets.append(('text/x-moz-url', 0, 0))

        clipboard.set_with_data(targets,
                                self.__clipboard_get_func_cb,
                                self.__clipboard_clear_func_cb)

    def __clipboard_get_func_cb(self, clipboard, selection_data, info, data):
        uri_targets = \
            [target[0] for target in gtk.target_list_add_uri_targets()]
        text_targets = \
            [target[0] for target in gtk.target_list_add_text_targets()]

        if selection_data.target in uri_targets:
            selection_data.set_uris([self._url])
        elif selection_data.target in text_targets:
            selection_data.set_text(self._url)
        elif selection_data.target == 'text/x-moz-url':
            selection_data.set('text/x-moz-url', 8, self._url)

    def __clipboard_clear_func_cb(self, clipboard, data):
        pass

