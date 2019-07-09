# Copyright (C) 2006, Red Hat, Inc.
# Copyright (C) 2007, One Laptop Per Child
# Copyright (C) 2009, Tomeu Vizoso
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
from gettext import gettext as _

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import Pango

from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics.toggletoolbutton import ToggleToolButton
from sugar3.graphics import iconentry
from sugar3.graphics.toolbarbox import ToolbarBox as ToolbarBase
from sugar3.graphics.palettemenu import PaletteMenuItem
from sugar3.graphics.palettemenu import PaletteMenuBox
from sugar3.graphics import style
from sugar3.activity.widgets import ActivityToolbarButton
from sugar3.activity.widgets import StopButton

import filepicker
import places
import downloadmanager
from browser import Browser
from browser import SETTINGS_KEY_HOME_PAGE, LIBRARY_PATH
from progresstoolbutton import ProgressToolButton

from pdfviewer import DummyBrowser

_MAX_HISTORY_ENTRIES = 15
_SEARCH_ENTRY_MARGIN = style.zoom(14)


class _SearchWindow(Gtk.Window):
    """A search window that can be styled in the theme."""

    __gtype_name__ = "BrowseSearchWindow"

    def __init__(self):
        Gtk.Window.__init__(self, type=Gtk.WindowType.POPUP)
        self.get_style_context().add_class('search-window')


screen = Gdk.Screen.get_default()
css_provider = Gtk.CssProvider.get_default()
css = ('''
@define-color button_grey #808080;

.search-window treeview {{
    background: black;
    color: white;
    border-color: @button_grey;
    border-width: 0 {thickness}px {thickness}px {thickness}px;
    border-style: solid;
}}

.search-window treeview:selected {{
    background: @button_grey;
}}

.connected-entry {{
    background: black;
    border-color: @button_grey;
    border-width: {thickness}px {thickness}px 0 {thickness}px;
    border-style: solid;
}}

.search-window scrollbar trough {{
    background: black;
}}

.search-window scrollbar {{
    border: {thickness}px solid @button_grey;
    border-left: none;
}}
'''.format(thickness=style.LINE_WIDTH))
css_provider.load_from_data(css.encode('utf-8'))
context = Gtk.StyleContext()
context.add_provider_for_screen(screen, css_provider,
                                Gtk.STYLE_PROVIDER_PRIORITY_USER)


