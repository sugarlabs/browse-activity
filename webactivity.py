# Copyright (C) 2006, Red Hat, Inc.
# Copyright (C) 2009 Martin Langhoff, Simon Schampijer, Daniel Drake, Tomeu Vizoso
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
import logging
from gettext import gettext as _

import gobject
gobject.threads_init()

import gtk
import sha
import base64
import time
import shutil
import sqlite3
import cjson
import gconf
import locale

# HACK: Needed by http://dev.sugarlabs.org/ticket/456
import gnome
gnome.init('Hulahop', '1.0')

from sugar.activity import activity
from sugar.graphics import style
import telepathy
import telepathy.client
from sugar.presence import presenceservice
from sugar.graphics.tray import HTray
from sugar import profile
from sugar.graphics.alert import Alert
from sugar.graphics.icon import Icon
from sugar.graphics.toolbarbox import ToolbarButton
from sugar import mime

PROFILE_VERSION = 1

_profile_version = 0
_profile_path = os.path.join(activity.get_activity_root(), 'data/gecko')
_version_file = os.path.join(_profile_path, 'version')

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

def _seed_xs_cookie():
    ''' Create a HTTP Cookie to authenticate with the Schoolserver
    '''
    client = gconf.client_get_default()
    backup_url = client.get_string('/desktop/sugar/backup_url')
    if not backup_url:
        _logger.debug('seed_xs_cookie: Not registered with Schoolserver')
        return

    jabber_server = client.get_string(
        '/desktop/sugar/collaboration/jabber_server')

    pubkey = profile.get_profile().pubkey
    cookie_data = {'color': profile.get_color().to_string(),
                   'pkey_hash': sha.new(pubkey).hexdigest()}

    db_path = os.path.join(_profile_path, 'cookies.sqlite')
    try:
        cookies_db = sqlite3.connect(db_path)
        c = cookies_db.cursor()

        c.execute('''CREATE TABLE IF NOT EXISTS
                     moz_cookies 
                     (id INTEGER PRIMARY KEY,
                      name TEXT,
                      value TEXT,
                      host TEXT,
                      path TEXT,
                      expiry INTEGER,
                      lastAccessed INTEGER,
                      isSecure INTEGER,
                      isHttpOnly INTEGER)''')

        c.execute('''SELECT id
                     FROM moz_cookies
                     WHERE name=? AND host=? AND path=?''',
                  ('xoid', jabber_server, '/'))
        
        if c.fetchone():
            _logger.debug('seed_xs_cookie: Cookie exists already')
            return

        expire = int(time.time()) + 10*365*24*60*60
        c.execute('''INSERT INTO moz_cookies (name, value, host, 
                                              path, expiry, lastAccessed,
                                              isSecure, isHttpOnly)
                     VALUES(?,?,?,?,?,?,?,?)''',
                  ('xoid', cjson.encode(cookie_data), jabber_server,
                   '/', expire, 0, 0, 0 ))
        cookies_db.commit()
        cookies_db.close()
    except sqlite3.Error, e:
        _logger.error('seed_xs_cookie: %s' % e)
    else:
        _logger.debug('seed_xs_cookie: Updated cookie successfully')


import hulahop
hulahop.set_app_version(os.environ['SUGAR_BUNDLE_VERSION'])
hulahop.startup(_profile_path)

from xpcom import components

def _set_accept_languages():
    ''' Set intl.accept_languages based on the locale
    '''

    lang = locale.getdefaultlocale()[0]
    if not lang:
        _logger.debug("Set_Accept_language: unrecognised LANG format")
        return
    lang = lang.split('_')

    # e.g. es-uy, es
    pref = lang[0] + "-" + lang[1].lower()  + ", " + lang[0]
    cls = components.classes["@mozilla.org/preferences-service;1"]
    prefService = cls.getService(components.interfaces.nsIPrefService)
    branch = prefService.getBranch('')
    branch.setCharPref('intl.accept_languages', pref)
    logging.debug('LANG set')

from browser import TabbedView
from webtoolbar import PrimaryToolbar
from edittoolbar import EditToolbar
from viewtoolbar import ViewToolbar
import downloadmanager
import globalhistory
import filepicker

_LIBRARY_PATH = '/usr/share/library-common/index.html'

