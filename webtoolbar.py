# Copyright (C) 2006, Red Hat, Inc.
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

from gettext import gettext as _

import gobject
import gtk
from xpcom.components import interfaces
from xpcom import components

from sugar.graphics.toolbutton import ToolButton
from sugar.graphics.menuitem import MenuItem
from sugar._sugarext import AddressEntry

import sessionhistory
import progresslistener
import filepicker

_MAX_HISTORY_ENTRIES = 15

class WebToolbar(gtk.Toolbar):
    __gtype_name__ = 'WebToolbar'

    __gsignals__ = {
        'add-link': (gobject.SIGNAL_RUN_FIRST,
                     gobject.TYPE_NONE,
                     ([]))
    }

    def __init__(self, browser):
        gtk.Toolbar.__init__(self)

        self._browser = browser
        
        self._loading = False

        self._back = ToolButton('go-previous-paired')
        self._back.set_tooltip(_('Back'))
        self._back.props.sensitive = False
        self._back.connect('clicked', self._go_back_cb)
        self.insert(self._back, -1)
        self._back.show()

        self._forward = ToolButton('go-next-paired')
        self._forward.set_tooltip(_('Forward'))
        self._forward.props.sensitive = False
        self._forward.connect('clicked', self._go_forward_cb)
        self.insert(self._forward, -1)
        self._forward.show()

        self._stop_and_reload = ToolButton('media-playback-stop')
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

        self._link_add = ToolButton('emblem-favorite')
        self._link_add.set_tooltip(_('Bookmark'))
        self._link_add.connect('clicked', self._link_add_clicked_cb)
        self.insert(self._link_add, -1)
        self._link_add.show()
        
        progress_listener = progresslistener.get_instance()
        progress_listener.connect('location-changed', 
                                  self._location_changed_cb)
        progress_listener.connect('loading-start', self._loading_start_cb)
        progress_listener.connect('loading-stop', self._loading_stop_cb)
        progress_listener.connect('loading-progress', 
                                  self._loading_progress_cb)

        session_history = sessionhistory.get_instance()
        session_history.connect('session-history-changed', 
                                self._session_history_changed_cb)

        self._browser.connect("notify::title", self._title_changed_cb)

    def _session_history_changed_cb(self, session_history, current_page_index):
        # We have to wait until the history info is updated.
        gobject.idle_add(self._reload_session_history, current_page_index)

    def _location_changed_cb(self, progress_listener, uri):
        cls = components.classes['@mozilla.org/intl/texttosuburi;1']
        texttosuburi = cls.getService(interfaces.nsITextToSubURI)
        ui_uri = texttosuburi.unEscapeURIForUI(uri.originCharset, uri.spec)

        self._set_address(ui_uri)
        self._update_navigation_buttons()
        filepicker.cleanup_temp_files()

    def _loading_start_cb(self, progress_listener):
        self._set_title(None)
        self._set_loading(True)
        self._update_navigation_buttons()

    def _loading_stop_cb(self, progress_listener):
        self._set_loading(False)
        self._update_navigation_buttons()

    def _loading_progress_cb(self, progress_listener, progress):
        self._set_progress(progress)

    def _set_progress(self, progress):
        self._entry.props.progress = progress

    def _set_address(self, address):
        self._entry.props.address = address

    def _set_title(self, title):
        self._entry.props.title = title

    def _show_stop_icon(self):
        self._stop_and_reload.set_icon('media-playback-stop')

    def _show_reload_icon(self):
        self._stop_and_reload.set_icon('view-refresh')

    def _update_navigation_buttons(self):
        can_go_back = self._browser.web_navigation.canGoBack
        self._back.props.sensitive = can_go_back

        can_go_forward = self._browser.web_navigation.canGoForward
        self._forward.props.sensitive = can_go_forward

    def _entry_activate_cb(self, entry):
        self._browser.load_uri(entry.props.text)
        self._browser.grab_focus()

    def _go_back_cb(self, button):
        self._browser.web_navigation.goBack()
    
    def _go_forward_cb(self, button):
        self._browser.web_navigation.goForward()

    def _title_changed_cb(self, embed, spec):
        self._set_title(embed.props.title)

    def _stop_and_reload_cb(self, button):
        if self._loading:
            self._browser.web_navigation.stop( \
                    interfaces.nsIWebNavigation.STOP_ALL)
        else:
            flags = interfaces.nsIWebNavigation.LOAD_FLAGS_NONE
            self._browser.web_navigation.reload(flags)

    def _set_loading(self, loading):
        self._loading = loading

        if self._loading:
            self._show_stop_icon()
            self._stop_and_reload.set_tooltip(_('Stop'))
        else:
            self._show_reload_icon()
            self._stop_and_reload.set_tooltip(_('Reload'))

    def _reload_session_history(self, current_page_index=None):
        session_history = self._browser.web_navigation.sessionHistory
        if current_page_index is None:
            current_page_index = session_history.index

        for palette in (self._back.get_palette(), self._forward.get_palette()):
            for menu_item in palette.menu.get_children():
                palette.menu.remove(menu_item)

        if current_page_index > _MAX_HISTORY_ENTRIES:
            bottom = current_page_index - _MAX_HISTORY_ENTRIES
        else:
            bottom = 0
        if  (session_history.count - current_page_index) > \
               _MAX_HISTORY_ENTRIES:
            top = current_page_index + _MAX_HISTORY_ENTRIES + 1
        else:
            top = session_history.count

        for i in range(bottom, top):
            if i == current_page_index:
                continue

            entry = session_history.getEntryAtIndex(i, False)
            menu_item = MenuItem(entry.title, text_maxlen=60)
            menu_item.connect('activate', self._history_item_activated_cb, i)

            if i < current_page_index:
                palette = self._back.get_palette()
                palette.menu.prepend(menu_item)
            elif i > current_page_index:
                palette = self._forward.get_palette()
                palette.menu.append(menu_item)

            menu_item.show()

    def _history_item_activated_cb(self, menu_item, index):
        self._browser.web_navigation.gotoIndex(index)

    def _link_add_clicked_cb(self, button):
        self.emit('add-link')