class WebEntry(iconentry.IconEntry):
    _COL_ADDRESS = 1
    _COL_TITLE = 0

    def __init__(self):
        GObject.GObject.__init__(self)

        self._address = None
        self._search_view = self._search_create_view()

        self._search_window = _SearchWindow()
        self._search_window_scroll = Gtk.ScrolledWindow()
        self._search_window_scroll.set_policy(Gtk.PolicyType.NEVER,
                                              Gtk.PolicyType.AUTOMATIC)
        self._search_window_scroll.set_min_content_height(200)
        self._search_window_scroll.add(self._search_view)
        self._search_window.add(self._search_window_scroll)
        self._search_view.show()
        self._search_window_scroll.show()

        self.connect('focus-in-event', self.__focus_in_event_cb)
        self.connect('populate-popup', self.__populate_popup_cb)
        self.connect('key-press-event', self.__key_press_event_cb)
        self._focus_out_hid = self.connect(
            'focus-out-event', self.__focus_out_event_cb)
        self._change_hid = self.connect('changed', self.__changed_cb)

    def _set_text(self, text):
        """Set the text but block changes notification, so that we can
           recognize changes caused directly by user actions"""
        self.handler_block(self._change_hid)
        try:
            self.props.text = text
        finally:
            self.handler_unblock(self._change_hid)

    def activate(self, uri):
        self._set_text(uri)
        self._search_popdown()
        self.emit('activate')

    def _set_address(self, address):
        self._address = address
        if address is not None:
            self._set_text(address)

    address = GObject.property(type=str, setter=_set_address)

    def _search_create_view(self):
        view = Gtk.TreeView()
        view.props.headers_visible = False

        view.connect('button-press-event', self.__view_button_press_event_cb)

        column = Gtk.TreeViewColumn()
        view.append_column(column)

        cell = Gtk.CellRendererText()
        cell.props.ellipsize = Pango.EllipsizeMode.END
        cell.props.ellipsize_set = True
        cell.props.height = style.STANDARD_ICON_SIZE
        cell.props.xpad = _SEARCH_ENTRY_MARGIN
        column.pack_start(cell, True)

        column.add_attribute(cell, 'markup', self._COL_TITLE)

        return view

    def _search_update(self):
        list_store = Gtk.ListStore(str, str)

        search_text = self.props.text
        for place in places.get_store().search(search_text):
            title = '<span weight="bold" >%s</span>' % (place.title)
            list_store.append([title + '\n' + place.uri, place.uri])

        self._search_view.set_model(list_store)

        return len(list_store) > 0

    def _search_popup(self):
        miss, window_x, window_y = self.props.window.get_origin()
        entry_allocation = self.get_allocation()
        preferred_height = self.get_preferred_height()[0]
        gap = (entry_allocation.height - preferred_height) / 2

        search_x = window_x + entry_allocation.x
        search_y = window_y + gap + preferred_height
        search_width = entry_allocation.width
        # Set minimun height to four entries.
        search_height = (style.STANDARD_ICON_SIZE + style.LINE_WIDTH * 2) * 4

        self._search_window.move(search_x, search_y)
        self._search_window.resize(search_width, search_height)
        self._search_window.show()

        self.get_parent().get_style_context().add_class('connected-entry')
        self.get_parent().queue_draw()

    def _search_popdown(self):
        self._search_window.hide()
        self.get_parent().get_style_context().remove_class('connected-entry')
        self.get_parent().queue_draw()

    def __focus_in_event_cb(self, entry, event):
        self._search_popdown()

    def __focus_out_event_cb(self, entry, event):
        self._search_popdown()

    def __view_button_press_event_cb(self, view, event):
        model = view.get_model()

        path, col_, x_, y_ = view.get_path_at_pos(int(event.x), int(event.y))
        if path:
            uri = model[path][self._COL_ADDRESS]
            self.activate(uri)

    def __key_press_event_cb(self, entry, event):
        selection = self._search_view.get_selection()
        model, selected = selection.get_selected()

        if event.keyval in (Gdk.KEY_uparrow, Gdk.KEY_Up):
            if selected is None:
                selection.select_iter(model[-1].iter)
                self._set_text(model[-1][0])
            else:
                up_iter = model.iter_previous(selected)
                if up_iter:
                    selection.select_iter(up_iter)
                    self._set_text(model.get(up_iter, self._COL_ADDRESS)[0])
            self.set_vadjustments(selection)
            return True

        if event.keyval in (Gdk.KEY_downarrow, Gdk.KEY_Down):
            if selected is None:
                down_iter = model.get_iter_first()
            else:
                down_iter = model.iter_next(selected)
            if down_iter:
                selection.select_iter(down_iter)
                self._set_text(model.get(down_iter, self._COL_ADDRESS)[0])
            self.set_vadjustments(selection)
            return True

        if event.keyval == Gdk.KEY_Return:
            if selected is None:
                return False
            uri = model[model.get_path(selected)][self._COL_ADDRESS]
            self.activate(uri)
            return True

        if event.keyval == Gdk.KEY_Escape:
            self._search_window.hide()
            self.props.text = ''
            return True

        return False

    def set_vadjustments(self, selection):
        # Sets the vertical adjustments of the scrolled window
        # on 'Up'/'Down' keypress
        path = (selection.get_selected_rows()[1])[0]
        index = path.get_indices()[0]
        adjustment = self._search_window_scroll.get_vadjustment()
        step = style.STANDARD_ICON_SIZE
        adjustment.set_value(step * index)
        self._search_window_scroll.set_vadjustment(adjustment)

    def __popup_unmap_cb(self, entry):
        self.handler_unblock(self._focus_out_hid)

    def __populate_popup_cb(self, entry, menu):
        self.handler_block(self._focus_out_hid)
        menu.connect('unmap', self.__popup_unmap_cb)

    def __changed_cb(self, entry):
        self._address = self.props.text

        if not self.props.text or not self._search_update():
            self._search_popdown()
        else:
            self._search_popup()


