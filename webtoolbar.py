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
import logging

import gtk

from sugar.graphics.toolbutton import ToolButton

from sugar.browser import AddressEntry

class WebToolbar(gtk.Toolbar):
    def __init__(self, embed):
        gtk.Toolbar.__init__(self)
        
        self._back = ToolButton('go-previous')
        self._back.props.sensitive = False
        self._back.connect('clicked', self._go_back_cb)
        self.insert(self._back, -1)
        self._back.show()

        self._forward = ToolButton('go-next')
        self._forward.props.sensitive = False
        self._forward.connect('clicked', self._go_forward_cb)
        self.insert(self._forward, -1)
        self._forward.show()

        self._stop_and_reload = ToolButton('stop')
        self._stop_and_reload.connect('clicked', self._stop_and_reload_cb)
        self.insert(self._stop_and_reload, -1)
        self._stop_and_reload.show()

        self._entry = AddressEntry()
        self._entry.connect('activate', self._entry_activate_cb)

        entry_item = gtk.ToolItem()
        entry_item.set_expand(True)
        entry_item.add(self._entry)
        self._entry.show()
        
        self.insert(entry_item, -1)
        entry_item.show()

        self._embed = embed
        embed.connect("notify::progress", self._progress_changed_cb)
        embed.connect("notify::loading", self._loading_changed_cb)
        embed.connect("notify::address", self._address_changed_cb)
        embed.connect("notify::title", self._title_changed_cb)
        embed.connect("notify::can-go-back", self._can_go_back_changed_cb)
        embed.connect("notify::can-go-forward",
                      self._can_go_forward_changed_cb)

        self._update_stop_and_reload_icon()

    def _update_stop_and_reload_icon(self):
        if self._embed.props.loading:
            self._stop_and_reload.set_named_icon('stop')
        else:
            self._stop_and_reload.set_named_icon('view-refresh')

    def _progress_changed_cb(self, embed, spec):
        self._entry.props.progress = embed.props.progress

    def _loading_changed_cb(self, embed, spec):
        self._update_stop_and_reload_icon()

    def _address_changed_cb(self, embed, spec):
        self._entry.props.address = embed.props.address

    def _title_changed_cb(self, embed, spec):
        self._entry.props.title = embed.props.title

    def _can_go_back_changed_cb(self, embed, spec):
        self._back.props.sensitive = embed.props.can_go_back

    def _can_go_forward_changed_cb(self, embed, spec):
        self._forward.props.sensitive = embed.props.can_go_forward

    def _entry_activate_cb(self, entry):
        self._embed.load_url(entry.props.text)
        self._embed.grab_focus()

    def _go_back_cb(self, button):
        self._embed.go_back()
    
    def _go_forward_cb(self, button):
        self._embed.go_forward()

    def _stop_and_reload_cb(self, button):
        if self._embed.props.loading:
            self._embed.stop_load()
        else:
            self._embed.reload(0)
