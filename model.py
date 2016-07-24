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
from hashlib import sha1


class Model(GObject.GObject):
    ''' The model of web-activity which uses json to serialize its data
    to a file and deserealize from it.
    '''

    add_link_signal = GObject.Signal('add_link', arg_types=[int, bool])
    link_removed_signal = GObject.Signal('link-removed')

    def __init__(self):
        GObject.GObject.__init__(self)
        self.data = {}
        self.data['shared_links'] = []

    def has_link(self, uri):
        '''returns true if the uri is already bookmarked, O(n) oddly'''
        for link in self.data['shared_links']:
            if link['hash'] == sha1(uri).hexdigest():
                return True
        return False

    def add_link(self, url, title, thumb, owner, color, timestamp,
                 by_me=False):
        info = {'hash': sha.new(str(url)).hexdigest(), 'url': str(url),
                'title': str(title), 'thumb': thumb,
                'owner': str(owner), 'color': str(color),
                'timestamp': float(timestamp)}
        self.add_link_from_info(info, by_me)

    def add_link_from_info(self, info_dict, by_me=False):
        index = len(self.data['shared_links'])
        for item in self.data['shared_links']:
            if info_dict['timestamp'] <= item['timestamp']:
                index = self.data['shared_links'].index(item)
                break

        self.data['shared_links'].insert(index, info_dict)
        self.add_link_signal.emit(index, by_me)

    def remove_link(self, hash):
        for link in self.data['shared_links']:
            if link['hash'] == hash:
                self.data['shared_links'].remove(link)
                self.link_removed_signal.emit()
                break

    def change_link_notes(self, hash, notes):
        for link in self.data['shared_links']:
            if link['hash'] == hash:
                link['notes'] = notes

    def serialize(self):
        return json.dumps(self.data)

    def deserialize(self, data):
        self.data = json.loads(data)
        self.data.setdefault('shared_links', [])

    def get_links_ids(self):
        ids = []
        for link in self.data['shared_links']:
            ids.append(link['hash'])
        ids.append('')
        return ids
