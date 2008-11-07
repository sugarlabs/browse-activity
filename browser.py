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

import os
import time
import logging
from gettext import gettext as _

import gobject
import gtk
import hulahop
import xpcom
from xpcom.nsError import *
from xpcom import components
from xpcom.components import interfaces
from hulahop.webview import WebView

from sugar.datastore import datastore
from sugar import profile
from sugar import env
from sugar.activity import activity
from sugar.graphics import style

import sessionstore
from palettes import ContentInvoker
from sessionhistory import HistoryListener
from progresslistener import ProgressListener

_ZOOM_AMOUNT = 0.1

class GetSourceListener(object):
    _com_interfaces_ = interfaces.nsIWebProgressListener
    
    def __init__(self, file_path, async_cb, async_err_cb):
        self._file_path = file_path
        self._async_cb = async_cb
        self._async_err_cb = async_err_cb

    def onStateChange(self, webProgress, request, stateFlags, status):
        if stateFlags & interfaces.nsIWebProgressListener.STATE_IS_REQUEST and \
                stateFlags & interfaces.nsIWebProgressListener.STATE_STOP:
            self._async_cb(self._file_path)

    def onProgressChange(self, progress, request, curSelfProgress,
                         maxSelfProgress, curTotalProgress, maxTotalProgress):
        pass

    def onLocationChange(self, progress, request, location):
        pass

    def onStatusChange(self, progress, request, status, message):
        pass

    def onSecurityChange(self, progress, request, state):
        pass

class CommandListener(object):
    _com_interfaces_ = interfaces.nsIDOMEventListener
    def __init__(self, window):
        self._window = window

    def handleEvent(self, event):
        if not event.isTrusted:
            return

        uri = event.originalTarget.ownerDocument.documentURI
        if not uri.startswith('about:neterror?e=nssBadCert'):
            return

        cls = components.classes['@sugarlabs.org/add-cert-exception;1']
        cert_exception = cls.createInstance(interfaces.hulahopAddCertException)
        cert_exception.showDialog(self._window)

class Browser(WebView):

    AGENT_SHEET = os.path.join(activity.get_bundle_path(), 
                               'agent-stylesheet.css')
    USER_SHEET = os.path.join(env.get_profile_path(), 'gecko', 
                              'user-stylesheet.css')

    def __init__(self):
        WebView.__init__(self)

        self.history = HistoryListener()
        self.progress = ProgressListener()

        cls = components.classes["@mozilla.org/typeaheadfind;1"]
        self.typeahead = cls.createInstance(interfaces.nsITypeAheadFind)

        self._jobject = None

        io_service_class = components.classes[ \
                "@mozilla.org/network/io-service;1"]
        io_service = io_service_class.getService(interfaces.nsIIOService)

        # Use xpcom to turn off "offline mode" detection, which disables
        # access to localhost for no good reason.  (Trac #6250.)
        io_service2 = io_service_class.getService(interfaces.nsIIOService2)
        io_service2.manageOfflineStatus = False

        cls = components.classes['@mozilla.org/content/style-sheet-service;1']
        style_sheet_service = cls.getService(interfaces.nsIStyleSheetService)

        if os.path.exists(Browser.AGENT_SHEET):
            agent_sheet_uri = io_service.newURI('file:///' + 
                                                Browser.AGENT_SHEET,
                                                None, None)
            style_sheet_service.loadAndRegisterSheet(agent_sheet_uri,
                    interfaces.nsIStyleSheetService.AGENT_SHEET)

        if os.path.exists(Browser.USER_SHEET):
            user_sheet_uri = io_service.newURI('file:///' + Browser.USER_SHEET,
                                               None, None)
            style_sheet_service.loadAndRegisterSheet(user_sheet_uri,
                    interfaces.nsIStyleSheetService.USER_SHEET)

    def do_setup(self):
        WebView.do_setup(self)

        listener = xpcom.server.WrapObject(ContentInvoker(self),
                                           interfaces.nsIDOMEventListener)
        self.window_root.addEventListener('click', listener, False)

        listener = xpcom.server.WrapObject(CommandListener(self.dom_window),
                                           interfaces.nsIDOMEventListener)
        self.window_root.addEventListener('command', listener, False)

        self.progress.setup(self)

        self.history.setup(self.web_navigation)

        self.typeahead.init(self.doc_shell)

    def get_session(self):
        return sessionstore.get_session(self)

    def set_session(self, data):
        return sessionstore.set_session(self, data)

    def get_source(self, async_cb, async_err_cb):
        cls = components.classes[ \
                '@mozilla.org/embedding/browser/nsWebBrowserPersist;1']
        persist = cls.createInstance(interfaces.nsIWebBrowserPersist)
        # get the source from the cache
        persist.persistFlags = \
                interfaces.nsIWebBrowserPersist.PERSIST_FLAGS_FROM_CACHE

        temp_path = os.path.join(activity.get_activity_root(), 'instance')
        file_path = os.path.join(temp_path, '%i' % time.time())        
        cls = components.classes["@mozilla.org/file/local;1"]
        local_file = cls.createInstance(interfaces.nsILocalFile)
        local_file.initWithPath(file_path)

        progresslistener = GetSourceListener(file_path, async_cb, async_err_cb)
        persist.progressListener = xpcom.server.WrapObject(
            progresslistener, interfaces.nsIWebProgressListener)

        uri = self.web_navigation.currentURI            
        persist.saveURI(uri, self.doc_shell, None, None, None, local_file)

    def zoom_in(self):
        contentViewer = self.doc_shell.queryInterface( \
                interfaces.nsIDocShell).contentViewer
        if contentViewer is not None:
            markupDocumentViewer = contentViewer.queryInterface( \
                    interfaces.nsIMarkupDocumentViewer)
            markupDocumentViewer.fullZoom += _ZOOM_AMOUNT

    def zoom_out(self):
        contentViewer = self.doc_shell.queryInterface( \
                interfaces.nsIDocShell).contentViewer
        if contentViewer is not None:
            markupDocumentViewer = contentViewer.queryInterface( \
                    interfaces.nsIMarkupDocumentViewer)
            markupDocumentViewer.fullZoom -= _ZOOM_AMOUNT

class PopupDialog(gtk.Window):
    def __init__(self):
        gtk.Window.__init__(self)

        self.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)

        border = style.GRID_CELL_SIZE
        self.set_default_size(gtk.gdk.screen_width() - border * 2,
                              gtk.gdk.screen_height() - border * 2)

        self.view = WebView()
        self.add(self.view)
        self.view.realize()

class WindowCreator:
    _com_interfaces_ = interfaces.nsIWindowCreator

    def createChromeWindow(self, parent, flags):
        dialog = PopupDialog()

        parent_dom_window = parent.webBrowser.contentDOMWindow
        parent_view = hulahop.get_view_for_window(parent_dom_window)
        if parent_view:
            dialog.set_transient_for(parent_view.get_toplevel())

        browser = dialog.view.browser

        if flags & interfaces.nsIWebBrowserChrome.CHROME_OPENAS_CHROME:
            dialog.view.is_chrome = True

            item = browser.queryInterface(interfaces.nsIDocShellTreeItem)
            item.itemType = interfaces.nsIDocShellTreeItem.typeChromeWrapper

        return browser.containerWindow

window_creator = WindowCreator()
cls = components.classes['@mozilla.org/embedcomp/window-watcher;1']
window_watcher = cls.getService(interfaces.nsIWindowWatcher)
window_watcher.setWindowCreator(window_creator)
