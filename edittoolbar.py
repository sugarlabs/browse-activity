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

from xpcom.components import interfaces

from sugar.activity import activity

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

