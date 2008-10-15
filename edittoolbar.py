# Copyright (C) 2008, One Laptop Per Child
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

import gtk
from gettext import gettext as _

from xpcom import components
from xpcom.components import interfaces

from sugar.activity import activity
from sugar.graphics import iconentry
from sugar.graphics.toolbutton import ToolButton
from sugar.graphics import style

class EditToolbar(activity.EditToolbar):

    _com_interfaces_ = interfaces.nsIObserver

    def __init__(self, browser):
        activity.EditToolbar.__init__(self)

        self._browser = browser

        self.undo.connect('clicked', self.__undo_cb)
        self.redo.connect('clicked', self.__redo_cb)
        self.copy.connect('clicked', self.__copy_cb)
        self.paste.connect('clicked', self.__paste_cb)

        """
        Notifications are not working right now:
        https://bugzilla.mozilla.org/show_bug.cgi?id=207339

        command_manager = self._get_command_manager()
        self.undo.set_sensitive(
                command_manager.isCommandEnabled('cmd_undo', None))
        self.redo.set_sensitive(
                command_manager.isCommandEnabled('cmd_redo', None))
        self.copy.set_sensitive(
                command_manager.isCommandEnabled('cmd_copy', None))
        self.paste.set_sensitive(
                command_manager.isCommandEnabled('cmd_paste', None))

        self._observer = xpcom.server.WrapObject(self, interfaces.nsIObserver)
        command_manager.addCommandObserver(self._observer, 'cmd_undo')
        command_manager.addCommandObserver(self._observer, 'cmd_redo')
        command_manager.addCommandObserver(self._observer, 'cmd_copy')
        command_manager.addCommandObserver(self._observer, 'cmd_paste')

    def observe(self, subject, topic, data):
        logging.debug('observe: %r %r %r' % (subject, topic, data))
        """

        separator = gtk.SeparatorToolItem()
        separator.set_draw(False)
        separator.set_expand(True)
        self.insert(separator, -1)
        separator.show()

        search_item = gtk.ToolItem()
        self.search_entry = iconentry.IconEntry()
        self.search_entry.set_icon_from_name(iconentry.ICON_ENTRY_PRIMARY,
                                             'system-search')
        self.search_entry.add_clear_button()
        self.search_entry.connect('activate', self.__search_entry_activate_cb)
        self.search_entry.connect('changed', self.__search_entry_changed_cb)

        width = int(gtk.gdk.screen_width() / 3)
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

    def __undo_cb(self, button):
        command_manager = self._get_command_manager()
        command_manager.doCommand('cmd_undo', None, None)

    def __redo_cb(self, button):
        command_manager = self._get_command_manager()
        command_manager.doCommand('cmd_redo', None, None)

    def __copy_cb(self, button):
        command_manager = self._get_command_manager()
        command_manager.doCommand('cmd_copy', None, None)

    def __paste_cb(self, button):
        command_manager = self._get_command_manager()
        command_manager.doCommand('cmd_paste', None, None)

    def _get_command_manager(self):
        web_browser = self._browser.browser
        requestor = web_browser.queryInterface(interfaces.nsIInterfaceRequestor)
        return requestor.getInterface(interfaces.nsICommandManager)

    def __search_entry_activate_cb(self, entry):
        self._browser.typeahead.findAgain(False, False)

    def __search_entry_changed_cb(self, entry):        
        found = self._browser.typeahead.find(entry.props.text, False)
        if found == interfaces.nsITypeAheadFind.FIND_NOTFOUND:
            self._prev.props.sensitive = False
            self._next.props.sensitive = False
            entry.modify_text(gtk.STATE_NORMAL, 
                              style.COLOR_BUTTON_GREY.get_gdk_color())
        else:
            self._prev.props.sensitive = True
            self._next.props.sensitive = True
            entry.modify_text(gtk.STATE_NORMAL, 
                              style.COLOR_BLACK.get_gdk_color())

    def __find_previous_cb(self, button):
        self._browser.typeahead.findAgain(True, False)

    def __find_next_cb(self, button):
        self._browser.typeahead.findAgain(False, False)
