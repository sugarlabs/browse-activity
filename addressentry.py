# Copyright (C) 2007, One Laptop Per Child
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.
import gobject

import _sugar
from sugar.graphics.entry import Entry

class AddressEntry(Entry):
    __gtype_name__ = 'WebAddressEntry'

    __gproperties__ = {
        'title'    : (str, None, None, None, gobject.PARAM_READWRITE),
        'address'  : (str, None, None, None, gobject.PARAM_READWRITE),
        'progress' : (float, None, None, 0.0, 1.0, 0.0, gobject.PARAM_READWRITE)
    }
    
    def __init__(self):
        Entry.__init__(self)

    def create_entry(self):
        self._address_entry = _sugar.AddressEntry()
        return self._address_entry
