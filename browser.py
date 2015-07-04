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
import re
import logging

from gettext import gettext as _

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import Gdk
from gi.repository import Pango
from gi.repository import WebKit2
from gi.repository import Soup
from gi.repository import GConf

import jarabe.config
from sugar3.activity import activity
from sugar3.graphics import style
from sugar3.graphics.icon import Icon
from sugar3.graphics.alert import ConfirmationAlert

from widgets import BrowserNotebook
from palettes import ContentInvoker
from filepicker import FilePicker
import globalhistory
import downloadmanager
from pdfviewer import PDFTabPage

ZOOM_ORIGINAL = 1.0
_ZOOM_AMOUNT = 0.1
LIBRARY_PATH = '/usr/share/library-common/index.html'

_WEB_SCHEMES = ['http', 'https', 'ftp', 'file', 'javascript', 'data',
                'about', 'gopher', 'mailto']

_NON_SEARCH_REGEX = re.compile('''
    (^localhost(\\.[^\s]+)?(:\\d+)?(/.*)?$|
    ^[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]$|
    ^::[0-9a-f:]*$|                         # IPv6 literals
    ^[0-9a-f:]+:[0-9a-f:]*$|                # IPv6 literals
    ^[^\\.\s]+\\.[^\\.\s]+.*$|              # foo.bar...
    ^https?://[^/\\.\s]+.*$|
    ^about:.*$|
    ^data:.*$|
    ^file:.*$)
    ''', re.VERBOSE)
_HOSTNAME_REGEX = re.compile('[a-z]+://([^/]+)/.*')

DEFAULT_ERROR_PAGE = os.path.join(activity.get_bundle_path(),
                                  'data/error_page.tmpl')

HOME_PAGE_GCONF_KEY = '/desktop/sugar/browser/home_page'


