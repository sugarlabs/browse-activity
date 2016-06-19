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
from gi.repository import Gdk

from sugar3.graphics.icon import Icon


class TabAdd(Gtk.HBox):
    __gtype_name__ = 'BrowseTabAdd'

    tab_added = GObject.Signal('tab-added', arg_types=[str])

    def __init__(self):
        GObject.GObject.__init__(self)

        add_tab_icon = Icon(icon_name='add')
        button = Gtk.Button()
        button.drag_dest_set(0, [], 0)
        button.props.relief = Gtk.ReliefStyle.NONE
        button.props.focus_on_click = False
        icon_box = Gtk.HBox()
        icon_box.pack_start(add_tab_icon, True, False, 0)
        button.add(icon_box)
        button.connect('clicked', self.__button_clicked_cb)
        button.connect('drag-data-received', self.__drag_cb)
        button.connect('drag-motion', self.__drag_motion_cb)
        button.connect('drag-drop', self.__drag_drop_cb)
        button.set_name('browse-tab-add')
        self.pack_start(button, True, True, 0)
        add_tab_icon.show()
        icon_box.show()
        button.show()

    def __drag_motion_cb(self, widget, context, x, y, time):
        Gdk.drag_status(context, Gdk.DragAction.MOVE, time)
        return True

    def __drag_drop_cb(self, widget, context, x, y, time):
        context_targets = context.list_targets()
        for target in context_targets:
            if str(target) not in ('TIMESTAMP', 'TARGETS', 'MULTIPLE'):
                widget.drag_get_data(context, target, time)
        return True

    def __drag_cb(self, widget, drag_context, x, y, data, info, time):
        uris = data.get_uris()
        for uri in uris:
            self.tab_added.emit(uri)

    def __button_clicked_cb(self, button):
        self.tab_added.emit(None)


class BrowserNotebook(Gtk.Notebook):
    __gtype_name__ = 'BrowseNotebook'

    """Handle an extra tab at the end with an Add Tab button."""

    def __init__(self):
        GObject.GObject.__init__(self)

        tab_add = TabAdd()
        tab_add.connect('tab-added', self.on_add_tab)
        self.set_action_widget(tab_add, Gtk.PackType.END)
        tab_add.show()

    def on_add_tab(self, obj, uri):
        raise NotImplementedError("implement this in the subclass")