from model import Model
from sugar.presence.tubeconn import TubeConnection
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

        self._tabbed_view = TabbedView()

        _set_accept_languages()
        _seed_xs_cookie()
        
        # don't pick up the sugar theme - use the native mozilla one instead
        cls = components.classes['@mozilla.org/preferences-service;1']
        pref_service = cls.getService(components.interfaces.nsIPrefService)
        branch = pref_service.getBranch("mozilla.widget.")
        branch.setBoolPref("disable-native-theme", True)

        self._primary_toolbar = PrimaryToolbar(self._tabbed_view, self)
        self._primary_toolbar.connect('add-link', self._link_add_button_cb)

        self._tray = HTray()
        self.set_tray(self._tray, gtk.POS_BOTTOM)
        self._tray.show()

        self._edit_toolbar = EditToolbar(self)
        self._edit_toolbar_button = ToolbarButton(
                page=self._edit_toolbar,
                icon_name='toolbar-edit')
        self._primary_toolbar.toolbar.insert(
                self._edit_toolbar_button, 1)
        
        self._view_toolbar = ViewToolbar(self)
        view_toolbar_button = ToolbarButton(
                page=self._view_toolbar,
                icon_name='toolbar-view')
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
            self._load_homepage()

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
            
        if self._shared_activity is not None:
            _logger.debug('shared:  %s' %self._shared_activity.props.joined)

        if self._shared_activity is not None:
            # We are joining the activity
            _logger.debug('Joined activity')                      
            self.connect('joined', self._joined_cb)
            if self.get_shared():
                # We've already joined
                self._joined_cb()
        else:   
            _logger.debug('Created activity')
    
    def _shared_cb(self, activity_):
        _logger.debug('My activity was shared')        
        self.initiating = True                        
        self._setup()

        _logger.debug('This is my activity: making a tube...')
        self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].OfferDBusTube(SERVICE, {})
                
    def _setup(self):
        if self._shared_activity is None:
            _logger.debug('Failed to share or join activity')
            return

        bus_name, conn_path, channel_paths = \
                self._shared_activity.get_channels()

        # Work out what our room is called and whether we have Tubes already
        room = None
        tubes_chan = None
        text_chan = None
        for channel_path in channel_paths:
            channel = telepathy.client.Channel(bus_name, channel_path)
            htype, handle = channel.GetHandle()
            if htype == telepathy.HANDLE_TYPE_ROOM:
                _logger.debug('Found our room: it has handle#%d "%s"' 
                    %(handle, self.conn.InspectHandles(htype, [handle])[0]))
                room = handle
                ctype = channel.GetChannelType()
                if ctype == telepathy.CHANNEL_TYPE_TUBES:
                    _logger.debug('Found our Tubes channel at %s'%channel_path)
                    tubes_chan = channel
                elif ctype == telepathy.CHANNEL_TYPE_TEXT:
                    _logger.debug('Found our Text channel at %s'%channel_path)
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
            tubes_chan = self.conn.request_channel(telepathy.CHANNEL_TYPE_TUBES,
                                                   telepathy.HANDLE_TYPE_ROOM, 
                                                   room, True)

        self.tubes_chan = tubes_chan
        self.text_chan = text_chan

        tubes_chan[telepathy.CHANNEL_TYPE_TUBES].connect_to_signal( \
                'NewTube', self._new_tube_cb)

    def _list_tubes_reply_cb(self, tubes):
        for tube_info in tubes:
            self._new_tube_cb(*tube_info)

    def _list_tubes_error_cb(self, e):
        _logger.debug('ListTubes() failed: %s'%e)

    def _joined_cb(self, activity_):
        if not self._shared_activity:
            return

        _logger.debug('Joined an existing shared activity')
        
        self.initiating = False
        self._setup()
                
        _logger.debug('This is not my activity: waiting for a tube...')
        self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].ListTubes(
            reply_handler=self._list_tubes_reply_cb, 
            error_handler=self._list_tubes_error_cb)

    def _new_tube_cb(self, identifier, initiator, type, service, params, state):
        _logger.debug('New tube: ID=%d initator=%d type=%d service=%s '
                      'params=%r state=%d' %(identifier, initiator, type, 
                                             service, params, state))

        if (type == telepathy.TUBE_TYPE_DBUS and
            service == SERVICE):
            if state == telepathy.TUBE_STATE_LOCAL_PENDING:
                self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].AcceptDBusTube(
                        identifier)

            self.tube_conn = TubeConnection(self.conn, 
                self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES], 
                identifier, group_iface = self.text_chan[
                    telepathy.CHANNEL_INTERFACE_GROUP])
            
            _logger.debug('Tube created')
            self.messenger = Messenger(self.tube_conn, self.initiating, 
                                       self.model)         

    def _load_homepage(self):
        browser = self._tabbed_view.current_browser
        if os.path.isfile(_LIBRARY_PATH):
            browser.load_uri('file://' + _LIBRARY_PATH)
        else:
            default_page = os.path.join(activity.get_bundle_path(), 
                                        "data/index.html")
            browser.load_uri(default_page)

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
            logging.debug('########## reading %s' % data)
            self._tabbed_view.set_session(self.model.data['history'])
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
            self._tabbed_view.props.current_browser.load_uri(file_path)
        
    def write_file(self, file_path):
        if not self.metadata['mime_type']:
            self.metadata['mime_type'] = 'text/plain'

        if self.metadata['mime_type'] == 'text/plain':

            browser = self._tabbed_view.current_browser

            if not self._jobject.metadata['title_set_by_user'] == '1':
                if browser.props.title:
                    self.metadata['title'] = browser.props.title

            self.model.data['history'] = self._tabbed_view.get_session()
            self.model.data['current_tab'] = self._tabbed_view.get_current_page()

            f = open(file_path, 'w')
            try:
                logging.debug('########## writing %s' % self.model.serialize())
                f.write(self.model.serialize())
            finally:
                f.close()

    def _link_add_button_cb(self, button):
        self._add_link()
            
    def _key_press_cb(self, widget, event):
        if event.state & gtk.gdk.CONTROL_MASK:
            if gtk.gdk.keyval_name(event.keyval) == "d":
                self._add_link()                
                return True
            elif gtk.gdk.keyval_name(event.keyval) == "f":
                _logger.debug('keyboard: Find')
                self._edit_toolbar_button.set_expanded(True)
                self._edit_toolbar.search_entry.grab_focus()                
                return True
            elif gtk.gdk.keyval_name(event.keyval) == "l":
                _logger.debug('keyboard: Focus url entry')
                self._primary_toolbar.entry.grab_focus()
                return True
            elif gtk.gdk.keyval_name(event.keyval) == "minus":
                _logger.debug('keyboard: Zoom out')
                self._tabbed_view.props.current_browser.zoom_out()
                return True
            elif gtk.gdk.keyval_name(event.keyval) == "plus" \
                     or gtk.gdk.keyval_name(event.keyval) == "equal" :
                _logger.debug('keyboard: Zoom in')
                self._tabbed_view.props.current_browser.zoom_in()
                return True
        return False

    def _add_link(self):
        ''' take screenshot and add link info to the model '''

        browser = self._tabbed_view.props.current_browser
        uri = browser.progress.location
        cls = components.classes['@mozilla.org/intl/texttosuburi;1']
        texttosuburi = cls.getService(components.interfaces.nsITextToSubURI)
        ui_uri = texttosuburi.unEscapeURIForUI(uri.originCharset, uri.spec)

        for link in self.model.data['shared_links']:
            if link['hash'] == sha.new(ui_uri).hexdigest():
                _logger.debug('_add_link: link exist already a=%s b=%s' %(
                    link['hash'], sha.new(ui_uri).hexdigest()))
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
        item = LinkButton(url, buf, color, title, owner, index, hash)
        item.connect('clicked', self._link_clicked_cb, url)
        item.connect('remove_link', self._link_removed_cb)
        self._tray.add_item(item, index) # use index to add to the tray
        item.show()
        if self._tray.props.visible is False:
            self._tray.show()        
        self._view_toolbar.traybutton.props.sensitive = True
        
    def _link_removed_cb(self, button, hash):
        ''' remove a link from tray and delete it in the model '''
        self.model.remove_link(hash)
        self._tray.remove_item(button)
        if len(self._tray.get_children()) == 0:
            self._view_toolbar.traybutton.props.sensitive = False

    def _link_clicked_cb(self, button, url):
        ''' an item of the link tray has been clicked '''
        self._tabbed_view.props.current_browser.load_uri(url)

    def _pixbuf_save_cb(self, buf, data):
        data[0] += buf
        return True

    def get_buffer(self, pixbuf):
        data = [""]
        pixbuf.save_to_callback(self._pixbuf_save_cb, "png", {}, data)
        return str(data[0])

    def _get_screenshot(self):
        window = self._tabbed_view.props.current_browser.window
        width, height = window.get_size()

        screenshot = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, has_alpha=False,
                                    bits_per_sample=8, width=width,
                                    height=height)
        screenshot.get_from_drawable(window, window.get_colormap(), 0, 0, 0, 0,
                                     width, height)

        screenshot = screenshot.scale_simple(style.zoom(100),
                                                 style.zoom(80),
                                                 gtk.gdk.INTERP_BILINEAR)

        buf = self.get_buffer(screenshot)
        return buf

    def can_close(self):
        if downloadmanager.can_quit():
            return True
        else:
            alert = Alert()
            alert.props.title = _('Download in progress')
            alert.props.msg = _('Stopping now will cancel your download')
            cancel_icon = Icon(icon_name='dialog-cancel')
            alert.add_button(gtk.RESPONSE_CANCEL, _('Cancel'), cancel_icon)
            stop_icon = Icon(icon_name='dialog-ok')
            alert.add_button(gtk.RESPONSE_OK, _('Stop'), stop_icon)
            stop_icon.show()
            self.add_alert(alert)
            alert.connect('response', self.__inprogress_response_cb)
            alert.show()            
            self.present()

    def __inprogress_response_cb(self, alert, response_id):
        self.remove_alert(alert)
        if response_id is gtk.RESPONSE_CANCEL:
            logging.debug('Keep on')
        elif response_id == gtk.RESPONSE_OK:
            logging.debug('Stop downloads and quit')
            downloadmanager.remove_all_downloads()
            self.close(force=True)

    def get_document_path(self, async_cb, async_err_cb):
        browser = self._tabbed_view.props.current_browser
        browser.get_source(async_cb, async_err_cb)

