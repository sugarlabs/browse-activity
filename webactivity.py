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
from gi.repository import WebKit
from gi.repository import Soup
from gi.repository import SoupGNOME

import base64
import time
import shutil
import json
from gi.repository import GConf
import cairo
import StringIO
from hashlib import sha1

from sugar3.activity import activity
from sugar3.graphics import style
import telepathy
import telepathy.client
from sugar3.presence import presenceservice
from sugar3.graphics.tray import HTray
from sugar3 import profile
from sugar3.graphics.alert import Alert
from sugar3.graphics.alert import NotifyAlert
from sugar3.graphics.icon import Icon
from sugar3 import mime

from sugar3.graphics.toolbarbox import ToolbarButton

PROFILE_VERSION = 2

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

    shutil.copy('cert8.db', _profile_path)
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
from sugar3.presence.tubeconn import TubeConnection
from messenger import Messenger
from linkbutton import LinkButton

SERVICE = "org.laptop.WebActivity"
IFACE = SERVICE
PATH = "/org/laptop/WebActivity"

_logger = logging.getLogger('web-activity')


class WebActivity(activity.Activity):
    def __init__(self, handle):
        activity.Activity.__init__(self, handle)

        _logger.debug('Starting the web activity')

        session = WebKit.get_default_session()
        session.set_property('accept-language-auto', True)
        session.set_property('ssl-use-system-ca-file', True)
        session.set_property('ssl-strict', False)

        # By default, cookies are not stored persistently, we have to
        # add a cookie jar so that they get saved to disk.  We use one
        # with a SQlite database:
        cookie_jar = SoupGNOME.CookieJarSqlite(filename=_cookies_db_path,
                                               read_only=False)
        session.add_feature(cookie_jar)

        _seed_xs_cookie(cookie_jar)

        # FIXME
        # downloadmanager.remove_old_parts()

        self._force_close = False
        self._tabbed_view = TabbedView()
        self._tabbed_view.connect('focus-url-entry', self._on_focus_url_entry)
        self._tabbed_view.connect('switch-page', self.__switch_page_cb)

        self._tray = HTray()
        self.set_tray(self._tray, Gtk.PositionType.BOTTOM)

        self._primary_toolbar = PrimaryToolbar(self._tabbed_view, self)
        self._edit_toolbar = EditToolbar(self)
        self._view_toolbar = ViewToolbar(self)

        self._primary_toolbar.connect('add-link', self._link_add_button_cb)

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

        self.model = Model()
        self.model.connect('add_link', self._add_link_model_cb)

        self.connect('key-press-event', self._key_press_cb)

        if handle.uri:
            self._tabbed_view.current_browser.load_uri(handle.uri)
        elif not self._jobject.file_path:
            # TODO: we need this hack until we extend the activity API for
            # opening URIs and default docs.
            self._tabbed_view.load_homepage()

        self.messenger = None
        self.connect('shared', self._shared_cb)

        # Get the Presence Service
        self.pservice = presenceservice.get_instance()
        try:
            name, path = self.pservice.get_preferred_connection()
            self.tp_conn_name = name
            self.tp_conn_path = path
            self.conn = telepathy.client.Connection(name, path)
        except TypeError:
            _logger.debug('Offline')
        self.initiating = None

        if self.get_shared_activity() is not None:
            _logger.debug('shared: %s', self.get_shared())
            # We are joining the activity
            _logger.debug('Joined activity')
            self.connect('joined', self._joined_cb)
            if self.get_shared():
                # We've already joined
                self._joined_cb()
        else:
            _logger.debug('Created activity')

        # README: this is a workaround to remove old temp file
        # http://bugs.sugarlabs.org/ticket/3973
        self._cleanup_temp_files()

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

    def _shared_cb(self, activity_):
        _logger.debug('My activity was shared')
        self.initiating = True
        self._setup()

        _logger.debug('This is my activity: making a tube...')
        self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].OfferDBusTube(SERVICE,
                                                                    {})

    def _setup(self):
        if self.get_shared_activity() is None:
            _logger.debug('Failed to share or join activity')
            return

        bus_name, conn_path, channel_paths = \
            self.get_shared_activity().get_channels()

        # Work out what our room is called and whether we have Tubes already
        room = None
        tubes_chan = None
        text_chan = None
        for channel_path in channel_paths:
            channel = telepathy.client.Channel(bus_name, channel_path)
            htype, handle = channel.GetHandle()
            if htype == telepathy.HANDLE_TYPE_ROOM:
                _logger.debug('Found our room: it has handle#%d "%s"',
                              handle,
                              self.conn.InspectHandles(htype, [handle])[0])
                room = handle
                ctype = channel.GetChannelType()
                if ctype == telepathy.CHANNEL_TYPE_TUBES:
                    _logger.debug('Found our Tubes channel at %s',
                                  channel_path)
                    tubes_chan = channel
                elif ctype == telepathy.CHANNEL_TYPE_TEXT:
                    _logger.debug('Found our Text channel at %s',
                                  channel_path)
                    text_chan = channel

        if room is None:
            _logger.debug("Presence service didn't create a room")
            return
        if text_chan is None:
            _logger.debug("Presence service didn't create a text channel")
            return

        # Make sure we have a Tubes channel - PS doesn't yet provide one
        if tubes_chan is None:
            _logger.debug("Didn't find our Tubes channel, requesting one...")
            tubes_chan = self.conn.request_channel(
                telepathy.CHANNEL_TYPE_TUBES, telepathy.HANDLE_TYPE_ROOM,
                room, True)

        self.tubes_chan = tubes_chan
        self.text_chan = text_chan

        tubes_chan[telepathy.CHANNEL_TYPE_TUBES].connect_to_signal(
            'NewTube', self._new_tube_cb)

    def _list_tubes_reply_cb(self, tubes):
        for tube_info in tubes:
            self._new_tube_cb(*tube_info)

    def _list_tubes_error_cb(self, e):
        _logger.debug('ListTubes() failed: %s', e)

    def _joined_cb(self, activity_):
        if not self.get_shared_activity():
            return

        _logger.debug('Joined an existing shared activity')

        self.initiating = False
        self._setup()

        _logger.debug('This is not my activity: waiting for a tube...')
        self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].ListTubes(
            reply_handler=self._list_tubes_reply_cb,
            error_handler=self._list_tubes_error_cb)

    def _new_tube_cb(self, identifier, initiator, type, service, params,
                     state):
        _logger.debug('New tube: ID=%d initator=%d type=%d service=%s '
                      'params=%r state=%d', identifier, initiator, type,
                      service, params, state)

        if (type == telepathy.TUBE_TYPE_DBUS and
                service == SERVICE):
            if state == telepathy.TUBE_STATE_LOCAL_PENDING:
                self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].AcceptDBusTube(
                    identifier)

            self.tube_conn = TubeConnection(
                self.conn, self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES],
                identifier, group_iface=self.text_chan[
                    telepathy.CHANNEL_INTERFACE_GROUP])

            _logger.debug('Tube created')
            self.messenger = Messenger(self.tube_conn, self.initiating,
                                       self.model)

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
                                      base64.b64decode(link['thumb']),
                                      link['color'], link['title'],
                                      link['owner'], -1, link['hash'])
            logging.debug('########## reading %s', data)
            self._tabbed_view.set_history(self.model.data['history'])
            for number, tab in enumerate(self.model.data['currents']):
                tab_page = self._tabbed_view.get_nth_page(number)
                tab_page.browser.set_history_index(tab['history_index'])
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
        if not self.metadata['mime_type']:
            self.metadata['mime_type'] = 'text/plain'

        if self.metadata['mime_type'] == 'text/plain':

            browser = self._tabbed_view.current_browser

            if not self._jobject.metadata['title_set_by_user'] == '1':
                if browser.props.title is None:
                    self.metadata['title'] = _('Untitled')
                else:
                    self.metadata['title'] = browser.props.title

            self.model.data['history'] = self._tabbed_view.get_history()
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

            f = open(file_path, 'w')
            try:
                logging.debug('########## writing %s', self.model.serialize())
                f.write(self.model.serialize())
            finally:
                f.close()

    def _link_add_button_cb(self, button):
        self._add_link()

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

            if key_name == 'd':
                self._add_link()
            elif key_name == 'f':
                _logger.debug('keyboard: Find')
                self._edit_toolbar_button.set_expanded(True)
                self._edit_toolbar.search_entry.grab_focus()
            elif key_name == 'l':
                _logger.debug('keyboard: Focus url entry')
                self._primary_toolbar.entry.grab_focus()
            elif key_name == 'minus':
                _logger.debug('keyboard: Zoom out')
                browser.zoom_out()
            elif key_name in ['plus', 'equal']:
                _logger.debug('keyboard: Zoom in')
                browser.zoom_in()
            elif key_name == '0':
                _logger.debug('keyboard: Actual size')
                browser.set_zoom_level(ZOOM_ORIGINAL)
            elif key_name == 'Left':
                _logger.debug('keyboard: Go back')
                browser.go_back()
            elif key_name == 'Right':
                _logger.debug('keyboard: Go forward')
                browser.go_forward()
            elif key_name == 'r':
                _logger.debug('keyboard: Reload')
                browser.reload()
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
            status = browser.get_load_status()
            loading = WebKit.LoadStatus.PROVISIONAL <= status \
                < WebKit.LoadStatus.FINISHED
            if loading:
                _logger.debug('keyboard: Stop loading')
                browser.stop_loading()

        return False

    def _add_link(self):
        ''' take screenshot and add link info to the model '''

        browser = self._tabbed_view.props.current_browser
        ui_uri = browser.get_uri()

        for link in self.model.data['shared_links']:
            if link['hash'] == sha1(ui_uri).hexdigest():
                _logger.debug('_add_link: link exist already a=%s b=%s',
                              link['hash'], sha1(ui_uri).hexdigest())
                return
        buf = self._get_screenshot()
        timestamp = time.time()
        self.model.add_link(ui_uri, browser.props.title, buf,
                            profile.get_nick_name(),
                            profile.get_color().to_string(), timestamp)

        if self.messenger is not None:
            self.messenger._add_link(ui_uri, browser.props.title,
                                     profile.get_color().to_string(),
                                     profile.get_nick_name(),
                                     base64.b64encode(buf), timestamp)

    def _add_link_model_cb(self, model, index):
        ''' receive index of new link from the model '''
        link = self.model.data['shared_links'][index]
        self._add_link_totray(link['url'], base64.b64decode(link['thumb']),
                              link['color'], link['title'],
                              link['owner'], index, link['hash'])

    def _add_link_totray(self, url, buf, color, title, owner, index, hash):
        ''' add a link to the tray '''
        item = LinkButton(buf, color, title, owner, hash)
        item.connect('clicked', self._link_clicked_cb, url)
        item.connect('remove_link', self._link_removed_cb)
        # use index to add to the tray
        self._tray.add_item(item, index)
        item.show()
        self._view_toolbar.traybutton.props.sensitive = True
        self._view_toolbar.traybutton.props.active = True
        self._view_toolbar.update_traybutton_tooltip()

    def _link_removed_cb(self, button, hash):
        ''' remove a link from tray and delete it in the model '''
        self.model.remove_link(hash)
        self._tray.remove_item(button)
        if len(self._tray.get_children()) == 0:
            self._view_toolbar.traybutton.props.sensitive = False
            self._view_toolbar.traybutton.props.active = False
            self._view_toolbar.update_traybutton_tooltip()

    def _link_clicked_cb(self, button, url):
        ''' an item of the link tray has been clicked '''
        self._tabbed_view.props.current_browser.load_uri(url)

    def _get_screenshot(self):
        browser = self._tabbed_view.props.current_browser
        window = browser.get_window()
        width, height = window.get_width(), window.get_height()

        thumb_width, thumb_height = style.zoom(100), style.zoom(80)

        thumb_surface = Gdk.Window.create_similar_surface(
            window, cairo.CONTENT_COLOR, thumb_width, thumb_height)

        cairo_context = cairo.Context(thumb_surface)
        thumb_scale_w = thumb_width * 1.0 / width
        thumb_scale_h = thumb_height * 1.0 / height
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
        status = browser.get_load_status()

        if status in (WebKit.LoadStatus.COMMITTED,
                      WebKit.LoadStatus.FIRST_VISUALLY_NON_EMPTY_LAYOUT):
            self.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.WATCH))
        elif status in (WebKit.LoadStatus.PROVISIONAL,
                        WebKit.LoadStatus.FAILED,
                        WebKit.LoadStatus.FINISHED):
            self.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.LEFT_PTR))

    def get_document_path(self, async_cb, async_err_cb):
        browser = self._tabbed_view.props.current_browser
        browser.get_source(async_cb, async_err_cb)

    def get_canvas(self):
        return self._tabbed_view
