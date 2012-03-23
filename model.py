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

import json
import sha
from gi.repository import GObject
import base64


class Model(GObject.GObject):
    ''' The model of web-activity which uses json to serialize its data
    to a file and deserealize from it.
    '''
    __gsignals__ = {
        'add_link': (GObject.SignalFlags.RUN_FIRST,
                     None, ([int])),
        }

    def __init__(self):
        GObject.GObject.__init__(self)
        self.data = {}
        self.data['shared_links'] = []
        self.data['deleted'] = []

    def add_link(self, url, title, thumb, owner, color, timestamp):
        index = len(self.data['shared_links'])
        for item in self.data['shared_links']:
            if timestamp <= item['timestamp']:
                index = self.data['shared_links'].index(item)
                break

        info = {'hash': sha.new(str(url)).hexdigest(), 'url': str(url),
                'title': str(title), 'thumb': base64.b64encode(thumb),
                'owner': str(owner), 'color': str(color),
                'timestamp': float(timestamp)}
        self.data['shared_links'].insert(index, info)
        self.emit('add_link', index)

    def remove_link(self, hash):
        for link in self.data['shared_links']:
            if link['hash'] == hash:
                self.data['deleted'].append(link['hash'])
                self.data['shared_links'].remove(link)
                break

    def serialize(self):
        return json.dumps(self.data)

    def deserialize(self, data):
        self.data = json.loads(data)
        self.data.setdefault('shared_links', [])
        self.data.setdefault('deleted', [])

    def get_links_ids(self):
        ids = []
        for link in self.data['shared_links']:
            ids.append(link['hash'])
        ids.extend(self.data['deleted'])
        ids.append('')
        return ids
