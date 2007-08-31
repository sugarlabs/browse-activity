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
import base64
import json

from xpcom import components
from xpcom.components import interfaces

_logger = logging.getLogger('model')

class Model(object):
    ''' The model of the activity which uses json to serialize its data
    to a file and deserelize from it. 
    '''
    
    def __init__(self):
        self.data = {}
        self.links = []
                                
    def serialize(self):
        self.get_session()
        return json.write(self.data)

    def deserialize(self, data):
        self.data = json.read(data)                
        self.links = self.data
        
    def get_links_ids(self):
        ids = []
        for link in self.links:
            ids.append(link['hash'])
        ids.append('')    
        return ids
    
