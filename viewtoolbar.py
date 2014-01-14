# Copyright (C) 2007, One Laptop Per Child
# Copyright (C) 2009, Tomeu Vizoso
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

from gi.repository import Gtk
from gi.repository import GObject

from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics.toggletoolbutton import ToggleToolButton

from browser import Browser
from browser import ZOOM_ORIGINAL


class ViewToolbar(Gtk.Toolbar):
    def __init__(self, activity):
        GObject.GObject.__init__(self)

        self._browser = None

        self._activity = activity

        self.zoomout = ToolButton('zoom-out')
        self.zoomout.set_tooltip(_('Zoom out'))
        self.zoomout.connect('clicked', self.__zoomout_clicked_cb)
        self.insert(self.zoomout, -1)
        self.zoomout.show()

        self.zoomin = ToolButton('zoom-in')
        self.zoomin.set_tooltip(_('Zoom in'))
        self.zoomin.connect('clicked', self.__zoomin_clicked_cb)
        self.insert(self.zoomin, -1)
        self.zoomin.show()

        self.zoom_original = ToolButton('zoom-original')
        self.zoom_original.set_tooltip(_('Actual size'))
        self.zoom_original.connect('clicked', self.__zoom_original_clicked_cb)
        self.insert(self.zoom_original, -1)
        self.zoom_original.show()

        self.separator = Gtk.SeparatorToolItem()
        self.separator.set_draw(True)
        self.insert(self.separator, -1)
        self.separator.show()

        self.fullscreen = ToolButton('view-fullscreen')
        self.fullscreen.set_tooltip(_('Fullscreen'))
        self.fullscreen.connect('clicked', self.__fullscreen_clicked_cb)
        self.insert(self.fullscreen, -1)
        self.fullscreen.show()

        self.traybutton = ToggleToolButton('tray-show')
        self.traybutton.set_icon_name('tray-favourite')
        self.traybutton.connect('toggled', self.__tray_toggled_cb)
        self.traybutton.props.sensitive = False
        self.traybutton.props.active = False
        self.insert(self.traybutton, -1)
        self.traybutton.show()

        tabbed_view = self._activity.get_canvas()

        if tabbed_view.get_n_pages():
            self._connect_to_browser(tabbed_view.props.current_browser)

        tabbed_view.connect_after('switch-page', self.__switch_page_cb)

    def __switch_page_cb(self, tabbed_view, page, page_num):
        self._connect_to_browser(tabbed_view.props.current_browser)

    def _connect_to_browser(self, browser):
        self._browser = browser
        self._update_zoom_buttons()

    def _update_zoom_buttons(self):
        is_webkit_browser = isinstance(self._browser, Browser)
        self.zoomin.set_sensitive(is_webkit_browser)
        self.zoomout.set_sensitive(is_webkit_browser)
        self.zoom_original.set_sensitive(is_webkit_browser)

    def __zoom_original_clicked_cb(self, button):
        tabbed_view = self._activity.get_canvas()
        tabbed_view.props.current_browser.set_zoom_level(ZOOM_ORIGINAL)

    def __zoomin_clicked_cb(self, button):
        tabbed_view = self._activity.get_canvas()
        tabbed_view.props.current_browser.zoom_in()

    def __zoomout_clicked_cb(self, button):
        tabbed_view = self._activity.get_canvas()
        tabbed_view.props.current_browser.zoom_out()

    def __fullscreen_clicked_cb(self, button):
        self._activity.fullscreen()

    def __tray_toggled_cb(self, button):
        if button.props.active:
            self._activity.tray.show()
        else:
            self._activity.tray.hide()
        self.update_traybutton_tooltip()

    def update_traybutton_tooltip(self):
        if not self.traybutton.props.active:
            self.traybutton.set_tooltip(_('Show Tray'))
        else:
            self.traybutton.set_tooltip(_('Hide Tray'))