class TabbedView(BrowserNotebook):
    __gtype_name__ = 'TabbedView'

    __gsignals__ = {
        'focus-url-entry': (GObject.SignalFlags.RUN_FIRST,
                            None,
                            ([])),
    }

    def __init__(self, activity):
        self._activity = activity
        BrowserNotebook.__init__(self)
        self.props.show_border = False
        self.props.scrollable = True

        # Used to connect and disconnect functions when 'switch-page'
        self._browser = None
        self._load_status_changed_hid = None

        self.connect('size-allocate', self.__size_allocate_cb)
        self.connect('page-added', self.__page_added_cb)
        self.connect('page-removed', self.__page_removed_cb)

        self.connect_after('switch-page', self.__switch_page_cb)

        self.add_tab()
        self._update_closing_buttons()
        self._update_tab_sizes()

    def __switch_page_cb(self, tabbed_view, page, page_num):
        if tabbed_view.get_n_pages():
            self._connect_to_browser(tabbed_view.props.current_browser)

    def _connect_to_browser(self, browser):
        if self._browser is not None:
            self._browser.disconnect(self._load_status_changed_hid)

        self._browser = browser
        self._load_status_changed_hid = self._browser.connect(
            'load-changed', self.__load_changed_cb)

    def normalize_or_autosearch_url(self, url):
        """Normalize the url input or return a url for search.

        We use SoupURI as an indication of whether the value given in url
        is not something we want to search; we only do that, though, if
        the address has a web scheme, because SoupURI will consider any
        string: as a valid scheme, and we will end up prepending http://
        to it.

        This code is borrowed from Epiphany.

        url -- input string that can be normalized to an url or serve
               as search

        Return: a string containing a valid url

        """
        def has_web_scheme(address):
            if address == '':
                return False

            scheme, sep, after = address.partition(':')
            if sep == '':
                return False

            return scheme in _WEB_SCHEMES

        soup_uri = None
        effective_url = None

        if has_web_scheme(url):
            try:
                soup_uri = Soup.URI.new(url)
            except TypeError:
                pass

        if soup_uri is None and not _NON_SEARCH_REGEX.match(url):
            # Get the user's LANG to use as default language of
            # the results
            locale = os.environ.get('LANG', '')
            language_location = locale.split('.', 1)[0].lower()
            language = language_location.split('_')[0]
            # If the string doesn't look like an URI, let's search it:
            url_search = 'http://www.google.com/search?' \
                'q=%(query)s&ie=UTF-8&oe=UTF-8&hl=%(language)s'
            query_param = Soup.form_encode_hash({'q': url})
            # [2:] here is getting rid of 'q=':
            effective_url = url_search % {'query': query_param[2:],
                                          'language': language}
        else:
            if has_web_scheme(url):
                effective_url = url
            else:
                effective_url = 'http://' + url

        return effective_url

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

    def __create_web_view_cb(self, web_view, frame):
        new_web_view = Browser(self._activity)
        new_web_view.connect('ready-to-show', self.__web_view_ready_cb)
        return new_web_view

    def __web_view_ready_cb(self, web_view):
        """
        Handle new window requested and open it in a new tab.

        This callback is called when the WebKit2.WebView request for a
        new window to open (for example a call to the Javascript
        function 'window.open()' or target="_blank")

        web_view -- the new browser there the url of the
                    window.open() call will be loaded.

                    This object is created in the signal callback
                    'create-web-view'.
        """

        web_view.connect('new-tab', self.__new_tab_cb)
        web_view.connect('open-pdf', self.__open_pdf_in_new_tab_cb)
        web_view.connect('create', self.__create_web_view_cb)
        web_view.grab_focus()

        self._insert_tab_next(web_view)

    def __open_pdf_in_new_tab_cb(self, browser, url):
        tab_page = PDFTabPage()
        tab_page.browser.connect('new-tab', self.__new_tab_cb)
        tab_page.browser.connect('tab-close', self.__tab_close_cb)

        label = TabLabel(tab_page.browser)
        label.connect('tab-close', self.__tab_close_cb, tab_page)

        next_index = self.get_current_page() + 1
        self.insert_page(tab_page, label, next_index)
        tab_page.show()
        label.show()
        self.set_current_page(next_index)
        tab_page.setup(url)

    def __load_changed_cb(self, widget, status):
        if self.get_window() is None:
            return

        if widget.props.estimated_load_progress < 1.0 and widget.props.uri:
            self.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.WATCH))
        else:
            self.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.LEFT_PTR))

    def add_tab(self, next_to_current=False):
        browser = Browser(self._activity)
        browser.connect('new-tab', self.__new_tab_cb)
        browser.connect('open-pdf', self.__open_pdf_in_new_tab_cb)
        browser.connect('ready-to-show', self.__web_view_ready_cb)
        browser.connect('create', self.__create_web_view_cb)

        if next_to_current:
            self._insert_tab_next(browser)
        else:
            self._append_tab(browser)
        self.emit('focus-url-entry')
        return browser

    def _insert_tab_next(self, browser):
        tab_page = TabPage(browser)
        label = TabLabel(browser)
        label.connect('tab-close', self.__tab_close_cb, tab_page)

        next_index = self.get_current_page() + 1
        self.insert_page(tab_page, label, next_index)
        tab_page.show()
        self.set_current_page(next_index)

    def _append_tab(self, browser):
        tab_page = TabPage(browser)
        label = TabLabel(browser)
        label.connect('tab-close', self.__tab_close_cb, tab_page)

        self.append_page(tab_page, label)
        tab_page.show()
        self.set_current_page(-1)

    def on_add_tab(self, gobject):
        self.add_tab()

    def close_tab(self, tab_page=None):
        if self.get_n_pages() == 1:
            return

        if tab_page is None:
            tab_page = self.get_nth_page(self.get_current_page())

        if isinstance(tab_page, PDFTabPage):
            tab_page.cancel_download()

        self.remove_page(self.page_num(tab_page))

        current_page = self.get_nth_page(self.get_current_page())
        current_page.props.browser.grab_focus()

    def __tab_close_cb(self, label, tab_page):
        self.close_tab(tab_page)

    def _update_tab_sizes(self):
        """Update tab widths based in the amount of tabs."""

        n_pages = self.get_n_pages()
        canvas_size = self.get_allocation()
        allowed_size = canvas_size.width
        if n_pages == 1:
            # use half of the whole space
            tab_expand = False
            tab_new_size = int(allowed_size / 2)
        elif n_pages <= 8:  # ensure eight tabs
            tab_expand = True  # use all the space available by tabs
            tab_new_size = -1
        else:
            # scroll the tab toolbar if there are more than 8 tabs
            tab_expand = False
            tab_new_size = (allowed_size / 8)

        for page_idx in range(n_pages):
            page = self.get_nth_page(page_idx)
            label = self.get_tab_label(page)
            self.child_set_property(page, 'tab-expand', tab_expand)
            label.update_size(tab_new_size)

    def _update_closing_buttons(self):
        """Prevent closing the last tab."""
        first_page = self.get_nth_page(0)
        first_label = self.get_tab_label(first_page)
        if self.get_n_pages() == 1:
            first_label.hide_close_button()
        else:
            first_label.show_close_button()

    def load_homepage(self, ignore_gconf=False):
        browser = self.current_browser
        uri_homepage = None
        if not ignore_gconf:
            client = GConf.Client.get_default()
            uri_homepage = client.get_string(HOME_PAGE_GCONF_KEY)
        if uri_homepage is not None:
            browser.load_uri(uri_homepage)
        elif os.path.isfile(LIBRARY_PATH):
            browser.load_uri('file://' + LIBRARY_PATH)
        else:
            default_page = os.path.join(activity.get_bundle_path(),
                                        "data/index.html")
            browser.load_uri('file://' + default_page)
        browser.grab_focus()

    def set_homepage(self):
        uri = self.current_browser.get_uri()
        client = GConf.Client.get_default()
        client.set_string(HOME_PAGE_GCONF_KEY, uri)

    def reset_homepage(self):
        client = GConf.Client.get_default()
        client.unset(HOME_PAGE_GCONF_KEY)

    def _get_current_browser(self):
        if self.get_n_pages():
            return self.get_nth_page(self.get_current_page()).browser
        else:
            return None

    current_browser = GObject.property(type=object,
                                       getter=_get_current_browser)

    def get_history(self):
        tab_histories = []
        for index in xrange(0, self.get_n_pages()):
            tab_page = self.get_nth_page(index)
            tab_histories.append(tab_page.browser.get_history())
        return tab_histories

    def set_history(self, tab_histories):
        if tab_histories and isinstance(tab_histories[0], dict):
            # Old format, no tabs
            tab_histories = [tab_histories]

        while self.get_n_pages():
            self.remove_page(self.get_n_pages() - 1)

        def is_pdf_history(tab_history):
            return (len(tab_history) == 1 and
                    tab_history[0]['url'].lower().endswith('pdf'))

        for tab_history in tab_histories:
            if is_pdf_history(tab_history):
                url = tab_history[0]['url']
                tab_page = PDFTabPage()
                tab_page.browser.connect('new-tab', self.__new_tab_cb)
                tab_page.browser.connect('tab-close', self.__tab_close_cb)

                label = TabLabel(tab_page.browser)
                label.connect('tab-close', self.__tab_close_cb, tab_page)

                self.append_page(tab_page, label)
                tab_page.show()
                label.show()
                tab_page.setup(url, title=tab_history[0]['title'])

            else:
                browser = Browser(self._activity)
                browser.connect('new-tab', self.__new_tab_cb)
                browser.connect('open-pdf', self.__open_pdf_in_new_tab_cb)
                browser.connect('ready-to-show', self.__web_view_ready_cb)
                browser.connect('create', self.__create_web_view_cb)
                self._append_tab(browser)
                browser.set_history(tab_history)

    def is_current_page_pdf(self):
        index = self.get_current_page()
        current_page = self.get_nth_page(index)
        return isinstance(current_page, PDFTabPage)


