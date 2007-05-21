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
import xpcom
from xpcom.components import interfaces

from sugar.graphics.toolbutton import ToolButton
from sugar.graphics import AddressEntry

class _ProgressListener:
    _com_interfaces_ = interfaces.nsIWebProgressListener
    
    def __init__(self, toolbar):
        self._toolbar = toolbar
    
    def onLocationChange(self, webProgress, request, location):
        self._toolbar._update_navigation_buttons()
        
    def onProgressChange(self, webProgress, request, curSelfProgress,
                         maxSelfProgress, curTotalProgress, maxTotalProgress):
        pass
    
    def onSecurityChange(self, webProgress, request, state):
        pass
        
    def onStateChange(self, webProgress, request, stateFlags, status):
        if stateFlags & interfaces.nsIWebProgressListener.STATE_START:
            self._toolbar._show_reload_icon()
            self._toolbar._update_navigation_buttons()
        if stateFlags & interfaces.nsIWebProgressListener.STATE_STOP:
            self._toolbar._show_stop_icon()
            self._toolbar._update_navigation_buttons()            

    def onStatusChange(self, webProgress, request, status, message):
        pass

class WebToolbar(gtk.Toolbar):
    def __init__(self, browser):
        gtk.Toolbar.__init__(self)

        self._browser = browser
                
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
        
        self._listener = xpcom.server.WrapObject(
            _ProgressListener(self), interfaces.nsIWebProgressListener)
        weak_ref = xpcom.client.WeakReference(self._listener)

        mask = interfaces.nsIWebProgress.NOTIFY_STATE_NETWORK | \
               interfaces.nsIWebProgress.NOTIFY_LOCATION
        self._browser.web_progress.addProgressListener(self._listener, mask)

    def _show_stop_icon(self):
        self._stop_and_reload.set_named_icon('stop')

    def _show_reload_icon(self):
        self._stop_and_reload.set_named_icon('view-refresh')

    def _update_navigation_buttons(self):
        can_go_back = self._browser.web_navigation.canGoBack
        self._back.props.sensitive = can_go_back

        can_go_forward = self._browser.web_navigation.canGoForward
        self._forward.props.sensitive = can_go_forward

    def _entry_activate_cb(self, entry):
        self._embed.load_uri(entry.props.text)
        self._embed.grab_focus()

    def _go_back_cb(self, button):
        self._browser.web_navigation.goBack()
    
    def _go_forward_cb(self, button):
        self._browser.web_navigation.goForward()

    def _stop_and_reload_cb(self, button):
        if self._embed.props.loading:
            self._embed.stop_load()
        else:
            self._embed.reload(0)
