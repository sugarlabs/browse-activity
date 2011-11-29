# Copyright (C) 2006, Red Hat, Inc.
# Copyright (C) 2007, One Laptop Per Child
# Copyright (C) 2009, Tomeu Vizoso, Simon Schampijer
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
from gettext import gettext as _

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango
from gi.repository import WebKit

from sugar3 import env
from sugar3.activity import activity
from sugar3.graphics import style
from sugar3.graphics.icon import Icon

# FIXME
# import sessionstore
# from palettes import ContentInvoker
# from sessionhistory import HistoryListener
# from progresslistener import ProgressListener
from widgets import BrowserNotebook

_ZOOM_AMOUNT = 0.1
_LIBRARY_PATH = '/usr/share/library-common/index.html'


class SaveListener(object):
    def __init__(self, user_data, callback):
        self._user_data = user_data
        self._callback = callback

    def onStateChange(self, webProgress, request, stateFlags, status):
        listener_class = interfaces.nsIWebProgressListener
        if (stateFlags & listener_class.STATE_IS_REQUEST and
            stateFlags & listener_class.STATE_STOP):
            self._callback(self._user_data)

        # Contrary to the documentation, STATE_IS_REQUEST is _not_ always set
        # if STATE_IS_DOCUMENT is set.
        if (stateFlags & listener_class.STATE_IS_DOCUMENT and
            stateFlags & listener_class.STATE_STOP):
            self._callback(self._user_data)

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


