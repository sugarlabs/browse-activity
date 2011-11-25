# Copyright (C) 2006, Red Hat, Inc.
# Copyright (C) 2011, One Laptop Per Child
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

from gi.repository import GObject
from gi.repository import Gtk

from sugar.graphics.icon import Icon


class TabAdd(Gtk.HBox):
    __gtype_name__ = 'TabAdd'

    __gsignals__ = {
        'tab-added': (GObject.SignalFlags.RUN_FIRST,
                      None,
                      ([])),
    }

    def __init__(self):
        GObject.GObject.__init__(self)

        add_tab_icon = Icon(icon_name='add')
        button = Gtk.Button()
        button.props.relief = Gtk.ReliefStyle.NONE
        button.props.focus_on_click = False
        icon_box = Gtk.HBox()
        icon_box.pack_start(add_tab_icon, True, False, 0)
        button.add(icon_box)
        button.connect('clicked', self.__button_clicked_cb)
        button.set_name('browse-tab-add')
        self.pack_start(button, True, True, 0)
        add_tab_icon.show()
        icon_box.show()
        button.show()

    def __button_clicked_cb(self, button):
        self.emit('tab-added')


class BrowserNotebook(Gtk.Notebook):
    __gtype_name__ = 'BrowserNotebook'

    """Handle an extra tab at the end with an Add Tab button."""

    def __init__(self):
        GObject.GObject.__init__(self)
        self._switch_handler = self.connect('switch-page',
                                            self.__on_switch_page)

        tab_add = TabAdd()
        tab_add.connect('tab-added', self.on_add_tab)
        empty_page = Gtk.HBox()
        self.append_page(empty_page, tab_add)
        empty_page.show()

    def on_add_tab(self, obj):
        raise NotImplementedError, "implement this in the subclass"

    def __on_switch_page(self, notebook, page, page_num):
        """Don't switch to the extra tab at the end."""
        if page_num == Gtk.Notebook.get_n_pages(self) - 1:
            self.handler_block(self._switch_handler)
            self.set_current_page(-1)
            self.handler_unblock(self._switch_handler)
            self.connect('switch-page', self.__on_switch_page)
            self.stop_emission("switch-page")

    def get_n_pages(self):
        """Skip the extra tab at the end on the pages count."""
        return Gtk.Notebook.get_n_pages(self) - 1

    def append_page(self, page, label):
        """Append keeping the extra tab at the end."""
        return self.insert_page(page, label, self.get_n_pages())

    def set_current_page(self, number):
        """If indexing from the end, skip the extra tab."""
        if number < 0:
            number = self.get_n_pages() - 1
        Gtk.Notebook.set_current_page(self, number)
