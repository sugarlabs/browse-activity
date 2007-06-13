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

import logging

import gobject
import gtk
import xpcom
from xpcom.nsError import *
from xpcom import components
from xpcom.components import interfaces
from hulahop.webview import WebView

import sessionstore
from dnd import DragDropHooks

class Browser(WebView):
    def __init__(self):
        WebView.__init__(self)

        window_creator = WindowCreator(self)
        cls = components.classes['@mozilla.org/embedcomp/window-watcher;1']
        window_watcher = cls.getService(interfaces.nsIWindowWatcher)
        window_watcher.setWindowCreator(window_creator)
        
        self.is_chrome = False
        
        self.connect('realize', self._realize_cb)
        
    def _realize_cb(self, widget):
        drag_drop_hooks = DragDropHooks(self)

        cls = components.classes['@mozilla.org/embedcomp/command-params;1']
        cmd_params = cls.createInstance('nsICommandParams')
        cmd_params.setISupportsValue('addhook', drag_drop_hooks)

        requestor = self.browser.queryInterface(interfaces.nsIInterfaceRequestor)
        command_manager = requestor.getInterface(interfaces.nsICommandManager)
        command_manager.doCommand('cmd_clipboardDragDropHook', cmd_params, self.window)

    def get_session(self):
        return sessionstore.get_session(self)

    def set_session(self, session_data):
        return sessionstore.set_session(self, session_data)

class WindowCreator:
    _com_interfaces_ = interfaces.nsIWindowCreator

    def __init__(self, browser):
        self._popup_creators = []
        self._browser = browser

    def createChromeWindow(self, parent, chrome_flags):
        logging.debug('createChromeWindow: %r %r' % (parent, chrome_flags))

        popup_creator = _PopupCreator(self._browser.get_toplevel())
        popup_creator.connect('popup-created', self._popup_created_cb)

        self._popup_creators.append(popup_creator)

        browser = popup_creator.get_embed()
        
        if chrome_flags & interfaces.nsIWebBrowserChrome.CHROME_OPENAS_CHROME:
            logging.debug('Creating chrome window.')
            browser.is_chrome = True
            item = browser.browser.queryInterface(interfaces.nsIDocShellTreeItem)
            item.itemType = interfaces.nsIDocShellTreeItem.typeChromeWrapper
        else:
            logging.debug('Creating browser window.')
            item = browser.browser.queryInterface(interfaces.nsIDocShellTreeItem)
            item.itemType = interfaces.nsIDocShellTreeItem.typeContentWrapper
        
        browser.realize()
        
        return browser.browser.containerWindow

    def _popup_created_cb(self, creator):
        self._popup_creators.remove(creator)

class _PopupCreator(gobject.GObject):
    __gsignals__ = {
        'popup-created':  (gobject.SIGNAL_RUN_FIRST,
                           gobject.TYPE_NONE, ([])),
    }

    def __init__(self, parent_window):
        gobject.GObject.__init__(self)

        logging.debug('Creating the popup widget')

        self._parent_window = parent_window

        self._dialog = gtk.Window()
        self._dialog.set_resizable(True)

        self._dialog.realize()
        self._dialog.window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)

        self._embed = Browser()
        self._vis_sid = self._embed.connect('notify::visible', self._notify_visible_cb)
        self._dialog.add(self._embed)

    def _notify_visible_cb(self, embed, param):
        self._embed.disconnect(self._vis_sid)

        if self._embed.type == Browser.TYPE_POPUP or self._embed.is_chrome:
            logging.debug('Show the popup')
            self._embed.show()
            self._dialog.set_transient_for(self._parent_window)
            self._dialog.show()
        else:
            logging.debug('Open a new activity for the popup')
            self._dialog.remove(self._embed)
            self._dialog.destroy()
            self._dialog = None

            # FIXME We need a better way to handle this.
            # It seem like a pretty special case though, I doubt
            # other activities will need something similar.
            from webactivity import WebActivity
            from sugar.activity import activityfactory
            from sugar.activity.activityhandle import ActivityHandle
            handle = ActivityHandle(activityfactory.create_activity_id())
            activity = WebActivity(handle, self._embed)
            activity.show()

        self.emit('popup-created')

    def get_embed(self):
        return self._embed

