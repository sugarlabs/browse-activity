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
from sugar.graphics.canvasicon import CanvasIcon
from sugar.graphics.popupcontext import PopupContext
from sugar.graphics.iconcolor import IconColor

class LinkIcon(CanvasIcon):
    def __init__(self, link):
        color = IconColor(link.buddy.get_color())
        
        path = os.path.join(env.get_bundle_path(), 'activity')
        icon_name = os.path.join(path, 'activity-web.svg')
        CanvasIcon.__init__(self, color=color, icon_name=icon_name)

        self._link = link

    def get_popup(self):
        menu = Menu(self._link.title)
        return menu

class LinksView(Toolbar):
    def __init__(self, model, browser, **kwargs):
        Toolbar.__init__(self, orientation=hippo.ORIENTATION_VERTICAL)

        self._icons = {}
        self._browser = browser

        for link in model:
            self._add_link(link)

        model.connect('link_added', self._link_added_cb)
        model.connect('link_removed', self._link_removed_cb)

    def _add_link(self, link):
        icon = LinkIcon(link)
        icon.connect('activated', self._link_activated_cb, link)
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