class TabbedView(BrowserNotebook):
    __gtype_name__ = 'TabbedView'

    __gsignals__ = {
        'focus-url-entry': (GObject.SignalFlags.RUN_FIRST,
                            None,
                            ([])),
    }

    AGENT_SHEET = os.path.join(activity.get_bundle_path(),
                               'agent-stylesheet.css')
    USER_SHEET = os.path.join(env.get_profile_path(), 'gecko',
                              'user-stylesheet.css')

    def __init__(self):
        BrowserNotebook.__init__(self)

        self.props.show_border = False
        self.props.scrollable = True

        # FIXME
        # io_service_class = components.classes[ \
        #         "@mozilla.org/network/io-service;1"]
        # io_service = io_service_class.getService(interfaces.nsIIOService)

        # # Use xpcom to turn off "offline mode" detection, which disables
        # # access to localhost for no good reason.  (Trac #6250.)
        # io_service2 = io_service_class.getService(interfaces.nsIIOService2)
        # io_service2.manageOfflineStatus = False

        # cls = components.classes['@mozilla.org/content/style-sheet-service;1']
        # style_sheet_service = cls.getService(interfaces.nsIStyleSheetService)

        # if os.path.exists(TabbedView.AGENT_SHEET):
        #     agent_sheet_uri = io_service.newURI('file:///' +
        #                                         TabbedView.AGENT_SHEET,
        #                                         None, None)
        #     style_sheet_service.loadAndRegisterSheet(agent_sheet_uri,
        #             interfaces.nsIStyleSheetService.AGENT_SHEET)

        # if os.path.exists(TabbedView.USER_SHEET):
        #     url = 'file:///' + TabbedView.USER_SHEET
        #     user_sheet_uri = io_service.newURI(url, None, None)
        #     style_sheet_service.loadAndRegisterSheet(user_sheet_uri,
        #             interfaces.nsIStyleSheetService.USER_SHEET)

        # cls = components.classes['@mozilla.org/embedcomp/window-watcher;1']
        # window_watcher = cls.getService(interfaces.nsIWindowWatcher)
        # window_creator = xpcom.server.WrapObject(self,
        #                                          interfaces.nsIWindowCreator)
        # window_watcher.setWindowCreator(window_creator)

        self.connect('size-allocate', self.__size_allocate_cb)
        self.connect('page-added', self.__page_added_cb)
        self.connect('page-removed', self.__page_removed_cb)

        self.add_tab()
        self._update_closing_buttons()
        self._update_tab_sizes()

    def createChromeWindow(self, parent, flags):
        if flags & interfaces.nsIWebBrowserChrome.CHROME_OPENAS_CHROME:
            dialog = PopupDialog()
            dialog.view.is_chrome = True

            parent_dom_window = parent.webBrowser.contentDOMWindow
            parent_view = hulahop.get_view_for_window(parent_dom_window)
            if parent_view:
                dialog.set_transient_for(parent_view.get_toplevel())

            browser = dialog.view.browser

            item = browser.queryInterface(interfaces.nsIDocShellTreeItem)
            item.itemType = interfaces.nsIDocShellTreeItem.typeChromeWrapper

            return browser.containerWindow
        else:
            browser = Browser()
            browser.connect('new-tab', self.__new_tab_cb)
            self._append_tab(browser)

            return browser.browser.containerWindow

    def __size_allocate_cb(self, widget, allocation):
        self._update_tab_sizes()

    def __page_added_cb(self, notebook, child, pagenum):
        self._update_closing_buttons()
        self._update_tab_sizes()

    def __page_removed_cb(self, notebook, child, pagenum):
        self._update_closing_buttons()
        self._update_tab_sizes()

    def __new_tab_cb(self, browser, url):
        new_browser = self.add_tab(next_to_current=True)
        new_browser.load_uri(url)
        new_browser.grab_focus()

    def add_tab(self, next_to_current=False):
        browser = Browser()
        browser.connect('new-tab', self.__new_tab_cb)

        label = TabLabel(browser)
        label.connect('tab-close', self.__tab_close_cb)

        if next_to_current:
            self._insert_tab_next(browser)
        else:
            self._append_tab(browser)
        self.emit('focus-url-entry')
        browser.load_uri('about:blank')
        return browser

    def _insert_tab_next(self, browser):
        label = TabLabel(browser)
        label.connect('tab-close', self.__tab_close_cb)

        next_index = self.get_current_page() + 1
        self.insert_page(browser, label, next_index)
        browser.show()
        self.set_current_page(next_index)

    def _append_tab(self, browser):
        label = TabLabel(browser)
        label.connect('tab-close', self.__tab_close_cb)

        self.append_page(browser, label)
        browser.show()
        self.set_current_page(-1)

    def on_add_tab(self, gobject):
        self.add_tab()

    def __tab_close_cb(self, label, browser):
        self.remove_page(self.page_num(browser))
        browser.destroy()

    def _update_tab_sizes(self):
        """Update ta widths based in the amount of tabs."""

        n_pages = self.get_n_pages()
        canvas_size = self.get_allocation()
        # FIXME
        # overlap_size = self.style_get_property('tab-overlap') * n_pages - 1
        overlap_size = 0
        allowed_size = canvas_size.width - overlap_size

        tab_new_size = int(allowed_size * 1.0 / (n_pages + 1))
        # Four tabs ensured:
        tab_max_size = int(allowed_size * 1.0 / (5))
        # Eight tabs ensured:
        tab_min_size = int(allowed_size * 1.0 / (9))

        if tab_new_size < tab_min_size:
            tab_new_size = tab_min_size
        elif tab_new_size > tab_max_size:
            tab_new_size = tab_max_size

        for page_idx in range(n_pages):
            page = self.get_nth_page(page_idx)
            label = self.get_tab_label(page)
            label.update_size(tab_new_size)

    def _update_closing_buttons(self):
        """Prevent closing the last tab."""
        first_page = self.get_nth_page(0)
        first_label = self.get_tab_label(first_page)
        if self.get_n_pages() == 0:
            return
        elif self.get_n_pages() == 1:
            first_label.hide_close_button()
        else:
            first_label.show_close_button()

    def load_homepage(self):
        browser = self.current_browser

        if os.path.isfile(_LIBRARY_PATH):
            browser.load_uri('file://' + _LIBRARY_PATH)
        else:
            default_page = os.path.join(activity.get_bundle_path(),
                                        "data/index.html")
            browser.load_uri(default_page)

    def _get_current_browser(self):
        return self.get_nth_page(self.get_current_page())

    current_browser = GObject.property(type=object,
                                       getter=_get_current_browser)

    def get_session(self):
        tab_sessions = []
        for index in xrange(0, self.get_n_pages()):
            browser = self.get_nth_page(index)
            tab_sessions.append(sessionstore.get_session(browser))
        return tab_sessions

    def set_session(self, tab_sessions):
        if tab_sessions and isinstance(tab_sessions[0], dict):
            # Old format, no tabs
            tab_sessions = [tab_sessions]

        while self.get_n_pages():
            self.remove_page(self.get_n_pages() - 1)

        for tab_session in tab_sessions:
            browser = Browser()
            browser.connect('new-tab', self.__new_tab_cb)
            self._append_tab(browser)
            sessionstore.set_session(browser, tab_session)


