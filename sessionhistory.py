# Copyright (C) 2007, One Laptop Per Child
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

import logging

import gobject
import xpcom
from xpcom.components import interfaces

class HistoryListener(gobject.GObject):
    _com_interfaces_ = interfaces.nsISHistoryListener
    
    def __init__(self, browser):
        gobject.GObject.__init__(self)

        self._wrapped_self = xpcom.server.WrapObject(self, interfaces.nsISHistoryListener)
        weak_ref = xpcom.client.WeakReference(self._wrapped_self)

        session_history = browser.web_navigation.sessionHistory
        session_history.addSHistoryListener(self._wrapped_self)

    def OnHistoryGoBack(self, back_uri):
        return True

    def OnHistoryGoForward(self, forward_uri):
        return True

    def OnHistoryGotoIndex(self, index, goto_uri):
        return True

    def OnHistoryNewEntry(self, new_uri):
        logging.debug(new_uri.spec)

    def OnHistoryPurge(self, num_entries):
        return True

    def OnHistoryReload(self, reload_uri, reload_flags):
        return True

_session_history_listener = None

def init(browser):
    global _session_history_listener
    _session_history_listener = HistoryListener(browser)

def get_instance():
    global _session_history_listener
    return _session_history_listener