class UrlToolbar(Gtk.EventBox):
    # This is used for the URL entry in portrait mode.

    def __init__(self):
        Gtk.EventBox.__init__(self)
        self.modify_bg(Gtk.StateType.NORMAL,
                       style.COLOR_TOOLBAR_GREY.get_gdk_color())

        url_alignment = Gtk.Alignment(xscale=1.0, yscale=1.0)
        url_alignment.set_padding(0, 0, style.LINE_WIDTH * 4,
                                  style.LINE_WIDTH * 4)

        self.add(url_alignment)
        url_alignment.show()

        self.toolbar = Gtk.Toolbar()
        self.toolbar.set_size_request(-1, style.GRID_CELL_SIZE)
        url_alignment.add(self.toolbar)
        self.toolbar.show()


class PrimaryToolbar(ToolbarBase):
    __gtype_name__ = 'PrimaryToolbar'

    __gsignals__ = {
        'add-link': (GObject.SignalFlags.RUN_FIRST, None, ([])),
        'remove-link': (GObject.SignalFlags.RUN_FIRST, None, ([])),
        'go-home': (GObject.SignalFlags.RUN_FIRST, None, ([])),
        'set-home': (GObject.SignalFlags.RUN_FIRST, None, ([])),
        'reset-home': (GObject.SignalFlags.RUN_FIRST, None, ([])),
        'go-library': (GObject.SignalFlags.RUN_FIRST, None, ([])),
    }

    def __init__(self, tabbed_view, act):
        ToolbarBase.__init__(self)

        self._url_toolbar = UrlToolbar()

        self._activity = act
        self.model = act.model
        self.model.link_removed_signal.connect(self.__link_removed_cb)

        self._tabbed_view = self._canvas = tabbed_view

        self._loading = False
        self._download_running_hid = None

        toolbar = self.toolbar
        activity_button = ActivityToolbarButton(self._activity)
        toolbar.insert(activity_button, 0)

        separator = Gtk.SeparatorToolItem()

        '''
        Disabled since the python gi bindings don't expose the critical
        WebKit2.PrintOperation.print function

        save_as_pdf = ToolButton('save-as-pdf')
        save_as_pdf.set_tooltip(_('Save page as pdf'))
        save_as_pdf.connect('clicked', self.save_as_pdf)

        activity_button.props.page.insert(separator, -1)
        activity_button.props.page.insert(save_as_pdf, -1)
        separator.show()
        save_as_pdf.show()
        '''
        inspect_view = ToolButton('emblem-view-source')
        inspect_view.set_tooltip(_('Show Web Inspector'))
        inspect_view.connect('clicked', self.inspect_view)

        activity_button.props.page.insert(separator, -1)
        activity_button.props.page.insert(inspect_view, -1)
        separator.show()
        inspect_view.show()

        self._go_home = ToolButton('go-home')
        self._go_home.set_tooltip(_('Home page'))
        self._go_home.connect('clicked', self._go_home_cb)
        # add a menu to save the home page
        menu_box = PaletteMenuBox()
        self._go_home.props.palette.set_content(menu_box)
        menu_item = PaletteMenuItem()
        menu_item.set_label(_('Select as initial page'))
        menu_item.connect('activate', self._set_home_cb)
        menu_box.append_item(menu_item)

        self._reset_home_menu = PaletteMenuItem()
        self._reset_home_menu.set_label(_('Reset initial page'))
        self._reset_home_menu.connect('activate', self._reset_home_cb)
        menu_box.append_item(self._reset_home_menu)

        if os.path.isfile(LIBRARY_PATH):
            library_menu = PaletteMenuItem()
            library_menu.set_label(_('Library'))
            library_menu.connect('activate', self._go_library_cb)
            menu_box.append_item(library_menu)

        menu_box.show_all()

        # verify if the home page is configured
        home_page = tabbed_view.settings.get_string(SETTINGS_KEY_HOME_PAGE)
        self._reset_home_menu.set_visible(home_page != '')

        toolbar.insert(self._go_home, -1)
        self._go_home.show()

        self.entry = WebEntry()
        self.entry.set_icon_from_name(iconentry.ICON_ENTRY_SECONDARY,
                                      'entry-stop')
        self.entry.connect('icon-press', self._stop_and_reload_cb)
        self.entry.connect('activate', self._entry_activate_cb)
        self.entry.connect('focus-in-event', self.__focus_in_event_cb)
        self.entry.connect('focus-out-event', self.__focus_out_event_cb)
        self.entry.connect('key-press-event', self.__key_press_event_cb)
        self.entry.connect('changed', self.__changed_cb)

        # In an event box so that it can render the background
        entry_box = Gtk.EventBox()
        entry_box.add(self.entry)
        entry_box.show()

        self._entry_item = Gtk.ToolItem()
        self._entry_item.set_expand(True)
        self._entry_item.add(entry_box)
        self.entry.show()

        toolbar.insert(self._entry_item, -1)

        self._entry_item.show()

        self._back = ToolButton('go-previous-paired',
                                accelerator='<ctrl>Left')
        self._back.set_tooltip(_('Back'))
        self._back.props.sensitive = False
        self._back.connect('clicked', self._go_back_cb)
        toolbar.insert(self._back, -1)
        self._back.show()

        palette = self._back.get_palette()
        self._back_box_menu = Gtk.VBox()
        self._back_box_menu.show()
        palette.set_content(self._back_box_menu)
        # FIXME, this is a hack, should be done in the theme:
        palette._content.set_border_width(1)

        self._forward = ToolButton('go-next-paired',
                                   accelerator='<ctrl>Right')
        self._forward.set_tooltip(_('Forward'))
        self._forward.props.sensitive = False
        self._forward.connect('clicked', self._go_forward_cb)
        toolbar.insert(self._forward, -1)
        self._forward.show()

        palette = self._forward.get_palette()
        self._forward_box_menu = Gtk.VBox()
        self._forward_box_menu.show()
        palette.set_content(self._forward_box_menu)
        # FIXME, this is a hack, should be done in the theme:
        palette._content.set_border_width(1)

        self._download_icon = ProgressToolButton(
            icon_name='emblem-downloads',
            tooltip=_('No Downloads Running'))
        toolbar.insert(self._download_icon, -1)
        self._download_icon.show()
        downloadmanager.connect_download_started(self.__download_started_cb)

        self._link_add = ToggleToolButton('emblem-favorite')
        self._link_add.set_accelerator('<ctrl>d')
        self._link_add.set_tooltip(_('Bookmark'))
        self._link_add_toggled_hid = \
            self._link_add.connect('toggled', self.__link_add_toggled_cb)
        toolbar.insert(self._link_add, -1)
        self._link_add.show()

        self._toolbar_separator = Gtk.SeparatorToolItem()
        self._toolbar_separator.props.draw = False
        self._toolbar_separator.set_expand(True)

        self._stop_button = StopButton(self._activity)
        toolbar.insert(self._stop_button, -1)

        self._progress_listener = None
        self._browser = None

        self._loading_changed_hid = None
        self._progress_changed_hid = None
        self._session_history_changed_hid = None
        self._uri_changed_hid = None
        self._load_changed_hid = None
        self._security_status_changed_hid = None

        if tabbed_view.get_n_pages():
            self._connect_to_browser(tabbed_view.props.current_browser)

        tabbed_view.connect_after('switch-page', self.__switch_page_cb)
        tabbed_view.connect_after('page-added', self.__page_added_cb)

        Gdk.Screen.get_default().connect('size-changed',
                                         self.__screen_size_changed_cb)

        self._configure_toolbar()

    def __download_started_cb(self):
        if self._download_running_hid is None:
            self._download_running_hid = GLib.timeout_add(
                80, self.__download_running_cb)

    def __download_running_cb(self):
        progress = downloadmanager.overall_downloads_progress()
        self._download_icon.update(progress)
        if downloadmanager.num_downloads() > 0:
            self._download_icon.props.tooltip = \
                _('{}% Downloaded').format(int(progress*100))
            return True
        else:
            self._download_running_hid = None
            self._download_icon.props.tooltip = _('No Downloads Running')
            return False

    def __key_press_event_cb(self, entry, event):
        self._tabbed_view.current_browser.loading_uri = entry.props.text

    def __switch_page_cb(self, tabbed_view, page, page_num):
        if tabbed_view.get_n_pages():
            self._connect_to_browser(tabbed_view.props.current_browser)

    def __page_added_cb(self, notebook, child, pagenum):
        self.entry._search_popdown()

    def _configure_toolbar(self, screen=None):
        # Adapt the toolbars for portrait or landscape mode.

        if screen is None:
            screen = Gdk.Screen.get_default()

        if screen.get_width() < screen.get_height():
            if self._entry_item in self._url_toolbar.toolbar.get_children():
                return

            self.toolbar.remove(self._entry_item)
            self._url_toolbar.toolbar.insert(self._entry_item, -1)

            separator_pos = len(self.toolbar.get_children()) - 1
            self.toolbar.insert(self._toolbar_separator, separator_pos)
            self._toolbar_separator.show()

            self.pack_end(self._url_toolbar, True, True, 0)
            self._url_toolbar.show()

        else:
            if self._entry_item in self.toolbar.get_children():
                return

            self.toolbar.remove(self._toolbar_separator)

            position = len(self.toolbar.get_children()) - 4
            self._url_toolbar.toolbar.remove(self._entry_item)
            self.toolbar.insert(self._entry_item, position)

            self._toolbar_separator.hide()
            self.remove(self._url_toolbar)

    def __screen_size_changed_cb(self, screen):
        self._configure_toolbar(screen)

    def _connect_to_browser(self, browser):
        if self._browser is not None:
            self._browser.disconnect(self._uri_changed_hid)
            self._browser.disconnect(self._load_changed_hid)
            self._browser.disconnect(self._progress_changed_hid)
            self._browser.disconnect(self._security_status_changed_hid)

        self._browser = browser
        if not isinstance(self._browser, DummyBrowser):
            address = self._browser.props.uri or self._browser.loading_uri
        else:
            address = self._browser.props.uri
        self._set_address(address)
        self._set_progress(self._browser.props.estimated_load_progress)
        self._set_loading(self._browser.props.estimated_load_progress < 1.0)
        self._set_security_status(self._browser.security_status)

        is_webkit_browser = isinstance(self._browser, Browser)
        self.entry.props.editable = is_webkit_browser

        self._uri_changed_hid = self._browser.connect(
            'notify::uri', self.__uri_changed_cb)
        self._load_changed_hid = self._browser.connect(
            'load-changed', self.__load_changed_cb)
        self._progress_changed_hid = self._browser.connect(
            'notify::estimated-load-progress', self.__progress_changed_cb)
        self._security_status_changed_hid = self._browser.connect(
            'security-status-changed', self.__security_status_changed_cb)

        self._update_navigation_buttons()

    def __security_status_changed_cb(self, widget):
        self._set_security_status(widget.security_status)

    def __progress_changed_cb(self, widget, param):
        self._set_progress(widget.props.estimated_load_progress)
        self._set_loading(widget.props.estimated_load_progress < 1.0)

    def _set_security_status(self, security_status):
        # Display security status as a lock icon in the left side of
        # the URL entry.
        if security_status is None:
            self.entry.set_icon_from_pixbuf(
                iconentry.ICON_ENTRY_PRIMARY, None)
        elif security_status == Browser.SECURITY_STATUS_SECURE:
            self.entry.set_icon_from_name(
                iconentry.ICON_ENTRY_PRIMARY, 'channel-secure-symbolic')
        elif security_status == Browser.SECURITY_STATUS_INSECURE:
            self.entry.set_icon_from_name(
                iconentry.ICON_ENTRY_PRIMARY, 'channel-insecure-symbolic')

    def _set_progress(self, progress):
        if progress == 1.0:
            self.entry.set_progress_fraction(0.0)
        else:
            self.entry.set_progress_fraction(progress)

    def _set_address(self, uri):
        if uri is None:
            self.entry.props.address = ''
        else:
            self.entry.props.address = uri

    def __changed_cb(self, iconentry):
        # The WebEntry can be changed when we click on a link, then we
        # have to show the clear icon only if is the user who has
        # changed the entry
        if self.entry.has_focus():
            if not self.entry.props.text:
                self._show_no_icon()
            else:
                self._show_clear_icon()

    def __focus_in_event_cb(self, entry, event):
        if not self._tabbed_view.is_current_page_pdf():
            if not self.entry.props.text:
                self._show_no_icon()
            else:
                self._show_clear_icon()

    def __focus_out_event_cb(self, entry, event):
        if self._loading:
            self._show_stop_icon()
        else:
            if not self._tabbed_view.is_current_page_pdf():
                self._show_reload_icon()

    def _show_no_icon(self):
        self.entry.remove_icon(iconentry.ICON_ENTRY_SECONDARY)

    def _show_stop_icon(self):
        self.entry.set_icon_from_name(iconentry.ICON_ENTRY_SECONDARY,
                                      'entry-stop')

    def _show_reload_icon(self):
        self.entry.set_icon_from_name(iconentry.ICON_ENTRY_SECONDARY,
                                      'entry-refresh')

    def _show_clear_icon(self):
        self.entry.set_icon_from_name(iconentry.ICON_ENTRY_SECONDARY,
                                      'entry-cancel')

    def _update_navigation_buttons(self):
        if isinstance(self._browser, Browser):
            can_go_back = self._browser.can_go_back()
            self._back.props.sensitive = can_go_back

            can_go_forward = self._browser.can_go_forward()
            self._forward.props.sensitive = can_go_forward
        else:
            self._back.props.sensitive = False
            self._forward.props.sensitive = False

        is_webkit_browser = isinstance(self._browser, Browser)
        self._go_home.props.sensitive = is_webkit_browser
        if is_webkit_browser:
            self._reload_session_history()

        with self._link_add.handler_block(self._link_add_toggled_hid):
            uri = self._browser.get_uri()
            self._link_add.props.active = self.model.has_link(uri)

    def __link_removed_cb(self, model):
        self._update_navigation_buttons()

    def _entry_activate_cb(self, entry):
        url = entry.props.text
        effective_url = self._tabbed_view.normalize_or_autosearch_url(url)
        self._browser.load_uri(effective_url)
        self._browser.loading_uri = effective_url
        self.entry.props.address = effective_url
        self._browser.grab_focus()

    def _go_home_cb(self, button):
        self.emit('go-home')

    def _go_library_cb(self, button):
        self.emit('go-library')

    def _set_home_cb(self, button):
        self._reset_home_menu.set_visible(True)
        self.emit('set-home')

    def _reset_home_cb(self, button):
        self._reset_home_menu.set_visible(False)
        self.emit('reset-home')

    def _go_back_cb(self, button):
        self._browser.go_back()

    def _go_forward_cb(self, button):
        self._browser.go_forward()

    def __uri_changed_cb(self, widget, param):
        self._set_address(widget.get_uri())
        self._update_navigation_buttons()
        filepicker.cleanup_temp_files()

    def __load_changed_cb(self, widget, event):
        self._update_navigation_buttons()

    def _stop_and_reload_cb(self, entry, icon_pos, button):
        if entry.has_focus() and \
                not self._tabbed_view.is_current_page_pdf():
            entry.set_text('')
        else:
            if self._loading:
                self._browser.stop_loading()
            else:
                self._browser.reload()

    def _set_loading(self, loading):
        self._loading = loading

        if self._loading:
            self._show_stop_icon()
        else:
            if not self._tabbed_view.is_current_page_pdf():
                self._set_sensitive(True)
                self._show_reload_icon()
            else:
                self._set_sensitive(False)
                self._show_no_icon()

    def _set_sensitive(self, value):
        for widget in self.toolbar:
            if widget not in (self._stop_button,
                              self._link_add):
                widget.set_sensitive(value)

    def _reload_session_history(self):
        back_forward_list = self._browser.get_back_forward_list()
        item_index = 0  # The index of the history item

        # Clear menus in palettes:
        for box_menu in (self._back_box_menu, self._forward_box_menu):
            for menu_item in box_menu.get_children():
                box_menu.remove(menu_item)

        def create_menu_item(history_item):
            """Create a MenuItem for the back or forward palettes."""
            title = history_item.get_title() or _('No Title')
            menu_item = PaletteMenuItem(text_label=title)
            menu_item.connect('activate', self._history_item_activated_cb,
                              history_item)
            return menu_item

        back_list = back_forward_list.get_back_list_with_limit(
            _MAX_HISTORY_ENTRIES)
        back_list.reverse()
        for item in back_list:
            menu_item = create_menu_item(item)
            self._back_box_menu.pack_end(menu_item, False, False, 0)
            menu_item.show()
            item_index += 1

        # Increment the item index to count the current page:
        item_index += 1

        forward_list = back_forward_list.get_forward_list_with_limit(
            _MAX_HISTORY_ENTRIES)
        forward_list.reverse()
        for item in forward_list:
            menu_item = create_menu_item(item)
            self._forward_box_menu.pack_start(menu_item, False, False, 0)
            menu_item.show()
            item_index += 1

    def _history_item_activated_cb(self, menu_item, history_item):
        self._back.get_palette().popdown(immediate=True)
        self._forward.get_palette().popdown(immediate=True)
        # self._browser.set_history_index(index)
        self._browser.go_to_back_forward_list_item(history_item)

    def __link_add_toggled_cb(self, button):
        if button.props.active:
            self.emit('add-link')
        else:
            self.emit('remove-link')

    def inspect_view(self, button):
        page = self._canvas.get_current_page()
        webview = self._canvas.get_children()[page].props.browser

        # If get_inspector returns None, it is not a real WebView
        inspector = webview.get_inspector()
        if inspector is not None:
            # Inspector window will be blank if disabled
            web_settings = webview.get_settings()
            web_settings.props.enable_developer_extras = True

            inspector.show()
            inspector.attach()

    '''
    import sugar3.profile
    from sugar3.datastore import datastore
    from sugar3.activity import activity
    from sugar3.graphics.alert import Alert
    from sugar3.graphics.icon import Icon
    import tempfile

    def save_as_pdf(self, widget):
        tmp_dir = os.path.join(self._activity.get_activity_root(), 'tmp')
        fd, file_path = tempfile.mkstemp(dir=tmp_dir)
        os.close(fd)

        page = self._canvas.get_current_page()
        webview = self._canvas.get_children()[page].get_children()[0]
        webview.connect('print', self.__pdf_print_cb, file_path)
        # Why is there no webview method to do this?
        webview.run_javascript('window.print()', None, None)

    def __pdf_print_cb(self, webview, wk_print, file_path):
        webkit.dicsonnect_by_func(self.__pdf_print_cb)

        settings = wk_print.get_settings()
        settings.set(Gtk.PRINT_SETTINGS_OUTPUT_FILE_FORMAT, 'PDF')
        settings.set(Gtk.PRINT_SETTINGS_OUTPUT_FILE_URI, 'file://' + file_path)
        # The docs say that the print operation has this, but it seems to
        # get lost in the python bindings since it conflicts with the keyword
        wk_print.print()

        color = sugar3.profile.get_color().to_string()
        try:
            jobject.metadata['title'] = _('Browse activity as PDF')
            jobject.metadata['icon-color'] = color
            jobject.metadata['mime_type'] = 'application/pdf'
            jobject.file_path = file_path
            datastore.write(jobject)
        finally:
            self.__pdf_alert(jobject.object_id)
            jobject.destroy()
            del jobject

    def __pdf_alert(self, object_id):
        alert = Alert()
        alert.props.title = _('Page saved')
        alert.props.msg = _('The page has been saved as PDF to journal')

        alert.add_button(Gtk.ResponseType.APPLY,
                         _('Show in Journal'),
                         Icon(icon_name='zoom-activity'))
        alert.add_button(Gtk.ResponseType.OK, _('Ok'),
                         Icon(icon_name='dialog-ok'))

        # Remove other alerts
        for alert in self._activity._alerts:
            self._activity.remove_alert(alert)

        self._activity.add_alert(alert)
        alert.connect('response', self.__pdf_response_alert, object_id)
        alert.show_all()

    def __pdf_response_alert(self, alert, response_id, object_id):

        if response_id is Gtk.ResponseType.APPLY:
            activity.show_object_in_journal(object_id)

        self._activity.remove_alert(alert)
    '''
