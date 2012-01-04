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
from gi.repository import Gdk
from gi.repository import Pango
from gi.repository import WebKit

from sugar3 import env
from sugar3.activity import activity
from sugar3.graphics import style
from sugar3.graphics.icon import Icon

# FIXME
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
        if self.get_n_pages():
            self._update_closing_buttons()
            self._update_tab_sizes()

    def __new_tab_cb(self, browser, url):
        new_browser = self.add_tab(next_to_current=True)
        new_browser.load_uri(url)
        new_browser.grab_focus()

    def add_tab(self, next_to_current=False):
        browser = Browser()
        browser.connect('new-tab', self.__new_tab_cb)

        if next_to_current:
            self._insert_tab_next(browser)
        else:
            self._append_tab(browser)
        self.emit('focus-url-entry')
        browser.load_uri('about:blank')
        return browser

    def _insert_tab_next(self, browser):
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.add(browser)
        browser.show()

        label = TabLabel(scrolled_window)
        label.connect('tab-close', self.__tab_close_cb)

        next_index = self.get_current_page() + 1
        self.insert_page(scrolled_window, label, next_index)
        scrolled_window.show()
        self.set_current_page(next_index)

    def _append_tab(self, browser):
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.add(browser)
        browser.show()

        label = TabLabel(scrolled_window)
        label.connect('tab-close', self.__tab_close_cb)

        self.append_page(scrolled_window, label)
        scrolled_window.show()
        self.set_current_page(-1)

    def on_add_tab(self, gobject):
        self.add_tab()

    def __tab_close_cb(self, label, browser_window):
        self.remove_page(self.page_num(browser_window))
        browser_window.destroy()

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
        if self.get_n_pages() == 1:
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
            browser.load_uri('file://' + default_page)

    def _get_current_browser(self):
        if self.get_n_pages():
            return self.get_nth_page(self.get_current_page()).get_child()
        else:
            return None

    current_browser = GObject.property(type=object,
                                       getter=_get_current_browser)

    def get_history(self):
        tab_histories = []
        for index in xrange(0, self.get_n_pages()):
            scrolled_window = self.get_nth_page(index)
            browser = scrolled_window.get_child()
            tab_histories.append(browser.get_history())
        return tab_histories

    def set_history(self, tab_histories):
        if tab_histories and isinstance(tab_histories[0], dict):
           # Old format, no tabs
            tab_histories = [tab_histories]

        while self.get_n_pages():
            self.remove_page(self.get_n_pages() - 1)

        for tab_history in tab_histories:
            browser = Browser()
            browser.connect('new-tab', self.__new_tab_cb)
            self._append_tab(browser)
            browser.set_history(tab_history)


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

    def __init__(self, browser_window):
        GObject.GObject.__init__(self)

        self._browser_window = browser_window
        browser = browser_window.get_child()
        browser.connect('notify::title', self.__title_changed_cb)

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
        self.emit('tab-close', self._browser_window)

    def __title_changed_cb(self, widget, param):
        if widget.props.title:
            self._label.set_text(widget.props.title)


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
        WebKit.WebView.do_setup(self)
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

    def get_history(self):
        """Return the browsing history of this browser."""
        back_forward_list = self.get_back_forward_list()
        if back_forward_list.get_back_length() == 0:
            return ''

        items_list = self._items_history_as_list(back_forward_list)
        history = []
        for item in items_list:
            history.append({'url': item.get_uri(),
                            'title': item.get_title()})

        return history

    def set_history(self, history):
        """Restore the browsing history for this browser."""
        back_forward_list = self.get_back_forward_list()
        back_forward_list.clear()
        for entry in history:
            uri, title = entry['url'], entry['title']
            history_item = WebKit.WebHistoryItem.new_with_data(uri, title)
            back_forward_list.add_item(history_item)

    def get_history_index(self):
        """Return the index of the current item in the history."""
        back_forward_list = self.get_back_forward_list()
        history_list = self._items_history_as_list(back_forward_list)
        current_item = back_forward_list.get_current_item()
        return history_list.index(current_item)

    def set_history_index(self, index):
        """Go to the item in the history specified by the index."""
        back_forward_list = self.get_back_forward_list()
        if back_forward_list.get_back_length() != 0:
            current_item = index - back_forward_list.get_back_length()
            item = back_forward_list.get_nth_item(current_item)
            if item is not None:
                self.go_to_back_forward_item(item)

    def _items_history_as_list(self, history):
        """Return a list with the items of a WebKit.WebBackForwardList."""
        back_items = []
        for n in reversed(range(1, history.get_back_length() + 1)):
            item = history.get_nth_item(n * -1)
            back_items.append(item)

        current_item = [history.get_current_item()]

        forward_items = []
        for n in range(1, history.get_forward_length() + 1):
            item = history.get_nth_item(n)
            forward_items.append(item)

        all_items = back_items + current_item + forward_items
        return all_items

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

    def open_new_tab(self, url):
        self.emit('new-tab', url)


class PopupDialog(Gtk.Window):
    def __init__(self):
        GObject.GObject.__init__(self)

        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)

        border = style.GRID_CELL_SIZE
        self.set_default_size(Gdk.Screen.width() - border * 2,
                              Gdk.Screen.height() - border * 2)

        self.view = WebKit.WebView()
        self.view.connect('notify::visibility', self.__notify_visibility_cb)
        self.add(self.view)
        self.view.realize()

    def __notify_visibility_cb(self, web_view, pspec):
        if self.view.props.visibility:
            self.view.show()
            self.show()