Gtk.rc_parse_string('''
    style "browse-tab-close" {
        xthickness = 0
        ythickness = 0
    }
    widget "*browse-tab-close" style "browse-tab-close"''')


class TabPage(Gtk.ScrolledWindow):
    __gtype_name__ = 'BrowseTabPage'

    def __init__(self, browser):
        GObject.GObject.__init__(self)

        self._browser = browser
        self._browser.connect('web-process-crashed', self.__crashed_cb)

        self.add(browser)
        browser.show()

    def _get_browser(self):
        return self._browser

    browser = GObject.property(type=object,
                               getter=_get_browser)

    def __crashed_cb(self, webview):
        self._show_message(
            _('WebKit has crashed'),
            _('WebKit was unable to display this page.  Try reloading this'
              ' page or navigating to a different page if the issue'
              ' persists'))

    def _show_message(self, title, message):
        # Copy 'n' paste reuse from the journal :)
        self.remove(self.get_child())

        background_box = Gtk.EventBox()
        background_box.modify_bg(Gtk.StateType.NORMAL,
                                 style.COLOR_WHITE.get_gdk_color())
        self.add(background_box)

        alignment = Gtk.Alignment.new(0.5, 0.5, 0.1, 0.1)
        background_box.add(alignment)

        box = Gtk.VBox()
        alignment.add(box)

        icon = Icon(pixel_size=style.LARGE_ICON_SIZE,
                    icon_name='emblem-warning',
                    stroke_color=style.COLOR_BUTTON_GREY.get_svg(),
                    fill_color=style.COLOR_TRANSPARENT.get_svg())
        box.pack_start(icon, expand=True, fill=False, padding=0)

        label = Gtk.Label()
        color = style.COLOR_BUTTON_GREY.get_html()
        label.set_markup(
            '<span weight="bold" color="%s">%s</span>' % (
                color, GLib.markup_escape_text(title)))
        box.pack_start(label, expand=True, fill=False, padding=0)

        label = Gtk.Label()
        label.set_markup(message)
        box.pack_start(label, expand=True, fill=False, padding=0)

        background_box.show_all()


