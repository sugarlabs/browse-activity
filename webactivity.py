# Copyright (C) 2006, Red Hat, Inc.
# Copyright (C) 2009 Martin Langhoff, Simon Schampijer, Daniel Drake,
#                    Tomeu Vizoso
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
from gettext import ngettext
import os

from gi.repository import GObject
GObject.threads_init()

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import WebKit2
from gi.repository import Soup
from gi.repository import SoupGNOME

from base64 import b64decode, b64encode
import time
import shutil
import json
from gi.repository import GConf
import cairo
import StringIO
from hashlib import sha1

from sugar3.activity import activity
from sugar3.graphics import style
from sugar3.graphics.alert import Alert
from sugar3.graphics.alert import NotifyAlert
from sugar3.graphics.icon import Icon
from sugar3.graphics.animator import Animator, Animation
from sugar3 import mime
from sugar3.graphics.toolbarbox import ToolbarButton
from sugar3 import profile

from collabwrapper.collabwrapper import CollabWrapper
from widgets import TitledTray


PROFILE_VERSION = 2

THUMB_WIDTH, THUMB_HEIGHT = style.zoom(100), style.zoom(80)

_profile_version = 0
_profile_path = os.path.join(activity.get_activity_root(), 'data/gecko')
_version_file = os.path.join(_profile_path, 'version')
_cookies_db_path = os.path.join(_profile_path, 'cookies.sqlite')

if os.path.exists(_version_file):
    f = open(_version_file)
    _profile_version = int(f.read())
    f.close()

if _profile_version < PROFILE_VERSION:
    if not os.path.exists(_profile_path):
        os.mkdir(_profile_path)

    if os.path.exists('cert8.db'):
        shutil.copy('cert8.db', _profile_path)
    else:
        # wikipedia activity use a empty file
        with open(os.path.join(_profile_path, 'cert8.db'), 'w') as cert_file:
            cert_file.write()

    os.chmod(os.path.join(_profile_path, 'cert8.db'), 0660)

    f = open(_version_file, 'w')
    f.write(str(PROFILE_VERSION))
    f.close()


def _seed_xs_cookie(cookie_jar):
    """Create a HTTP Cookie to authenticate with the Schoolserver.

    Do nothing if the laptop is not registered with Schoolserver, or
    if the cookie already exists.

    """
    client = GConf.Client.get_default()
    backup_url = client.get_string('/desktop/sugar/backup_url')
    if backup_url == '':
        _logger.debug('seed_xs_cookie: Not registered with Schoolserver')
        return

    jabber_server = client.get_string(
        '/desktop/sugar/collaboration/jabber_server')

    soup_uri = Soup.URI()
    soup_uri.set_scheme('xmpp')
    soup_uri.set_host(jabber_server)
    soup_uri.set_path('/')
    xs_cookie = cookie_jar.get_cookies(soup_uri, for_http=False)
    if xs_cookie is not None:
        _logger.debug('seed_xs_cookie: Cookie exists already')
        return

    pubkey = profile.get_profile().pubkey
    cookie_data = {'color': profile.get_color().to_string(),
                   'pkey_hash': sha1(pubkey).hexdigest()}

    expire = int(time.time()) + 10 * 365 * 24 * 60 * 60

    xs_cookie = Soup.Cookie()
    xs_cookie.set_name('xoid')
    xs_cookie.set_value(json.dumps(cookie_data))
    xs_cookie.set_domain(jabber_server)
    xs_cookie.set_path('/')
    xs_cookie.set_max_age(expire)
    cookie_jar.add_cookie(xs_cookie)
    _logger.debug('seed_xs_cookie: Updated cookie successfully')


from browser import TabbedView
from browser import ZOOM_ORIGINAL
from webtoolbar import PrimaryToolbar
from edittoolbar import EditToolbar
from viewtoolbar import ViewToolbar
import downloadmanager

# TODO: make the registration clearer SL #3087

from model import Model
from linkbutton import LinkButton

SERVICE = "org.laptop.WebActivity"
IFACE = SERVICE
PATH = "/org/laptop/WebActivity"

_logger = logging.getLogger('web-activity')


