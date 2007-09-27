# Copyright (C) 2006, Red Hat, Inc.
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

import gtk
import dbus
import sha
import base64
import time
 
from sugar.activity import activity
from sugar import env
from sugar.graphics import style
import telepathy
import telepathy.client
from sugar import _sugarext
from sugar.presence import presenceservice
from sugar.graphics.tray import HTray
from sugar import profile

import hulahop
hulahop.startup(os.path.join(env.get_profile_path(), 'gecko'))

from browser import Browser
from webtoolbar import WebToolbar
import downloadmanager
import promptservice
import securitydialogs
import filepicker
import sessionhistory 
import progresslistener

_LIBRARY_PATH = '/home/olpc/Library/index.html'

from model import Model
from sugar.presence.tubeconn import TubeConnection
from messenger import Messenger
from linkbutton import LinkButton

SERVICE = "org.laptop.WebActivity"
IFACE = SERVICE
PATH = "/org/laptop/WebActivity"

_VIEW_SOURCE_KEY_CODE = 0x1008FF1A

_logger = logging.getLogger('web-activity')

class WebActivity(activity.Activity):
    def __init__(self, handle, browser=None):
        activity.Activity.__init__(self, handle)

        _logger.debug('Starting the web activity')

        if browser:
            self._browser = browser
        else:
            self._browser = Browser()

        temp_path = os.path.join(self.get_activity_root(), 'tmp')
        downloadmanager.init(self._browser, temp_path)
        sessionhistory.init(self._browser)
        progresslistener.init(self._browser)

        toolbox = activity.ActivityToolbox(self)
        activity_toolbar = toolbox.get_activity_toolbar()

        self.toolbar = WebToolbar(self._browser)
        toolbox.add_toolbar(_('Browse'), self.toolbar)
        self.toolbar.show()

        self.set_toolbox(toolbox)
        toolbox.show()

        self._tray = HTray()
        self.session_history = sessionhistory.get_instance()
        self.session_history.connect('session-link-changed', self._session_history_changed_cb)
        self.toolbar.connect('add-link', self._link_add_button_cb)
        self.toolbar.connect('visibility-tray', self._tray_visibility_cb)
        self._tray_isvisible = False
        self._tray_numelems = 0

        self._browser.connect("notify::title", self._title_changed_cb)

        self.model = Model()
        self.model.connect('add_link', self._add_link_model_cb)

        self._main_view = gtk.VBox()
        self.set_canvas(self._main_view)
        self._main_view.show()

        self._main_view.pack_start(self._browser)
        self._browser.show()

        self._main_view.pack_start(self._tray, expand=False)
        self._tray.show()

        self.current = _('blank')
        self.webtitle = _('blank')
        self.connect('key-press-event', self.key_press_cb)
        self.sname =  _sugarext.get_prgname()
        _logger.debug('ProgName:  %s' %self.sname)

        if handle.uri:
            self._browser.load_uri(handle.uri)
            self.toolbox.set_current_toolbar(1)
        elif not self._jobject.file_path and not browser:
            # TODO: we need this hack until we extend the activity API for
            # opening URIs and default docs.
            self._load_homepage()

        _sugarext.set_prgname(self.sname)

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
            self.toolbox.set_current_toolbar(1)
            _logger.debug('Joined activity')                      
            self.connect('joined', self._joined_cb)
            if self.get_shared():
                # We've already joined
                self._joined_cb()
        else:   
            _logger.debug('Created activity')
    
    def _shared_cb(self, activity):
        _logger.debug('My activity was shared')        
        self.initiating = True                        
        self._setup()

        _logger.debug('This is my activity: making a tube...')
        id = self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].OfferDBusTube(
                SERVICE, {})
                
    def _setup(self):
        if self._shared_activity is None:
            _logger.debug('Failed to share or join activity')
            return

        bus_name, conn_path, channel_paths = self._shared_activity.get_channels()

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
                                                   telepathy.HANDLE_TYPE_ROOM, room, True)

        self.tubes_chan = tubes_chan
        self.text_chan = text_chan

        tubes_chan[telepathy.CHANNEL_TYPE_TUBES].connect_to_signal('NewTube', 
                                                                   self._new_tube_cb)

    def _list_tubes_reply_cb(self, tubes):
        for tube_info in tubes:
            self._new_tube_cb(*tube_info)

    def _list_tubes_error_cb(self, e):
        _logger.debug('ListTubes() failed: %s'%e)

    def _joined_cb(self, activity):
        if not self._shared_activity:
            return

        _logger.debug('Joined an existing shared activity')
        
        self.initiating = False
        self._setup()
                
        _logger.debug('This is not my activity: waiting for a tube...')
        self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].ListTubes(
            reply_handler=self._list_tubes_reply_cb, 
            error_handler=self._list_tubes_error_cb)

    def _new_tube_cb(self, id, initiator, type, service, params, state):
        _logger.debug('New tube: ID=%d initator=%d type=%d service=%s '
                     'params=%r state=%d' %(id, initiator, type, service, 
                     params, state))

        if (type == telepathy.TUBE_TYPE_DBUS and
            service == SERVICE):
            if state == telepathy.TUBE_STATE_LOCAL_PENDING:
                self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].AcceptDBusTube(id)

            self.tube_conn = TubeConnection(self.conn, 
                self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES], 
                id, group_iface=self.text_chan[telepathy.CHANNEL_INTERFACE_GROUP])
            
            _logger.debug('Tube created')
            self.messenger = Messenger(self.tube_conn, self.initiating, self.model)         

             
    def _load_homepage(self):
        if os.path.isfile(_LIBRARY_PATH):
            self._browser.load_uri('file://' + _LIBRARY_PATH)
        else:
            self._browser.load_uri('about:blank')
        _sugarext.set_prgname(self.sname)

    def _session_history_changed_cb(self, session_history, link):
        _logger.debug('NewPage: %s.' %link)
        self.current = link
        
    def _title_changed_cb(self, embed, pspec):
        if embed.props.title is not '':
            _logger.debug('Title changed=%s' % embed.props.title)
            self.webtitle = embed.props.title
            _sugarext.set_prgname("org.laptop.WebActivity")
            
    def read_file(self, file_path):
        if self.metadata['mime_type'] == 'text/plain':
            f = open(file_path, 'r')
            try:
                data = f.read()
            finally:
                f.close()
            self.model.deserialize(data)
            
            for link in self.model.data['shared_links']:
                _logger.debug('read: url=%s title=%s d=%s' % (link['url'],
                                                              link['title'],
                                                              link['color']))
                self._add_link_totray(link['url'],
                                      base64.b64decode(link['thumb']),
                                      link['color'], link['title'],
                                      link['owner'], -1, link['hash'])                                
            self._browser.set_session(self.model.data['history'])
        else:
            self._browser.load_uri(file_path)
            _sugarext.set_prgname(self.sname)
        
    def write_file(self, file_path):
        if not self.metadata['mime_type']:
            self.metadata['mime_type'] = 'text/plain'
        
        if self.metadata['mime_type'] == 'text/plain':
            if not self._jobject.metadata['title_set_by_user'] == '1':
                if self._browser.props.title:
                    self.metadata['title'] = self._browser.props.title

            self.model.data['history'] = self._browser.get_session()

            f = open(file_path, 'w')
            try:
                f.write(self.model.serialize())
            finally:
                f.close()

    def _link_add_button_cb(self, button):
        _logger.debug('button: Add link: %s.' % self.current)                
        self._add_link()
            
    def key_press_cb(self, widget, event):
        if event.state & gtk.gdk.CONTROL_MASK:
            if gtk.gdk.keyval_name(event.keyval) == "l":
                _logger.debug('keyboard: Add link: %s.' % self.current)                
                self._add_link()
                return True           
            elif gtk.gdk.keyval_name(event.keyval) == "v":
                # toggle visibility of tray
                self._tray_visibility()
                return True
            elif gtk.gdk.keyval_name(event.keyval) == "u":
                _logger.debug('keyboard: Show source of the current page')
                self._show_source()
                return True
        elif event.keyval == _VIEW_SOURCE_KEY_CODE:
            _logger.debug('keyboard: Show source of the current page SHOW_KEY')
            self._show_source()
            return True
        return False

    def _add_link(self):
        ''' take screenshot and add link info to the model '''
        for link in self.model.data['shared_links']:
            if link['hash'] == sha.new(self.current).hexdigest():
                _logger.debug('_add_link: link exist already a=%s b=%s' %(
                    link['hash'], sha.new(self.current).hexdigest()))
                return
        buffer = self._get_screenshot()
        timestamp = time.time()
        self.model.add_link(self.current, self.webtitle, buffer,
                            profile.get_nick_name(),
                            profile.get_color().to_string(), timestamp)

        if self.messenger is not None:
            self.messenger._add_link(self.current, self.webtitle,                                     
                                     profile.get_color().to_string(),
                                     profile.get_nick_name(),
                                     base64.b64encode(buffer), timestamp)

    def _add_link_model_cb(self, model, index):
        ''' receive index of new link from the model '''
        link = self.model.data['shared_links'][index]
        self._add_link_totray(link['url'], base64.b64decode(link['thumb']),
                              link['color'], link['title'],
                              link['owner'], index, link['hash'])

    def _add_link_totray(self, url, buffer, color, title, owner, index, hash):
        ''' add a link to the tray '''
        item = LinkButton(url, buffer, color, title, owner, index, hash)
        item.connect('clicked', self._link_clicked_cb, url)
        item.connect('remove_link', self._link_removed_cb)
        self._tray.add_item(item, index) # use index to add to the tray
        item.show()
        self._tray_numelems+=1
        if self._tray_isvisible == False:
            self._tray.show()
            self._tray_isvisible = True
            self.toolbar.tray_set_hide()

    def _link_removed_cb(self, button, hash):
        ''' remove a link from tray and delete it in the model '''
        self.model.remove_link(hash)
        self._tray.remove_item(button)
        self._tray_numelems-=1
        if self._tray_numelems == 0:
            self.toolbar.tray_set_empty()
            self._tray_isvisible = False

    def _link_clicked_cb(self, button, url):
        ''' an item of the link tray has been clicked '''
        self._browser.load_uri(url)

    def _tray_visibility_cb(self, toolbar):
        self._tray_visibility()

    def _tray_visibility(self):
        if self._tray_numelems > 0:
            if self._tray_isvisible is False:
                self.toolbar.tray_set_hide()
                self._tray.show()
                self._tray_isvisible = True
            else:
                self.toolbar.tray_set_show()
                self._tray.hide()
                self._tray_isvisible = False

    def _show_source(self):
        self._browser.get_source()

    def _pixbuf_save_cb(self, buf, data):
        data[0] += buf
        return True

    def get_buffer(self, pixbuf):
        data = [""]
        pixbuf.save_to_callback(self._pixbuf_save_cb, "png", {}, data)
        return str(data[0])

    def _get_screenshot(self):
        window = self._browser.window
        width, height = window.get_size()

        screenshot = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, has_alpha=False,
                                    bits_per_sample=8, width=width,
                                    height=height)
        screenshot.get_from_drawable(window, window.get_colormap(), 0, 0, 0, 0,
                                     width, height)

        screenshot = screenshot.scale_simple(style.zoom(100),
                                                 style.zoom(80),
                                                 gtk.gdk.INTERP_BILINEAR)

        buffer = self.get_buffer(screenshot)
        return buffer

    def destroy(self):
        if downloadmanager.can_quit():
            activity.Activity.destroy(self)
        else:
            downloadmanager.set_quit_callback(self._quit_callback_cb)

    def _quit_callback_cb(self):
        _logger.debug('_quit_callback_cb')
        activity.Activity.destroy(self)
