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

import hippo

from sugar import env
from sugar.graphics.toolbar import Toolbar
from sugar.graphics.menu import Menu
from sugar.graphics.menushell import MenuShell
from sugar.graphics.menuicon import MenuIcon
from sugar.graphics.iconcolor import IconColor
from sugar.graphics import style

class LinkIcon(MenuIcon):
    def __init__(self, menu_shell, link):
        color = IconColor(link.buddy.get_color())
        
        path = os.path.join(env.get_bundle_path(), 'activity')
        icon_name = os.path.join(path, 'activity-web.svg')
        MenuIcon.__init__(self, menu_shell, color=color,
                          icon_name=icon_name)

        self._link = link

    def create_menu(self):
        menu = Menu(self._link.title)
        return menu

class LinksView(Toolbar):
    def __init__(self, model, browser, **kwargs):
        Toolbar.__init__(self, orientation=hippo.ORIENTATION_VERTICAL)

        self._icons = {}
        self._browser = browser
        self._menu_shell = MenuShell(self)

        for link in model:
            self._add_link(link)

        model.connect('link_added', self._link_added_cb)
        model.connect('link_removed', self._link_removed_cb)

    def _add_link(self, link):
        icon = LinkIcon(self._menu_shell, link)
        icon.connect('activated', self._link_activated_cb, link)
        style.apply_stylesheet(icon, 'links.Icon')
        self.append(icon)

        self._icons[link] = icon

    def _remove_link(self, link):
        icon = self._icons[link]
        self.remove(icon)

        del self._icons[link]

    def _link_added_cb(self, model, link):
        self._add_link(link)

    def _link_removed_cb(self, model, link):
        self._remove_link(link)

    def _link_activated_cb(self, link_item, link):
        self._browser.load_url(link.url)

    def get_link_count(self):
        return len(self._icons)
