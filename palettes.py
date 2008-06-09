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

import os
import tempfile
import urlparse
from gettext import gettext as _

import gtk
from xpcom import components
from xpcom.components import interfaces

from sugar.graphics.palette import Palette, Invoker
from sugar.graphics.menuitem import MenuItem
from sugar.graphics.icon import Icon
from sugar import profile
from sugar.activity import activity

class ContentInvoker(Invoker):
    _com_interfaces_ = interfaces.nsIDOMEventListener

    def __init__(self, browser):
        Invoker.__init__(self)
        self._position_hint = self.AT_CURSOR
        self._browser = browser

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
                title = None

            self.palette = LinkPalette(self._browser, title, target.href)
            self.notify_right_click()
        elif target.tagName.lower() == 'img':
            if target.title:
                title = target.title
            elif target.title:
                title = target.alt
            elif target.name:
                title = target.name
            else:
                title = os.path.basename(urlparse.urlparse(target.src).path)

            self.palette = ImagePalette(title, target.src)
            self.notify_right_click()

class LinkPalette(Palette):
    def __init__(self, browser, title, url):
        Palette.__init__(self)

        self._url = url
        self._browser = browser

        if title is not None:
            self.props.primary_text = title
            self.props.secondary_text = url
        else:
            self.props.primary_text = url

        menu_item = MenuItem(_('Follow link'), 'edit-copy')
        menu_item.connect('activate', self.__follow_activate_cb)
        self.menu.append(menu_item)
        menu_item.show()

        menu_item = MenuItem(_('Copy'))
        icon = Icon(icon_name='edit-copy', xo_color=profile.get_color(),
                    icon_size=gtk.ICON_SIZE_MENU)
        menu_item.set_image(icon)
        menu_item.connect('activate', self.__copy_activate_cb)
        self.menu.append(menu_item)
        menu_item.show()

    def __follow_activate_cb(self, menu_item):
        self._browser.load_uri(self._url)
        self._browser.grab_focus()

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

class ImagePalette(Palette):
    def __init__(self, title, url):
        Palette.__init__(self)

        self._url = url
        self._temp_file = None

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
        clipboard.set_with_data([('text/uri-list', 0, 0)],
                                self.__clipboard_get_func_cb,
                                self.__clipboard_clear_func_cb)

    def __clipboard_get_func_cb(self, clipboard, selection_data, info, data):
        file_name = os.path.basename(urlparse.urlparse(self._url).path)
        if '.' in file_name:
            base_name, extension = file_name.split('.')
            extension = '.' + extension
        else:
            base_name = file_name
            extension = ''

        temp_path = os.path.join(activity.get_activity_root(), 'instance')
        fd, self._temp_file = tempfile.mkstemp(dir=temp_path, prefix=base_name,
                                               suffix=extension)
        os.close(fd)
        os.chmod(self._temp_file, 0664)

        cls = components.classes['@mozilla.org/network/io-service;1']
        io_service = cls.getService(interfaces.nsIIOService)
        uri = io_service.newURI(self._url, None, None)

        cls = components.classes['@mozilla.org/file/local;1']
        target_file = cls.createInstance(interfaces.nsILocalFile)
        target_file.initWithPath(self._temp_file)
		
        cls = components.classes[ \
                '@mozilla.org/embedding/browser/nsWebBrowserPersist;1']
        persist = cls.createInstance(interfaces.nsIWebBrowserPersist)
        persist.persistFlags = 1 # PERSIST_FLAGS_FROM_CACHE
        persist.saveURI(uri, None, None, None, None, target_file)

        selection_data.set_uris(['file://' + self._temp_file])

    def __clipboard_clear_func_cb(self, clipboard, data):
        if os.path.exists(self._temp_file):
            os.remove(self._temp_file)