class WebActivity(activity.Activity):
    def __init__(self, handle):
        activity.Activity.__init__(self, handle)
        self._collab = CollabWrapper(self)
        self._collab.message.connect(self.__message_cb)

        _logger.debug('Starting the web activity')

        # TODO PORT
        # session = WebKit2.get_default_session()
        # session.set_property('accept-language-auto', True)
        # session.set_property('ssl-use-system-ca-file', True)
        # session.set_property('ssl-strict', False)

        # But of a hack, but webkit doesn't let us change the cookie jar
        # contents, we we can just pre-seed it
        cookie_jar = SoupGNOME.CookieJarSqlite(filename=_cookies_db_path,
                                               read_only=False)
        _seed_xs_cookie(cookie_jar)
        del cookie_jar

        context = WebKit2.WebContext.get_default()
        cookie_manager = context.get_cookie_manager()
        cookie_manager.set_persistent_storage(
            _cookies_db_path, WebKit2.CookiePersistentStorage.SQLITE)

        # FIXME
        # downloadmanager.remove_old_parts()
        context.connect('download-started', self.__download_requested_cb)

        self._force_close = False
        self._tabbed_view = TabbedView(self)
        self._tabbed_view.connect('focus-url-entry', self._on_focus_url_entry)
        self._tabbed_view.connect('switch-page', self.__switch_page_cb)

        self._titled_tray = TitledTray(_('Bookmarks'))
        self._tray = self._titled_tray.tray
        self.set_tray(self._titled_tray, Gtk.PositionType.BOTTOM)
        self._tray_links = {}

        self.model = Model()
        self.model.add_link_signal.connect(self._add_link_model_cb)

        self._primary_toolbar = PrimaryToolbar(self._tabbed_view, self)
        self._edit_toolbar = EditToolbar(self)
        self._view_toolbar = ViewToolbar(self)

        self._primary_toolbar.connect('add-link', self.__link_add_button_cb)
        self._primary_toolbar.connect('remove-link',
                                      self.__link_remove_button_cb)
        self._primary_toolbar.connect('go-home', self._go_home_button_cb)
        self._primary_toolbar.connect('go-library', self._go_library_button_cb)
        self._primary_toolbar.connect('set-home', self._set_home_button_cb)
        self._primary_toolbar.connect('reset-home', self._reset_home_button_cb)

        self._edit_toolbar_button = ToolbarButton(
            page=self._edit_toolbar, icon_name='toolbar-edit')

        self._primary_toolbar.toolbar.insert(
            self._edit_toolbar_button, 1)

        view_toolbar_button = ToolbarButton(
            page=self._view_toolbar, icon_name='toolbar-view')
        self._primary_toolbar.toolbar.insert(
            view_toolbar_button, 2)

        self._primary_toolbar.show_all()
        self.set_toolbar_box(self._primary_toolbar)

        self.set_canvas(self._tabbed_view)
        self._tabbed_view.show()

        self.connect('key-press-event', self._key_press_cb)

        if handle.uri:
            self._tabbed_view.current_browser.load_uri(handle.uri)
        elif not self._jobject.file_path:
            # TODO: we need this hack until we extend the activity API for
            # opening URIs and default docs.
            self._tabbed_view.load_homepage()

        # README: this is a workaround to remove old temp file
        # http://bugs.sugarlabs.org/ticket/3973
        self._cleanup_temp_files()

        self._collab.setup()

    def __download_requested_cb(self, context, download):
        logging.error('__download_requested_cb %r',
                      download.get_request().get_uri())
        downloadmanager.add_download(download, self)
        return True

    def unfullscreen(self):
        activity.Activity.unfullscreen(self)

        # Always show tabs here, because they are automatically hidden
        # if it is like a video fullscreening.  We ALWAYS need to make
        # sure these are visible.  Don't make the user lost
        self._tabbed_view.props.show_tabs = True

    def _cleanup_temp_files(self):
        """Removes temporary files generated by Download Manager that
        were cancelled by the user or failed for any reason.

        There is a bug in GLib that makes this to happen:
            https://bugzilla.gnome.org/show_bug.cgi?id=629301
        """

        try:
            uptime_proc = open('/proc/uptime', 'r').read()
            uptime = int(float(uptime_proc.split()[0]))
        except EnvironmentError:
            logging.warning('/proc/uptime could not be read')
            uptime = None

        temp_path = os.path.join(self.get_activity_root(), 'instance')
        now = int(time.time())
        cutoff = now - 24 * 60 * 60  # yesterday
        if uptime is not None:
            boot_time = now - uptime
            cutoff = max(cutoff, boot_time)

        for f in os.listdir(temp_path):
            if f.startswith('.goutputstream-'):
                fpath = os.path.join(temp_path, f)
                mtime = int(os.path.getmtime(fpath))
                if mtime < cutoff:
                    logging.warning('Removing old temporary file: %s', fpath)
                    try:
                        os.remove(fpath)
                    except EnvironmentError:
                        logging.error('Temporary file could not be '
                                      'removed: %s', fpath)

    def _on_focus_url_entry(self, gobject):
        self._primary_toolbar.entry.grab_focus()

    def _get_data_from_file_path(self, file_path):
        fd = open(file_path, 'r')
        try:
            data = fd.read()
        finally:
            fd.close()
        return data

    def read_file(self, file_path):
        if self.metadata['mime_type'] == 'text/plain':
            data = self._get_data_from_file_path(file_path)
            self.model.deserialize(data)

            for link in self.model.data['shared_links']:
                _logger.debug('read: url=%s title=%s d=%s' % (link['url'],
                                                              link['title'],
                                                              link['color']))
                self._add_link_totray(link['url'],
                                      b64decode(link['thumb']),
                                      link['color'], link['title'],
                                      link['owner'], -1, link['hash'],
                                      link.get('notes'))
            logging.debug('########## reading %s', data)
            if 'session_state' in self.model.data:
                self._tabbed_view.set_session_state(
                    self.model.data['session_state'])
            else:
                self._tabbed_view.set_legacy_history(
                    self.model.data['history'],
                    self.model.data['currents'])
                for number, tab in enumerate(self.model.data['currents']):
                    tab_page = self._tabbed_view.get_nth_page(number)
                    zoom_level = tab.get('zoom_level')
                    if zoom_level is not None:
                        tab_page.browser.set_zoom_level(zoom_level)
                    tab_page.browser.grab_focus()

            self._tabbed_view.set_current_page(self.model.data['current_tab'])

        elif self.metadata['mime_type'] == 'text/uri-list':
            data = self._get_data_from_file_path(file_path)
            uris = mime.split_uri_list(data)
            if len(uris) == 1:
                self._tabbed_view.props.current_browser.load_uri(uris[0])
            else:
                _logger.error('Open uri-list: Does not support'
                              'list of multiple uris by now.')
        else:
            file_uri = 'file://' + file_path
            self._tabbed_view.props.current_browser.load_uri(file_uri)
            self._tabbed_view.props.current_browser.grab_focus()

    def write_file(self, file_path):
        if not hasattr(self, '_tabbed_view'):
            _logger.error('Called write_file before the tabbed_view was made')
            return

        if not self.metadata['mime_type']:
            self.metadata['mime_type'] = 'text/plain'

        if self.metadata['mime_type'] == 'text/plain':
            browser = self._tabbed_view.current_browser

            if not self._jobject.metadata['title_set_by_user'] == '1':
                if browser.props.title is None:
                    self.metadata['title'] = _('Untitled')
                else:
                    self.metadata['title'] = browser.props.title

            self.model.data['history'] = self._tabbed_view.get_legacy_history()
            current_tab = self._tabbed_view.get_current_page()
            self.model.data['current_tab'] = current_tab

            self.model.data['currents'] = []
            for n in range(0, self._tabbed_view.get_n_pages()):
                tab_page = self._tabbed_view.get_nth_page(n)
                n_browser = tab_page.browser
                if n_browser is not None:
                    uri = n_browser.get_uri()
                    history_index = n_browser.get_history_index()
                    info = {'title': n_browser.props.title, 'url': uri,
                            'history_index': history_index,
                            'zoom_level': n_browser.get_zoom_level()}

                    self.model.data['currents'].append(info)

            self.model.data['session_state'] = \
                self._tabbed_view.get_state()

            f = open(file_path, 'w')
            try:
                logging.debug('########## writing %s', self.model.serialize())
                f.write(self.model.serialize())
            finally:
                f.close()

    def __link_add_button_cb(self, button):
        self._add_link()

    def __link_remove_button_cb(self, button):
        browser = self._tabbed_view.props.current_browser
        uri = browser.get_uri()
        self.__link_removed_cb(None, sha1(uri).hexdigest())

    def _go_home_button_cb(self, button):
        self._tabbed_view.load_homepage()

    def _go_library_button_cb(self, button):
        self._tabbed_view.load_homepage(ignore_gconf=True)

    def _set_home_button_cb(self, button):
        self._tabbed_view.set_homepage()
        self._alert(_('The initial page was configured'))

    def _reset_home_button_cb(self, button):
        self._tabbed_view.reset_homepage()
        self._alert(_('The default initial page was configured'))

    def _alert(self, title, text=None):
        alert = NotifyAlert(timeout=5)
        alert.props.title = title
        alert.props.msg = text
        self.add_alert(alert)
        alert.connect('response', self._alert_cancel_cb)
        alert.show()

    def _alert_cancel_cb(self, alert, response_id):
        self.remove_alert(alert)

    def _key_press_cb(self, widget, event):
        key_name = Gdk.keyval_name(event.keyval)
        browser = self._tabbed_view.props.current_browser

        if event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            if key_name == 'f':
                _logger.debug('keyboard: Find')
                self._edit_toolbar_button.set_expanded(True)
                self._edit_toolbar.search_entry.grab_focus()
            elif key_name == 'l':
                _logger.debug('keyboard: Focus url entry')
                self._primary_toolbar.entry.grab_focus()
            elif key_name == 'minus':
                _logger.debug('keyboard: Zoom out')
                browser.zoom_out()
            elif key_name == 'equal':
                # Equal is + without a shift, a convenience in addition to
                # the ctrl+ accelerator configured in the ToolButton
                _logger.debug('keyboard: Zoom in')
                browser.zoom_in()
            elif Gdk.keyval_name(event.keyval) == "t":
                self._tabbed_view.add_tab()
            elif key_name == 'w':
                _logger.debug('keyboard: close tab')
                self._tabbed_view.close_tab()
            else:
                return False

            return True

        elif key_name in ('KP_Up', 'KP_Down', 'KP_Left', 'KP_Right'):
            scrolled_window = browser.get_parent()

            if key_name in ('KP_Up', 'KP_Down'):
                adjustment = scrolled_window.get_vadjustment()
            elif key_name in ('KP_Left', 'KP_Right'):
                adjustment = scrolled_window.get_hadjustment()
            value = adjustment.get_value()
            step = adjustment.get_step_increment()

            if key_name in ('KP_Up', 'KP_Left'):
                adjustment.set_value(value - step)
            elif key_name in ('KP_Down', 'KP_Right'):
                adjustment.set_value(value + step)

            return True

        elif key_name == 'Escape':
            _logger.debug('keyboard: Stop loading')
            browser.stop_loading()

        return False

    def _add_link(self):
        ''' take screenshot and add link info to the model '''

        browser = self._tabbed_view.props.current_browser
        ui_uri = browser.get_uri()

        if self.model.has_link(ui_uri):
            return

        buf = b64encode(self._get_screenshot())
        timestamp = time.time()
        args = (ui_uri, browser.props.title, buf,
                profile.get_nick_name(),
                profile.get_color().to_string(), timestamp)
        self.model.add_link(*args, by_me=True)
        self._collab.post({'type': 'add_link', 'args': args})

    def __message_cb(self, collab, buddy, message):
        type_ = message.get('type')
        if type_ == 'add_link':
            self.model.add_link(*message['args'])
        elif type_ == 'add_link_from_info':
            self.model.add_link_from_info(message['dict'])
        elif type_ == 'remove_link':
            self.remove_link(message['hash'])

    def get_data(self):
        return self.model.data

    def set_data(self, data):
        for link in data['shared_links']:
            if link['hash'] not in self.model.get_links_ids():
                self.model.add_link_from_info(link)
            # FIXME: Case where buddy has updated link desciption

        their_model = Model()
        their_model.data = data
        for link in self.model.data['shared_links']:
            if link['hash'] not in their_model.get_links_ids():
                self._collab.post({'type': 'add_link_from_info',
                                   'dict': link})

    def _add_link_model_cb(self, model, index, by_me):
        ''' receive index of new link from the model '''
        link = self.model.data['shared_links'][index]
        widget = self._add_link_totray(
            link['url'], b64decode(link['thumb']),
            link['color'], link['title'],
            link['owner'], index, link['hash'],
            link.get('notes'))

        if by_me:
            animator = Animator(1, widget=self)
            animator.add(AddLinkAnimation(
                self, self._tabbed_view.props.current_browser, widget))
            animator.start()

    def _add_link_totray(self, url, buf, color, title, owner, index, hash,
                         notes=None):
        ''' add a link to the tray '''
        item = LinkButton(buf, color, title, owner, hash, notes)
        item.connect('clicked', self._link_clicked_cb, url)
        item.connect('remove_link', self.__link_removed_cb)
        item.notes_changed_signal.connect(self.__link_notes_changed)
        # use index to add to the tray
        self._tray_links[hash] = item
        self._tray.add_item(item, index)
        item.show()
        self._view_toolbar.traybutton.props.sensitive = True
        self._view_toolbar.traybutton.props.active = True
        self._view_toolbar.update_traybutton_tooltip()
        return item

    def __link_removed_cb(self, button, hash):
        self.remove_link(hash)
        self._collab.post({'type': 'remove_link', 'hash': hash})

    def remove_link(self, hash):
        ''' remove a link from tray and delete it in the model '''
        self._tray_links[hash].hide()
        self._tray_links[hash].destroy()
        del self._tray_links[hash]

        self.model.remove_link(hash)
        if len(self._tray.get_children()) == 0:
            self._view_toolbar.traybutton.props.sensitive = False
            self._view_toolbar.traybutton.props.active = False
            self._view_toolbar.update_traybutton_tooltip()

    def __link_notes_changed(self, button, hash, notes):
        self.model.change_link_notes(hash, notes)

    def _link_clicked_cb(self, button, url):
        ''' an item of the link tray has been clicked '''
        browser = self._tabbed_view.add_tab()
        browser.load_uri(url)
        browser.grab_focus()

    def _get_screenshot(self):
        browser = self._tabbed_view.props.current_browser
        window = browser.get_window()
        width, height = window.get_width(), window.get_height()

        thumb_surface = Gdk.Window.create_similar_surface(
            window, cairo.CONTENT_COLOR, THUMB_WIDTH, THUMB_HEIGHT)

        cairo_context = cairo.Context(thumb_surface)
        thumb_scale_w = THUMB_WIDTH * 1.0 / width
        thumb_scale_h = THUMB_HEIGHT * 1.0 / height
        cairo_context.scale(thumb_scale_w, thumb_scale_h)
        Gdk.cairo_set_source_window(cairo_context, window, 0, 0)
        cairo_context.paint()

        thumb_str = StringIO.StringIO()
        thumb_surface.write_to_png(thumb_str)
        return thumb_str.getvalue()

    def can_close(self):
        if self._force_close:
            return True
        elif downloadmanager.can_quit():
            return True
        else:
            alert = Alert()
            alert.props.title = ngettext('Download in progress',
                                         'Downloads in progress',
                                         downloadmanager.num_downloads())
            message = ngettext('Stopping now will erase your download',
                               'Stopping now will erase your downloads',
                               downloadmanager.num_downloads())
            alert.props.msg = message
            cancel_icon = Icon(icon_name='dialog-cancel')
            cancel_label = ngettext('Continue download', 'Continue downloads',
                                    downloadmanager.num_downloads())
            alert.add_button(Gtk.ResponseType.CANCEL, cancel_label,
                             cancel_icon)
            stop_icon = Icon(icon_name='dialog-ok')
            alert.add_button(Gtk.ResponseType.OK, _('Stop'), stop_icon)
            stop_icon.show()
            self.add_alert(alert)
            alert.connect('response', self.__inprogress_response_cb)
            alert.show()
            self.present()
            return False

    def __inprogress_response_cb(self, alert, response_id):
        self.remove_alert(alert)
        if response_id is Gtk.ResponseType.CANCEL:
            logging.debug('Keep on')
        elif response_id == Gtk.ResponseType.OK:
            logging.debug('Stop downloads and quit')
            self._force_close = True
            downloadmanager.remove_all_downloads()
            self.close()

    def __switch_page_cb(self, tabbed_view, page, page_num):
        browser = page._browser
        if browser.props.estimated_load_progress < 1.0 and browser.props.uri:
            self.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.WATCH))
        else:
            self.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.LEFT_PTR))

    def get_document_path(self, async_cb, async_err_cb):
        browser = self._tabbed_view.props.current_browser
        browser.get_source(async_cb, async_err_cb)

    def get_canvas(self):
        return self._tabbed_view


