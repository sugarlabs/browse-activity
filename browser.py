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
from gettext import gettext as _

import gobject
import gtk
import tempfile
import os
import time
import xpcom
from xpcom.nsError import *
from xpcom import components
from xpcom.components import interfaces
from hulahop.webview import WebView

from sugar.datastore import datastore
from sugar import profile
from sugar.activity import activityfactory

import sessionstore
from dnd import DragDropHooks

class GetSourceListener(gobject.GObject):
    _com_interfaces_ = interfaces.nsIWebProgressListener
    
    __gsignals__ = {    
        'finished':     (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                             ([]))
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

    def onSecurityChange(progress, request, state):
        pass
    
class Browser(WebView):
    def __init__(self):
        WebView.__init__(self)

        window_creator = WindowCreator(self)
        cls = components.classes['@mozilla.org/embedcomp/window-watcher;1']
        window_watcher = cls.getService(interfaces.nsIWindowWatcher)
        window_watcher.setWindowCreator(window_creator)
        
        self.connect('realize', self._realize_cb)
        
    def _realize_cb(self, widget):
        drag_drop_hooks = DragDropHooks(self)

        cls = components.classes['@mozilla.org/embedcomp/command-params;1']
        cmd_params = cls.createInstance('nsICommandParams')
        cmd_params.setISupportsValue('addhook', drag_drop_hooks)

        requestor = self.browser.queryInterface(interfaces.nsIInterfaceRequestor)
        command_manager = requestor.getInterface(interfaces.nsICommandManager)
        command_manager.doCommand('cmd_clipboardDragDropHook', cmd_params, self.dom_window)

    def get_session(self):
        return sessionstore.get_session(self)

    def set_session(self, data):
        return sessionstore.set_session(self, data)

    def get_source(self):
        cls = components.classes['@mozilla.org/embedding/browser/nsWebBrowserPersist;1']
        persist = cls.createInstance(interfaces.nsIWebBrowserPersist)
        # get the source from the cache
        persist.persistFlags = interfaces.nsIWebBrowserPersist.PERSIST_FLAGS_FROM_CACHE

        progresslistener = GetSourceListener(persist)
        persist.progressListener = xpcom.server.WrapObject(
            progresslistener, interfaces.nsIWebProgressListener)
        progresslistener.connect('finished', self._have_source_cb)
            
        file_path = os.path.join(tempfile.gettempdir(), '%i' % time.time())        
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
        self._jobject.metadata['mime_type'] = 'text/plain'
        self._jobject.file_path = ''
        datastore.write(self._jobject)

    def _internal_save_cb(self):
        logging.debug("Saved source object to datastore.")
        id = self._jobject.object_id
        service_name = 'org.laptop.AbiWordActivity'
        self._cleanup_jobject()        
        activityfactory.create_with_object_id(service_name, id)
            
    def _internal_save_error_cb(self, err):
        logging.debug("Error saving source object to datastore: %s" % err)
        self._cleanup_jobject()

    def _cleanup_jobject(self):
        if self._jobject:
            if os.path.isfile(self._jobject.file_path):
                logging.debug('_cleanup_jobject: removing %r' % self._jobject.file_path)
                os.remove(self._jobject.file_path)            
            self._jobject.destroy()
            self._jobject = None            
            
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

