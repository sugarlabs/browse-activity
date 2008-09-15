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
import pango
from xpcom.components import interfaces
from xpcom import components

from sugar.graphics.toolbutton import ToolButton
from sugar.graphics.menuitem import MenuItem
from sugar._sugarext import AddressEntry

import sessionhistory
import progresslistener
import filepicker
import places

_MAX_HISTORY_ENTRIES = 15

class WebEntry(AddressEntry):
    _COL_ADDRESS = 0
    _COL_TITLE = 1

    def __init__(self):
        gobject.GObject.__init__(self)

        self._address = None
        self._title = None
        self._search_view = self._search_create_view()

        self._search_window = gtk.Window(gtk.WINDOW_POPUP)
        self._search_window.add(self._search_view)
        self._search_view.show()

        self.connect('focus-in-event', self.__focus_in_event_cb)
        self.connect('populate-popup', self.__populate_popup_cb)
        self.connect('key-press-event', self.__key_press_event_cb)
        self.connect('enter-notify-event', self.__enter_notify_event_cb)
        self.connect('leave-notify-event', self.__leave_notify_event_cb)
        self._focus_out_hid = self.connect(
                    'focus-out-event', self.__focus_out_event_cb)
        self._change_hid = self.connect('changed', self.__changed_cb)

    def _set_text(self, text):
        """Set the text but block changes notification, so that we can
           recognize changes caused directly by user actions"""
        self.handler_block(self._change_hid)
        try:
            self.props.text = text            
        finally:
            self.handler_unblock(self._change_hid)
        self.set_position(-1)

    def activate(self, uri):
        self._set_text(uri)
        self._search_popdown()
        self.emit('activate')

    def _set_address(self, address):
        self._address = address

    address = gobject.property(type=str, setter=_set_address)

    def _set_title(self, title):
        self._title = title
        if title is not None and not self.props.has_focus:
            self._set_text(title)

    title = gobject.property(type=str, setter=_set_title)

    def _search_create_view(self):
        view = gtk.TreeView()
        view.props.headers_visible = False

        view.connect('button-press-event', self.__view_button_press_event_cb)

        column = gtk.TreeViewColumn()
        view.append_column(column)

        cell = gtk.CellRendererText()
        cell.props.ellipsize = pango.ELLIPSIZE_END
        cell.props.ellipsize_set = True
        cell.props.font = 'Bold'
        column.pack_start(cell, True)

        column.set_attributes(cell, text=self._COL_TITLE)

        cell = gtk.CellRendererText()
        cell.props.ellipsize = pango.ELLIPSIZE_END
        cell.props.ellipsize_set = True
        cell.props.alignment = pango.ALIGN_LEFT
        column.pack_start(cell)

        column.set_attributes(cell, text=self._COL_ADDRESS)

        return view

    def _search_update(self):
        list_store = gtk.ListStore(str, str)

        for place in places.get_store().search(self.props.text):
            list_store.append([place.uri, place.title])

        self._search_view.set_model(list_store)

        return len(list_store) > 0

    def _search_popup(self):
        entry_x, entry_y = self.window.get_origin()
        entry_w, entry_h = self.size_request()

        x = entry_x + entry_h / 2
        y = entry_y + entry_h
        width = self.allocation.width - entry_h
        height = gtk.gdk.screen_height() / 3

        self._search_window.move(x, y)
        self._search_window.resize(width, height)
        self._search_window.show()

    def _search_popdown(self):
        self._search_window.hide()

    def __focus_in_event_cb(self, entry, event):
        self._set_text(self._address)
        self._search_popdown()

    def __focus_out_event_cb(self, entry, event):
        self._set_text(self._title)
        self._search_popdown()

    def __enter_notify_event_cb(self, entry, event):
        if not entry.props.has_focus:
            self._set_text(self._address)

    def __leave_notify_event_cb(self, entry, event):
        if not entry.props.has_focus:
            self._set_text(self._title)

    def __view_button_press_event_cb(self, view, event):
        model = view.get_model()

        path, col_, x_, y_ = view.get_path_at_pos(event.x, event.y)
        if path:
            uri = model[path][self._COL_ADDRESS]
            self.activate(uri)

    def __key_press_event_cb(self, entry, event):
        keyname = gtk.gdk.keyval_name(event.keyval)

        selection = self._search_view.get_selection()
        model, selected = selection.get_selected()

        if keyname == 'Up':
            if selected is None:
                selection.select_iter(model[-1].iter)
                self._set_text(model[-1][0])
            else:                    
                index = model.get_path(selected)[0]
                if index > 0:
                    selection.select_path(index - 1)
                    self._set_text(model[index - 1][0])
            return True
        elif keyname == 'Down':
            if selected is None:
                down_iter = model.get_iter_first()
            else:    
                down_iter = model.iter_next(selected)
            if down_iter:
                selection.select_iter(down_iter)                
                self._set_text(model.get(down_iter, 0)[0])
            return True
        elif keyname == 'Return':
            if selected is None:
                return False
            uri = model[model.get_path(selected)][self._COL_ADDRESS]
            self.activate(uri)
            return True
        elif keyname == 'Escape':
            self._search_window.hide()
            return True
        return False

    def __popup_unmap_cb(self, entry):
        self.handler_unblock(self._focus_out_hid)

    def __populate_popup_cb(self, entry, menu):
        self.handler_block(self._focus_out_hid)
        menu.connect('unmap', self.__popup_unmap_cb)

    def __changed_cb(self, entry):
        self._address = self.props.text

        if not self.props.text or not self._search_update():
            self._search_popdown()
        else:
            self._search_popup()

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

        self.entry = WebEntry()
        self.entry.connect('activate', self._entry_activate_cb)

        entry_item = gtk.ToolItem()
        entry_item.set_expand(True)
        entry_item.add(self.entry)
        self.entry.show()
        
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
        self.entry.props.progress = progress

    def _set_address(self, address):
        self.entry.props.address = address

    def _set_title(self, title):
        self.entry.props.title = title

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

