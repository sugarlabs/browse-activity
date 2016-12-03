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

from sugar3.graphics.icon import Icon, EventIcon
from sugar3.graphics.tray import HTray
from sugar3.graphics import style
from sugar3.graphics.xocolor import XoColor
from sugar3.graphics.palette import Palette


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


screen = Gdk.Screen.get_default()
css_provider = Gtk.CssProvider.get_default()
css = ('''
@define-color button_grey #808080;

.TitledTray-top-bar {{
    color: white;
    background: @button_grey;
    min-height: {cell2over5}px;
}}
.TitledTray-top-bar label {{
    color: white;
}}
'''.format(
    cell2over5=(style.GRID_CELL_SIZE*2)/5
))

try:
    css_provider.load_from_data(css)
except:
    pass  # Gtk+ 3.18.9 does not have min-height

context = Gtk.StyleContext()
context.add_provider_for_screen(screen, css_provider,
                                Gtk.STYLE_PROVIDER_PRIORITY_USER)


class TitledTray(Gtk.Box):
    '''
    This is a tray that has a title bar.  The title bar has buttons.

    Args:
        title (str): title of the tray
    '''

    def __init__(self, title):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)

        self._top_event_box = Gtk.EventBox()
        self._top_event_box.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                                       Gdk.EventMask.TOUCH_MASK |
                                       Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.add(self._top_event_box)
        self._top_event_box.connect('button-release-event',
                                    self.__top_event_box_release_cb)
        self._top_event_box.show()

        self._top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                                halign=Gtk.Align.CENTER)
        self._top_bar.get_style_context().add_class('TitledTray-top-bar')
        self._top_bar.set_size_request(-1, (style.GRID_CELL_SIZE*3)/5)
        self._top_event_box.add(self._top_bar)
        self._top_bar.show()

        self._title = Gtk.Label(label=title)
        self._top_bar.add(self._title)
        self._title.show()

        self._hide = self.add_button('go-down', 'Hide')
        self._show = self.add_button('go-up', 'Show')
        self._show.hide()

        self._revealer = Gtk.Revealer(reveal_child=True)
        self.add(self._revealer)
        self._revealer.show()
        self.tray = HTray()
        self._revealer.add(self.tray)
        self.tray.show()

    def __top_event_box_release_cb(self, widget, event):
        alloc = widget.get_allocation()
        if 0 < event.x < alloc.width and 0 < event.y < alloc.height:
            self.toggle_expanded()

    def toggle_expanded(self):
        if self._revealer.props.reveal_child:
            self._revealer.props.reveal_child = False
            self._hide.hide()
            self._show.show()
        else:
            self._revealer.props.reveal_child = True
            self._hide.show()
            self._show.hide()

    def add_button(self, icon_name, description, clicked_cb=None):
        icon = EventIcon(icon_name=icon_name,
                         pixel_size=(style.GRID_CELL_SIZE*2)/5,
                         xo_color=XoColor('#ffffff,#ffffff'))
        icon.props.palette = Palette(description)
        self._top_bar.add(icon)

        if clicked_cb:
            def closure(widget, event):
                alloc = widget.get_allocation()
                if 0 < event.x < alloc.width and 0 < event.y < alloc.height:
                    clicked_cb(widget)
            icon.connect('button-release-event', closure)
        icon.show()
        return icon
