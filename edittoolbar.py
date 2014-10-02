# Copyright (C) 2008, One Laptop Per Child
# Copyright (C) 2009 Simon Schampijer
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
from gettext import gettext as _

from sugar3.activity.widgets import EditToolbar as BaseEditToolbar
from sugar3.graphics import iconentry
from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics import style


class EditToolbar(BaseEditToolbar):
    def __init__(self, act):
        BaseEditToolbar.__init__(self)

        self._activity = act
        self._browser = None

        self.undo.connect('clicked', self.__undo_cb)
        self.redo.connect('clicked', self.__redo_cb)
        self.copy.connect('clicked', self.__copy_cb)
        self.paste.connect('clicked', self.__paste_cb)

        separator = Gtk.SeparatorToolItem()
        separator.set_draw(False)
        separator.set_expand(True)
        self.insert(separator, -1)
        separator.show()

        search_item = Gtk.ToolItem()
        self.search_entry = iconentry.IconEntry()
        self.search_entry.set_icon_from_name(iconentry.ICON_ENTRY_PRIMARY,
                                             'entry-search')
        self.search_entry.add_clear_button()
        self.search_entry.connect('activate', self.__search_entry_activate_cb)
        self.search_entry.connect('changed', self.__search_entry_changed_cb)

        width = int(Gdk.Screen.width() / 3)
        self.search_entry.set_size_request(width, -1)

        search_item.add(self.search_entry)
        self.search_entry.show()

        self.insert(search_item, -1)
        search_item.show()

        self._prev = ToolButton('go-previous-paired')
        self._prev.set_tooltip(_('Previous'))
        self._prev.props.sensitive = False
        self._prev.connect('clicked', self.__find_previous_cb)
        self.insert(self._prev, -1)
        self._prev.show()

        self._next = ToolButton('go-next-paired')
        self._next.set_tooltip(_('Next'))
        self._next.props.sensitive = False
        self._next.connect('clicked', self.__find_next_cb)
        self.insert(self._next, -1)
        self._next.show()

        tabbed_view = self._activity.get_canvas()

        GObject.idle_add(lambda: self._connect_to_browser(
            tabbed_view.props.current_browser))

        tabbed_view.connect_after('switch-page', self.__switch_page_cb)

    def __switch_page_cb(self, tabbed_view, page, page_num):
        self._connect_to_browser(tabbed_view.props.current_browser)

    def _connect_to_browser(self, browser):
        if self._browser is not None:
            self._browser.disconnect(self._selection_changed_hid)

        self._browser = browser

        self._update_undoredo_buttons()
        self._update_copypaste_buttons()

        self._selection_changed_hid = self._browser.connect(
            'selection-changed', self._selection_changed_cb)

    def _selection_changed_cb(self, widget):
        self._update_undoredo_buttons()
        self._update_copypaste_buttons()

    def _update_undoredo_buttons(self):
        self.undo.set_sensitive(self._browser.can_undo())
        self.redo.set_sensitive(self._browser.can_redo())

    def _update_copypaste_buttons(self):
        self.copy.set_sensitive(self._browser.can_copy_clipboard())
        self.paste.set_sensitive(self._browser.can_paste_clipboard())

    def __undo_cb(self, button):
        self._browser.undo()
        self._update_undoredo_buttons()

    def __redo_cb(self, button):
        self._browser.redo()
        self._update_undoredo_buttons()

    def __copy_cb(self, button):
        self._browser.copy_clipboard()

    def __paste_cb(self, button):
        self._browser.paste_clipboard()

    def _find_and_mark_text(self, entry):
        search_text = entry.get_text()
        self._browser.unmark_text_matches()
        self._browser.mark_text_matches(search_text, case_sensitive=False,
                                        limit=0)
        self._browser.set_highlight_text_matches(True)
        found = self._browser.search_text(search_text, case_sensitive=False,
                                          forward=True, wrap=True)
        return found

    def __search_entry_activate_cb(self, entry):
        self._find_and_mark_text(entry)

    def __search_entry_changed_cb(self, entry):
        found = self._find_and_mark_text(entry)
        if not found:
            self._prev.props.sensitive = False
            self._next.props.sensitive = False
            entry.modify_text(Gtk.StateType.NORMAL,
                              style.COLOR_BUTTON_GREY.get_gdk_color())
        else:
            self._prev.props.sensitive = True
            self._next.props.sensitive = True
            entry.modify_text(Gtk.StateType.NORMAL,
                              style.COLOR_BLACK.get_gdk_color())

    def __find_previous_cb(self, button):
        search_text = self.search_entry.get_text()
        self._browser.search_text(search_text, case_sensitive=False,
                                  forward=False, wrap=True)

    def __find_next_cb(self, button):
        search_text = self.search_entry.get_text()
        self._browser.search_text(search_text, case_sensitive=False,
                                  forward=True, wrap=True)
