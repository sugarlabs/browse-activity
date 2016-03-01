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

from gi.repository import WebKit2
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
        self._source_id = None

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
        self._browser = browser

        self._update_buttons()

        # FIXME  this api was changed.  Since multiproccess, we need
        #        a "web extension" which is loaded into the
        #        webkit process to access the page and signal
        # self._selection_changed_hid = self._browser.connect(
        #     'selection-changed', self.__selection_changed_cb)
        if self._source_id is not None:
            GObject.source_remove(self._source_id)
        self._source_id = \
            GObject.timeout_add(300, self.__selection_changed_cb)

        find = self._browser.get_find_controller()
        if find is not None:
            find.connect('found-text', self.__found_text_cb)
            find.connect('failed-to-find-text', self.__failed_to_find_text_cb)

    def __selection_changed_cb(self, *args):
        self._update_buttons()
        return True

    def _update_buttons(self):
        if self._browser.can_query_editing_commands():
            self._find_sensitive(self.undo, WebKit2.EDITING_COMMAND_UNDO)
            self._find_sensitive(self.redo, WebKit2.EDITING_COMMAND_REDO)
            self._find_sensitive(self.copy, WebKit2.EDITING_COMMAND_COPY)
            self._find_sensitive(self.paste, WebKit2.EDITING_COMMAND_PASTE)

    def _find_sensitive(self, button, command):
        self._browser.can_execute_editing_command(
            command, None, self.__can_execute_editing_command_cb, button)

    def __can_execute_editing_command_cb(self, source, result, button):
        can = self._browser.can_execute_editing_command_finish(result)
        button.set_sensitive(can)

    def __undo_cb(self, button):
        self._browser.execute_editing_command(WebKit2.EDITING_COMMAND_UNDO)
        self._update_buttons()

    def __redo_cb(self, button):
        self._browser.execute_editing_command(WebKit2.EDITING_COMMAND_REDO)
        self._update_buttons()

    def __copy_cb(self, button):
        self._browser.execute_editing_command(WebKit2.EDITING_COMMAND_COPY)

    def __paste_cb(self, button):
        self._browser.execute_editing_command(WebKit2.EDITING_COMMAND_PASTE)

    def _find_and_mark_text(self, entry):
        search_text = entry.get_text()
        controller = self._browser.get_find_controller()
        controller.search(search_text,
                          WebKit2.FindOptions.CASE_INSENSITIVE
                          | WebKit2.FindOptions.WRAP_AROUND,
                          (2 << 31) - 1)

    def __search_entry_activate_cb(self, entry):
        self._find_and_mark_text(entry)

    def __search_entry_changed_cb(self, entry):
        self._find_and_mark_text(entry)

    def __found_text_cb(self, controller, match_count):
        self._prev.props.sensitive = True
        self._next.props.sensitive = True
        self.search_entry.modify_text(Gtk.StateType.NORMAL,
                                      style.COLOR_BLACK.get_gdk_color())

    def __failed_to_find_text_cb(self, controller):
        self._prev.props.sensitive = False
        self._next.props.sensitive = False
        self.search_entry.modify_text(Gtk.StateType.NORMAL,
                                      style.COLOR_BUTTON_GREY.get_gdk_color())

    def __find_previous_cb(self, button):
        self._browser.get_find_controller().search_previous()

    def __find_next_cb(self, button):
        self._browser.get_find_controller().search_next()