Gtk.rc_parse_string('''
    style "browse-tab-close" {
        xthickness = 0
        ythickness = 0
    }
    widget "*browse-tab-close" style "browse-tab-close"''')


class TabLabel(Gtk.HBox):
    __gtype_name__ = 'TabLabel'

    __gsignals__ = {
        'tab-close': (GObject.SignalFlags.RUN_FIRST,
                      None,
                      ([object])),
    }

    def __init__(self, browser):
        GObject.GObject.__init__(self)

        self._browser = browser
        self._browser.connect('is-setup', self.__browser_is_setup_cb)

        self._label = Gtk.Label(label=_('Untitled'))
        self._label.set_ellipsize(Pango.EllipsizeMode.END)
        self._label.set_alignment(0, 0.5)
        self.pack_start(self._label, True, True, 0)
        self._label.show()

        close_tab_icon = Icon(icon_name='browse-close-tab')
        button = Gtk.Button()
        button.props.relief = Gtk.ReliefStyle.NONE
        button.props.focus_on_click = False
        icon_box = Gtk.HBox()
        icon_box.pack_start(close_tab_icon, True, False, 0)
        button.add(icon_box)
        button.connect('clicked', self.__button_clicked_cb)
        button.set_name('browse-tab-close')
        self.pack_start(button, False, True, 0)
        close_tab_icon.show()
        icon_box.show()
        button.show()
        self._close_button = button

    def update_size(self, size):
        self.set_size_request(size, -1)

    def hide_close_button(self):
        self._close_button.hide()

    def show_close_button(self):
        self._close_button.show()

    def __button_clicked_cb(self, button):
        self.emit('tab-close', self._browser)

    def __browser_is_setup_cb(self, browser):
        browser.progress.connect('notify::location',
                                 self.__location_changed_cb)
        browser.connect('notify::title', self.__title_changed_cb)

    def __location_changed_cb(self, progress_listener, pspec):
        url = self._browser.get_url_from_nsiuri(progress_listener.location)
        if url == 'about:blank':
            self._label.set_text(_('Loading...'))
        else:
            self._label.set_text(url)

    def __title_changed_cb(self, browser, pspec):
        if browser.props.title == "":
            self._label.set_text(_('Untitled'))
        else:
            self._label.set_text(browser.props.title)


class Browser(WebKit.WebView):
    __gtype_name__ = 'Browser'

    __gsignals__ = {
        'is-setup': (GObject.SignalFlags.RUN_FIRST,
                     None,
                     ([])),
        'new-tab': (GObject.SignalFlags.RUN_FIRST,
                    None,
                    ([str])),
    }

    def __init__(self):
        WebKit.WebView.__init__(self)

        # FIXME
        # self.history = HistoryListener()
        # self.progress = ProgressListener()

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

        self.emit('is-setup')

    def get_url_from_nsiuri(self, uri):
        """
        get a nsIURI object and return a string with the url
        """
        if uri == None:
            return ''
        cls = components.classes['@mozilla.org/intl/texttosuburi;1']
        texttosuburi = cls.getService(interfaces.nsITextToSubURI)
        return texttosuburi.unEscapeURIForUI(uri.originCharset, uri.spec)

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

        progresslistener = SaveListener(file_path, async_cb)
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

    def get_history_index(self):
        return self.web_navigation.sessionHistory.index

    def set_history_index(self, index):
        if index == -1:
            return
        self.web_navigation.gotoIndex(index)

    def open_new_tab(self, url):
        self.emit('new-tab', url)


class PopupDialog(Gtk.Window):
    def __init__(self):
        GObject.GObject.__init__(self)

        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)

        border = style.GRID_CELL_SIZE
        self.set_default_size(Gdk.Screen.width() - border * 2,
                              Gdk.Screen.height() - border * 2)

        self.view = WebView()
        self.view.connect('notify::visibility', self.__notify_visibility_cb)
        self.add(self.view)
        self.view.realize()

    def __notify_visibility_cb(self, web_view, pspec):
        if self.view.props.visibility:
            self.view.show()
            self.show()
