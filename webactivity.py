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

from sugar.activity import activity
from sugar import env
from sugar.graphics import style
import telepathy
import telepathy.client
from sugar import _sugarext
from sugar.presence import presenceservice

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

from linktoolbar import LinkToolbar
from model import Model
from tubeconn import TubeConnection
from messenger import Messenger

SERVICE = "org.laptop.WebActivity"
IFACE = SERVICE
PATH = "/org/laptop/WebActivity"

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

        toolbar = WebToolbar(self._browser)
        toolbox.add_toolbar(_('Browse'), toolbar)
        toolbar.show()

        self.set_toolbox(toolbox)
        toolbox.show()

        self.linkbar = LinkToolbar()
        self.linkbar.connect('link-selected', self._link_selected_cb)
        self.linkbar.connect('link-rm', self._link_rm_cb)
        self.session_history = sessionhistory.get_instance()
        self.session_history.connect('session-link-changed', self._session_history_changed_cb)
        
        self._browser.connect("notify::title", self._title_changed_cb)
        self.model = Model(os.path.dirname(__file__))
        
        self._main_view = gtk.VBox()
        self.set_canvas(self._main_view)
        self._main_view.show()
        
        self._main_view.pack_start(self._browser)
        self._browser.show()

        self._main_view.pack_start(self.linkbar, expand=False)
        self.linkbar.show()

        self.current = _('blank')
        self.webtitle = _('blank')
        self.connect('key-press-event', self.key_press_cb)
        self.sname =  _sugarext.get_prgname()
        _logger.debug('ProgName:  %s' %self.sname)
        
        if handle.uri:
            self._browser.load_uri(handle.uri)
        elif not self._jobject.file_path and not browser:
            # TODO: we need this hack until we extend the activity API for
            # opening URIs and default docs.
            self._load_homepage()

        _sugarext.set_prgname(self.sname)
                    
        self.set_title('WebActivity')
        self.messenger = None
        self.connect('shared', self._shared_cb)
                                
        # Get the Presence Service
        self.pservice = presenceservice.get_instance()
        name, path = self.pservice.get_preferred_connection()
        self.tp_conn_name = name
        self.tp_conn_path = path
        self.conn = telepathy.client.Connection(name, path)
        self.initiating = None
            
        if self._shared_activity is not None:
            _logger.debug('shared:  %s' %self._shared_activity.props.joined)

        self.owner = self.pservice.get_owner()
        if self._shared_activity is not None:
            # We are joining the activity
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
        id = self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].OfferTube(
            telepathy.TUBE_TYPE_DBUS, SERVICE, {})
        
        
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
                self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].AcceptTube(id)

            self.tube_conn = TubeConnection(self.conn, 
                self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES], 
                id, group_iface=self.text_chan[telepathy.CHANNEL_INTERFACE_GROUP])
            
            _logger.debug('Tube created')
            self.messenger = Messenger(self.tube_conn, self.initiating, self.model, self.linkbar, self.owner)         

             
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
            #self.set_title(embed.props.title)            
            _logger.debug('Title changed=%s' % embed.props.title)
            self.webtitle = embed.props.title
            _sugarext.set_prgname("org.laptop.WebActivity")
            
    def read_file(self, file_path):
        if self.metadata['mime_type'] == 'text/plain':
            self.model.read(file_path)
            i=0
            for link in self.model.links:
                _logger.debug('read: url=%s title=%s d=%s' % (link['url'], link['title'], link['color']))
                if link['deleted'] == 0:
                    self.linkbar._add_link(link['url'], link['thumb'], link['color'], link['title'], link['owner'], i)                    
                i+=1
                
            if self.model.session_data is not '':                
                self._browser.set_session(self.model.session_data)                
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

            for link in self.model.links:
                _logger.debug('write: url=%s title=%s d=%s' % (link['url'], link['title'], link['color']))

            self.model.session_data = self._browser.get_session()                
            _logger.debug('Trying save session: %s.' % self.model.session_data)
            self.model.write(file_path)
            
    def destroy(self):
        if downloadmanager.can_quit():
            activity.Activity.destroy(self)
        else:
            downloadmanager.set_quit_callback(self._quit_callback_cb)

    def _quit_callback_cb(self):
        _logger.debug('_quit_callback_cb')
        activity.Activity.destroy(self)

    def _link_selected_cb(self, linkbar, link):
        self._browser.load_uri(link)

    def _link_rm_cb(self, linkbar, index):
        self.model.links[index]['deleted'] = 1
        self.model.links[index]['thumb'] = ''
            
    def key_press_cb(self, widget, event):        
        if event.state & gtk.gdk.CONTROL_MASK:
            if gtk.gdk.keyval_name(event.keyval) == "l":
                buffer = self._get_screenshot()
                _logger.debug('keyboard: Add link: %s.' % self.current)                
                self.model.links.append( {'hash':sha.new(self.current).hexdigest(), 'url':self.current, 'title':self.webtitle,
                                          'thumb':buffer, 'owner':self.owner.props.nick, 'color':self.owner.props.color, 'deleted':0} )

                self.linkbar._add_link(self.current, buffer, self.owner.props.color, self.webtitle, self.owner.props.nick,
                                       len(self.model.links)-1)
                if self.messenger is not None:
                    import base64
                    self.messenger._add_link(self.current, self.webtitle, self.owner.props.color,
                                             self.owner.props.nick, base64.b64encode(buffer))
                return True
            elif gtk.gdk.keyval_name(event.keyval) == "r":
                _logger.debug('keyboard: Remove link: %s.' % self.current)
                current = self.linkbar._rm_link()
                self.model.links[current]['deleted'] = 1
                self.model.links[current]['thumb'] = ''
                return True
        return False


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
                                    bits_per_sample=8, width=width, height=height)
        screenshot.get_from_drawable(window, window.get_colormap(), 0, 0, 0, 0,
                                     width, height)

        screenshot = screenshot.scale_simple(style.zoom(160),
                                                 style.zoom(120),
                                                 gtk.gdk.INTERP_BILINEAR)

        buffer = self.get_buffer(screenshot)
        return buffer
