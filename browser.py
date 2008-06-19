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
import xpcom
from xpcom.nsError import *
from xpcom import components
from xpcom.components import interfaces
from hulahop.webview import WebView

from sugar.datastore import datastore
from sugar import profile
from sugar import env
from sugar.activity import activity

import sessionstore
from palettes import ContentInvoker

_ZOOM_AMOUNT = 0.1

class GetSourceListener(gobject.GObject):
    _com_interfaces_ = interfaces.nsIWebProgressListener
    
    __gsignals__ = {    
        'finished':     (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ([]))
    }
    
    def __init__(self, persist):
        gobject.GObject.__init__(self)
        self._persist = persist

    def onStateChange(self, progress, request, flags, status):
        finished = interfaces.nsIWebBrowserPersist.PERSIST_STATE_FINISHED
        if self._persist.currentState == finished:
            self.emit('finished')

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

        listener = xpcom.server.WrapObject(ContentInvoker(self),
                                           interfaces.nsIDOMEventListener)
        self.window_root.addEventListener('click', listener, False)

        listener = xpcom.server.WrapObject(CommandListener(self.dom_window),
                                           interfaces.nsIDOMEventListener)
        self.window_root.addEventListener('command', listener, False)

    def get_session(self):
        return sessionstore.get_session(self)

    def set_session(self, data):
        return sessionstore.set_session(self, data)

    def get_source(self):
        cls = components.classes[ \
                '@mozilla.org/embedding/browser/nsWebBrowserPersist;1']
        persist = cls.createInstance(interfaces.nsIWebBrowserPersist)
        # get the source from the cache
        persist.persistFlags = \
                interfaces.nsIWebBrowserPersist.PERSIST_FLAGS_FROM_CACHE

        progresslistener = GetSourceListener(persist)
        persist.progressListener = xpcom.server.WrapObject(
            progresslistener, interfaces.nsIWebProgressListener)
        progresslistener.connect('finished', self._have_source_cb)
        
        temp_path = os.path.join(activity.get_activity_root(), 'instance')
        file_path = os.path.join(temp_path, '%i' % time.time())        
        cls = components.classes["@mozilla.org/file/local;1"]
        local_file = cls.createInstance(interfaces.nsILocalFile)
        local_file.initWithPath(file_path)

        uri = self.web_navigation.currentURI            
        persist.saveURI(uri, self.doc_shell, None, None, None, local_file)
        self._create_journal_object(file_path)
        self._jobject.file_path = file_path
        
    def _have_source_cb(self, progress_listener):
        logging.debug("Finished getting source - writing to datastore")      
        datastore.write(self._jobject,
                        reply_handler=self._internal_save_cb,
                        error_handler=self._internal_save_error_cb)

    def _create_journal_object(self, file_path):        
        self._jobject = datastore.create()        
        title = _('Source') + ': ' + self.props.title 
        self._jobject.metadata['title'] = title
        self._jobject.metadata['keep'] = '0'
        self._jobject.metadata['buddies'] = ''
        self._jobject.metadata['preview'] = ''
        self._jobject.metadata['icon-color'] = profile.get_color().to_string()
        self._jobject.metadata['mime_type'] = 'text/html'
        self._jobject.metadata['source'] = '1'
        self._jobject.file_path = ''
        datastore.write(self._jobject)

    def _internal_save_cb(self):
        logging.debug("Saved source object to datastore.")
        activity.show_object_in_journal(self._jobject.object_id) 
        self._cleanup_jobject()
            
    def _internal_save_error_cb(self, err):
        logging.debug("Error saving source object to datastore: %s" % err)
        self._cleanup_jobject()

    def _cleanup_jobject(self):
        if self._jobject:
            if os.path.isfile(self._jobject.file_path):
                logging.debug('_cleanup_jobject: removing %r' % 
                              self._jobject.file_path)
                os.remove(self._jobject.file_path)            
            self._jobject.destroy()
            self._jobject = None

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

class XULDialog(gtk.Window):
    def __init__(self):
        gtk.Window.__init__(self)

        self.view = WebView()
        self.add(self.view)

        self.connect('realize', self.__realize_cb)

    def __realize_cb(self, window):
        self.window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)

class WindowCreator:
    _com_interfaces_ = interfaces.nsIWindowCreator

    def createChromeWindow(self, parent, chrome_flags):
        dialog = XULDialog()
        browser = dialog.view.browser

        dialog.view.is_chrome = True
        item = browser.queryInterface(interfaces.nsIDocShellTreeItem)
        item.itemType = interfaces.nsIDocShellTreeItem.typeChromeWrapper

        return browser.containerWindow

window_creator = WindowCreator()
cls = components.classes['@mozilla.org/embedcomp/window-watcher;1']
window_watcher = cls.getService(interfaces.nsIWindowWatcher)
window_watcher.setWindowCreator(window_creator)
