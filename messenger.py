#
#    Copyright (C) 2007, One Laptop Per Child
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import logging
import os
import dbus
from dbus.gobject_service import ExportedGObject
import base64

SERVICE = "org.laptop.WebActivity"
IFACE = SERVICE
PATH = "/org/laptop/WebActivity"

_logger = logging.getLogger('messenger')

class Messenger(ExportedGObject):
    def __init__(self, tube, is_initiator, model, owner):
        ExportedGObject.__init__(self, tube, PATH)
        self.tube = tube
        self.is_initiator = is_initiator
        self.members = []
        self.entered = False
        self.model = model
        self.owner = owner
        self.tube.watch_participants(self.participant_change_cb)

    def participant_change_cb(self, added, removed):
        _logger.debug('Participants change add=%s    rem=%s'
                      %(added, removed))
        for handle, bus_name in added:
            _logger.debug('Add member handle=%s  bus_name=%s'
                          %(str(handle), str(bus_name)))
            self.members.append(bus_name)
                    
        for handle, bus_name in removed:
            _logger.debug('Remove member handle=%s  bus_name=%s'
                          %(str(handle), str(bus_name)))
            try:
                self.members.remove(bus_name)
            except ValueError:
                # already absent
                pass        
                
        if not self.entered:
            self.tube.add_signal_receiver(self._add_link_receiver, '_add_link',
                                          IFACE, path=PATH,
                                          sender_keyword='sender',
                                          byte_arrays=True)
            if self.is_initiator:
                _logger.debug('Initialising a new shared browser, I am %s .'
                              %self.tube.get_unique_name())                
            else:               
                # sync with other members
                self.bus_name = self.tube.get_unique_name()
                _logger.debug('Joined I am %s .'%self.bus_name)                
                for member in self.members:
                    if member != self.bus_name:
                        _logger.debug('Get info from %s' %member)
                        self.tube.get_object(member, PATH).sync_with_members(
                            self.model.get_links_ids(), dbus_interface=IFACE,
                            reply_handler=self.reply_sync, error_handler=lambda
                            e:self.error_sync(e, 'transfering file'))
                                                                         
        self.entered = True
        
    def reply_sync(self, a_ids):
        a_ids.pop()                    
        for link in self.model.data['shared_links']:
            if link['hash'] not in a_ids:
                if link['deleted'] == 0:
                    self.tube.get_object(sender, PATH).send_link(
                        link['hash'], link['url'], link['title'], link['color'],
                        link['owner'], link['thumb'])
            
    def error_sync(self, e, when):    
        _logger.error('Error %s: %s'%(when, e))

    @dbus.service.method(dbus_interface=IFACE, in_signature='as', out_signature='as', sender_keyword='sender')
    def sync_with_members(self, b_ids, sender=None):
        '''Sync with members '''
        b_ids.pop()
        # links the caller wants from me
        for link in self.model.data['shared_links']:
            if link['hash'] not in b_ids:
                if link['deleted'] == 0:
                    self.tube.get_object(sender, PATH).send_link(link['hash'], link['url'], link['title'], link['color'],
                                                                 link['owner'], link['thumb'])
        a_ids = self.model.get_links_ids()
        a_ids.append('')
        # links I want from the caller
        return a_ids                        
        
    @dbus.service.method(dbus_interface=IFACE, in_signature='ssssss', out_signature='')
    def send_link(self, id, url, title, color, owner, buffer):
        '''Send link'''
        a_ids = self.model.get_links_ids()
        if id not in a_ids:
            thumb = base64.b64decode(buffer)
            self.model.add_link(url, title, thumb, owner, color)
                    
    @dbus.service.signal(IFACE, signature='sssss')
    def _add_link(self, url, title, color, owner, thumb):        
        '''Signal to send the link information (add)'''
        _logger.debug('Add Link: %s '%url)
        
    def _add_link_receiver(self, url, title, color, owner, buffer, sender=None):
        '''Member sent a link'''
        handle = self.tube.bus_name_to_handle[sender]            
        if self.tube.self_handle != handle:
            thumb = base64.b64decode(buffer)
            self.model.add_link(url, title, thumb, owner, color)            
            _logger.debug('Added link: %s to linkbar.'%(url))
    