class AddLinkAnimation(Animation):

    def __init__(self, widget, browser, tray_widget):
        Animation.__init__(self, 0, 3)
        self._draw_hid = None
        self._widget = widget
        self._browser = browser
        self._tray_widget = tray_widget
        self._tray_widget.hide_thumb()

        self._balloc = browser.get_allocation()
        self._center = ((self._balloc.width) / 2.0,
                        (self._balloc.height) / 2.0)

        window = browser.get_window()
        width, height = window.get_width(), window.get_height()

        self._snap = Gdk.Window.create_similar_surface(
            window, cairo.CONTENT_COLOR, width, height)
        cairo_context = cairo.Context(self._snap)
        Gdk.cairo_set_source_window(cairo_context, window, 0, 0)
        cairo_context.paint()

    def do_frame(self, t, duration, easing):
        # exponential ease in/out
        t /= duration / 2.0
        if t < 1:
            frame = self.end/2.0 * pow(2, 10 * (t - 1))
        else:
            t -= 1
            frame = self.end/2.0 * (-pow(2, -10 * t) + 2)
        self.next_frame(frame)

    def next_frame(self, frame):
        self._frame = frame
        if self._draw_hid is None:
            self._draw_hid = self._widget.connect_after('draw', self.__draw_cb)
        self._widget.queue_draw()

    def __draw_cb(self, widget, cr):
        cr.save()

        thumb_scale_w = THUMB_WIDTH * 1.0 / self._balloc.width
        thumb_scale_h = THUMB_HEIGHT * 1.0 / self._balloc.height
        rect = (self._balloc.x, self._balloc.y,
                self._balloc.width, self._balloc.height)
        ox, oy = self._browser.translate_coordinates(widget, 0, 0)
        if self._frame < 1.0:
            frame = self._frame
            notframe = 1.0 - frame

            cr.save()
            cr.translate(ox, oy)
            cr.set_source_rgba(1.0, 1.0, 1.0, notframe)
            cr.rectangle(*rect)
            cr.fill()
            cr.restore()

            cr.translate(ox + (self._center[0] * frame),
                         oy + (self._center[1] * frame))
            cr.scale(notframe + (thumb_scale_w * frame),
                     notframe + (thumb_scale_h * frame))
            stroke_alpha = frame
            width = 20 * frame
        else:
            frame = (self._frame - 1.0) / 2.0
            notframe = 1.0 - frame
            x, y = self._tray_widget.get_image_coords(widget)
            cr.translate(((ox + self._center[0]) * notframe) + (x * frame),
                         ((oy + self._center[1]) * notframe) + (y * frame))
            cr.scale(thumb_scale_w, thumb_scale_h)
            stroke_alpha = notframe
            width = 20

        cr.set_source_surface(self._snap)
        cr.rectangle(*rect)
        cr.fill()
        cr.set_source_rgba(0.0, 0.0, 0.0, stroke_alpha)
        cr.set_line_width(width)
        cr.rectangle(*rect)
        cr.stroke()

        cr.restore()

    def do_stop(self):
        self._tray_widget.show_thumb()
        self._widget.disconnect(self._draw_hid)
        self._widget.queue_draw()
