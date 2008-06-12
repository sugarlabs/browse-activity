# Copyright (C) 2008, Red Hat, Inc.
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

_store = None

class Place(object):
    def __init__(self, uri):
        self.uri = uri
        self.redirect = False
        self.toplevel = True
        self.referrer = None
        self.title = None
        self.gecko_flags = 0
        self.visits = 0

class MemoryStore(object):
    def __init__(self):
        self._places = {}

    def search(self, text):
        result = []
        for place in self._places.values():
            if text in place.uri or text in place.title:
                result.append(place)
        return result

    def add_place(self, place):
        self._places[place.uri] = place

    def lookup_place(self, uri):
        try:
            return self._places[uri]
        except KeyError:
            return None

    def update_place(self, place):
        self._places[place.uri] = place

class SQliteStore(object):
    def __init__(self):
        pass

    def search(self, text):
        pass

    def add_place(self, place):
        pass

    def lookup_place(self, uri):
        pass

    def update_place(self, place):
        pass

def get_store():
    global _store
    if _store == None:
        _store = MemoryStore()
    return _store