class TabLabel(Gtk.HBox):
    __gtype_name__ = 'BrowseTabLabel'

    __gsignals__ = {
        'tab-close': (GObject.SignalFlags.RUN_FIRST,
                      None,
                      ([])),
    }

    def __init__(self, browser):
        GObject.GObject.__init__(self)

        browser.connect('notify::title', self.__title_changed_cb)
        browser.connect('load-changed', self.__load_changed_cb)

        self._title = _('Untitled')
        self._label = Gtk.Label(label=self._title)
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
        self.emit('tab-close')

    def __title_changed_cb(self, widget, param):
        title = widget.props.title
        if not title:
            title = os.path.basename(widget.props.uri)

        self._label.set_text(title)
        self._title = title

    def __load_changed_cb(self, widget, status):
        if status == WebKit2.LoadEvent.FINISHED:
            if widget.props.title is None:
                self._label.set_text(_('Untitled'))
                self._title = _('Untitled')
        else:
            self._label.set_text(_('Loading...'))


class Browser(WebKit2.WebView):
    __gtype_name__ = 'Browser'

    __gsignals__ = {
        'new-tab': (GObject.SignalFlags.RUN_FIRST,
                    None,
                    ([str])),
        'open-pdf': (GObject.SignalFlags.RUN_FIRST,
                     None,
                     ([str])),
        'security-status-changed': (GObject.SignalFlags.RUN_FIRST,
                                    None,
                                    ([])),
    }

    SECURITY_STATUS_SECURE = 1
    SECURITY_STATUS_INSECURE = 2

    def __init__(self, activity):
        WebKit2.WebView.__init__(self)
        self._activity = activity
        web_settings = self.get_settings()

        # Add SugarLabs user agent:
        identifier = ' SugarLabs/' + jarabe.config.version
        web_settings.props.user_agent += identifier

        # Change font size based in the GtkSettings font size.  The
        # gtk-font-name property is a string with format '[font name]
        # [font size]' like 'Sans Serif 10'.
        gtk_settings = Gtk.Settings.get_default()
        gtk_font_name = gtk_settings.get_property('gtk-font-name')
        gtk_font_size = float(gtk_font_name.split()[-1])
        web_settings.props.default_font_size = gtk_font_size * 1.2
        web_settings.props.default_monospace_font_size = \
            gtk_font_size * 1.2 - 2

        self.set_settings(web_settings)

        context = self.get_context()
        context.connect('download-started', self.__download_requested_cb)

        # Scale text and graphics:
        # TODO PORT
        # self.set_full_content_zoom(True)

        # This property is used to set the title immediatly the user
        # presses Enter on the URL Entry
        self.loading_uri = None

        self.security_status = None

        # Reference to the global history and callbacks to handle it:
        self._global_history = globalhistory.get_global_history()
        self.connect('load-changed', self.__load_changed_cb)
        self.connect('notify::title', self.__title_changed_cb)
        self.connect('decide-policy', self.__decide_policy_cb)
        self.connect('permission-request', self.__permission_request_cb)

        # self.connect('load-error', self.__load_error_cb)

        self._inject_media_style = False

        ContentInvoker(self)

        try:
            self.connect('run-file-chooser', self.__run_file_chooser)
        except TypeError:
            # Only present in WebKit1 > 1.9.3 and WebKit2
            pass

    def get_history(self):
        """Return the browsing history of this browser."""
        back_forward_list = self.get_back_forward_list()
        items_list = self._items_history_as_list(back_forward_list)

        # If this is an empty tab, return an empty history:
        if len(items_list) == 1 and items_list[0] is None:
            return []

        history = []
        for item in items_list:
            history.append({'url': item.get_uri(),
                            'title': item.get_title()})

        return history

    def set_history(self, history):
        """Restore the browsing history for this browser."""
        pass
        # TODO PORT: how create objects for the history
        # is not possible set the title and url
        """
        back_forward_list = self.get_back_forward_list()
        # back_forward_list.clear()
        for entry in history:
            uri, title = entry['url'], entry['title']
            history_item = WebKit2.BackForwardHistoryItem()
            # history_item WebHistoryItem.new_with_data(uri, title)
            # back_forward_list.add_item(history_item)
        """

    def get_history_index(self):
        """Return the index of the current item in the history."""
        back_forward_list = self.get_back_forward_list()
        history_list = self._items_history_as_list(back_forward_list)
        current_item = back_forward_list.get_current_item()
        return history_list.index(current_item)

    def set_history_index(self, index):
        """Go to the item in the history specified by the index."""
        back_forward_list = self.get_back_forward_list()
        current_item = index - back_forward_list.get_length()
        item = back_forward_list.get_nth_item(current_item)
        if item is not None:
            self.go_to_back_forward_list_item(item)

    def _items_history_as_list(self, history):
        """Return a list with the items of a WebKit2.WebBackForwardList."""
        all_items = []

        for item in reversed(history.get_back_list()):
            all_items.append(item)

        all_items.append(history.get_current_item())

        for item in history.get_forward_list():
            all_items.append(item)

        return all_items

    def get_source(self, async_cb, async_err_cb):
        data_source = self.get_main_frame().get_data_source()
        data = data_source.get_data()
        if data_source.is_loading() or data is None:
            async_err_cb()
        temp_path = os.path.join(activity.get_activity_root(), 'instance')
        file_path = os.path.join(temp_path, '%i' % time.time())

        file_handle = file(file_path, 'w')
        file_handle.write(data.str)
        file_handle.close()
        async_cb(file_path)

    def open_new_tab(self, url):
        self.emit('new-tab', url)

    def __run_file_chooser(self, browser, request):
        picker = FilePicker(self)
        chosen = picker.run()
        picker.destroy()

        if chosen:
            request.select_files([chosen])
        elif hasattr(request, 'cancel'):
            # WebKit2 only
            request.cancel()
        return True

    def __load_changed_cb(self, widget, status):
        if status <= WebKit2.LoadEvent.COMMITTED:
            # Add the url to the global history or update it.
            uri = self.get_uri()
            self._global_history.add_page(uri)

        if status == WebKit2.LoadEvent.COMMITTED:
            # Update the security status.
            bool_, cert, errors = widget.get_tls_info()
            if cert:
                if not errors:
                    self.security_status = self.SECURITY_STATUS_SECURE
                else:
                    self.security_status = self.SECURITY_STATUS_INSECURE
            else:
                self.security_status = None
            self.emit('security-status-changed')

    def __title_changed_cb(self, widget, param):
        """Update title in global history."""
        uri = self.get_uri()
        if self.props.title is not None:
            title = self.props.title
            if not isinstance(title, unicode):
                title = unicode(title, 'utf-8')
            self._global_history.set_page_title(uri, title)

    def __decide_policy_cb(self, webview, policy_decision, decision_type):
        """Handle downloads and PDF files."""

        if decision_type != WebKit2.PolicyDecisionType.RESPONSE:
            return False

        response = WebKit2.ResponsePolicyDecision.get_response(policy_decision)
        mimetype = WebKit2.URIResponse.get_mime_type(response)

        if mimetype == 'application/pdf':
            self.emit('open-pdf', response.get_uri())
            policy_decision.ignore()
            return True

        elif mimetype == 'audio/x-vorbis+ogg' or mimetype == 'audio/mpeg':
            self._inject_media_style = True

        elif not self.can_show_mime_type(mimetype):
            policy_decision.download()
            return True

        return False

    def __download_requested_cb(self, context, download):
        logging.error('__download_requested_cb')
        downloadmanager.add_download(download, self._activity)
        return True

    def __load_error_cb(self, web_view, web_frame, uri, web_error):
        """Show Sugar's error page"""

        # Don't show error page if the load was interrupted by policy
        # change or the request is going to be handled by a
        # plugin. For example, if a file was requested for download or
        # an .ogg file is going to be played.
        if web_error.code in (
                WebKit2.PolicyError.FRAME_LOAD_INTERRUPTED_BY_POLICY_CHANGE,
                WebKit2.PluginError.WILL_HANDLE_LOAD):
            if self._inject_media_style:
                css_style_file = open(os.path.join(activity.get_bundle_path(),
                                                   "data/media-controls.css"))
                css_style = css_style_file.read().replace('\n', '')
                inject_style_script = \
                    "var style = document.createElement('style');" \
                    "style.innerHTML = '%s';" \
                    "document.body.appendChild(style);" % css_style
                web_view.execute_script(inject_style_script)
            return True

        data = {
            'page_title': _('This web page could not be loaded'),
            'title': _('This web page could not be loaded'),
            'message': _('"%s" could not be loaded. Please check for '
                         'typing errors, and make sure you are connected '
                         'to the Internet.') % uri,
            'btn_value': _('Try again'),
            'url': uri,
            }

        html = open(DEFAULT_ERROR_PAGE, 'r').read() % data
        web_frame.load_alternate_html(html, uri, uri)

        return True

    def _get_permission_name(self, request):
        if hasattr(WebKit2, 'GeolocationPermissionRequest') and \
           isinstance(request, WebKit2.GeolocationPermissionRequest):
            return _('access to you location')
        if hasattr(WebKit2, 'NotificationPermissionRequest') and \
           isinstance(request, WebKit2.NotificationPermissionRequest):
            return _('to display notifications in the frame')
        # Should never be reached
        return type(request).__name__

    def __permission_request_cb(self, webview, request):
        description = self._get_permission_name(request)
        site = webview.get_uri()
        match = _HOSTNAME_REGEX.match(site)
        if match:
            site = match.group(1)

        alert = ConfirmationAlert()
        alert.props.title = _('Allow %s to %s?') % \
            (site, description)
        alert.props.msg = _('You can change your choice later by reloading the page')
        alert.connect('response', self.__permission_request_alert_cb, request)
        self._activity.add_alert(alert)

        # Allow async handeling
        return True

    def __permission_request_alert_cb(self, alert, response_id, request):
        self._activity.remove_alert(alert)

        if response_id == Gtk.ResponseType.OK:
            request.allow()
        elif response_id == Gtk.ResponseType.CANCEL:
            request.deny()

class PopupDialog(Gtk.Window):
    def __init__(self):
        GObject.GObject.__init__(self)

        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)

        border = style.GRID_CELL_SIZE
        self.set_default_size(Gdk.Screen.width() - border * 2,
                              Gdk.Screen.height() - border * 2)

        self.view = WebKit2.WebView()
        self.view.connect('notify::visibility', self.__notify_visibility_cb)
        self.add(self.view)
        self.view.realize()

    def __notify_visibility_cb(self, web_view, pspec):
        if self.view.props.visibility:
            self.view.show()
            self.show()
