#
#    Copyright (C) 2006, 2007, One Laptop Per Child
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

import os
import logging
import json
import sha
import gobject

_logger = logging.getLogger('model')

class Model(gobject.GObject):
    ''' The model of the activity which uses json to serialize its data
    to a file and deserelize from it. 
    '''
    __gsignals__ = {
        'add_link': (gobject.SIGNAL_RUN_FIRST,
                     gobject.TYPE_NONE, ([int]))
        }
    
    def __init__(self):
        gobject.GObject.__init__(self)    

        self.data = {}
        self._links = []
        self.data['shared_links'] = self._links

    def add_link(self, url, title, thumb, owner, color):
        self.links.append( {'hash':sha.new(url).hexdigest(), 'url':url, 'title':title, 'thumb':thumb,
                            'owner':owner, 'color':color, 'deleted':0} )        
        self.emit('add_link', len(self.links)-1)

    def mark_link_deleted(self, index):
        self._links[index]['deleted'] = 1
        self._links[index]['thumb'] = ''
        
    def serialize(self):
        self.get_session()
        return json.write(self.data)

    def deserialize(self, data):
        self.data = json.read(data)                
        self.links = self.data
        
    def get_links_ids(self):
        ids = []
        for link in self._links:
            ids.append(link['hash'])
        ids.append('')    
        return ids
    
