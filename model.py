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

import cjson
import sha
import gobject
import base64

class Model(gobject.GObject):
    ''' The model of web-activity which uses json to serialize its data
    to a file and deserealize from it. 
    '''
    __gsignals__ = {
        'add_link': (gobject.SIGNAL_RUN_FIRST,
                     gobject.TYPE_NONE, ([int]))
        }
    
    def __init__(self):
        gobject.GObject.__init__(self)    
        self.data = {}
        self.data['shared_links'] = []
        self.data['deleted'] = []
        
    def add_link(self, url, title, thumb, owner, color, timestamp):
        index = len(self.data['shared_links'])
        for item in self.data['shared_links']:
            if timestamp <= item['timestamp']: 
                index = self.data['shared_links'].index(item)
                break
        
        self.data['shared_links'].insert(index,
                                         {'hash':sha.new(str(url)).hexdigest(),
                                          'url':str(url), 'title':str(title),
                                          'thumb':base64.b64encode(thumb),
                                          'owner':str(owner), 
                                          'color':str(color),
                                          'timestamp':float(timestamp)})
        self.emit('add_link', index)

    def remove_link(self, hash):
        for link in self.data['shared_links']:
            if link['hash'] == hash:
                self.data['deleted'].append(link['hash'])
                self.data['shared_links'].remove(link)
                break                
        
    def serialize(self):
        return cjson.encode(self.data)

    def deserialize(self, data):
        self.data = cjson.decode(data)
        if not self.data.has_key('shared_links'):
            self.data['shared_links'] = []
        if not self.data.has_key('deleted'):
            self.data['deleted'] = []
        
    def get_links_ids(self):
        ids = []
        for link in self.data['shared_links']:
            ids.append(link['hash'])
        ids.extend(self.data['deleted'])
        ids.append('')    
        return ids
    
