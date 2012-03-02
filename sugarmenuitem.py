# Copyright 2012 One Laptop Per Child
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

from sugar3.graphics.icon import Icon
from sugar3.graphics import style


class SugarMenuItem(Gtk.EventBox):

    __gsignals__ = {
        'clicked': (GObject.SignalFlags.RUN_FIRST, None, [])
    }

    def __init__(self, text_label='', icon_name=None):
        Gtk.EventBox.__init__(self)
        self._sensitive = True
        vbox = Gtk.VBox()
        hbox = Gtk.HBox()
        vbox.set_border_width(style.DEFAULT_PADDING)
        if icon_name is not None:
            self.icon = Icon()
            self.icon.props.icon_name = icon_name
            hbox.pack_start(self.icon, expand=False, fill=False,
                    padding=style.DEFAULT_PADDING)
        align = Gtk.Alignment(xalign=0.0, yalign=0.5, xscale=0.0, yscale=0.0)
        text = '<span foreground="%s">' % style.COLOR_WHITE.get_html() + \
                    text_label + '</span>'
        self.label = Gtk.Label()
        self.label.set_use_markup(True)
        self.label.set_markup(text)
        align.add(self.label)
        hbox.pack_start(align, expand=True, fill=True,
                padding=style.DEFAULT_PADDING)
        vbox.pack_start(hbox, expand=False, fill=False,
                padding=style.DEFAULT_PADDING)
        self.add(vbox)
        self.id_bt_release_cb = self.connect('button-release-event',
                self.__button_release_cb)
        self.id_enter_notify_cb = self.connect('enter-notify-event',
                self.__enter_notify_cb)
        self.id_leave_notify_cb = self.connect('leave-notify-event',
                self.__leave_notify_cb)
        self.modify_bg(Gtk.StateType.NORMAL, style.COLOR_BLACK.get_gdk_color())
        self.show_all()
        self.set_above_child(True)

    def __button_release_cb(self, widget, event):
        self.emit('clicked')

    def __enter_notify_cb(self, widget, event):
        self.modify_bg(Gtk.StateType.NORMAL,
                style.COLOR_BUTTON_GREY.get_gdk_color())

    def __leave_notify_cb(self, widget, event):
        self.modify_bg(Gtk.StateType.NORMAL, style.COLOR_BLACK.get_gdk_color())

    def set_icon(self, icon_name):
        self.icon.props.icon_name = icon_name

    def set_label(self, text_label):
        text = '<span foreground="%s">' % style.COLOR_WHITE.get_html() + \
                    text_label + '</span>'
        self.label.set_markup(text)

    def set_sensitive(self, sensitive):
        if self._sensitive == sensitive:
            return

        self._sensitive = sensitive
        if sensitive:
            self.handler_unblock(self.id_bt_release_cb)
            self.handler_unblock(self.id_enter_notify_cb)
            self.handler_unblock(self.id_leave_notify_cb)
        else:
            self.handler_block(self.id_bt_release_cb)
            self.handler_block(self.id_enter_notify_cb)
            self.handler_block(self.id_leave_notify_cb)
            self.modify_bg(Gtk.StateType.NORMAL,
                    style.COLOR_BLACK.get_gdk_color())
