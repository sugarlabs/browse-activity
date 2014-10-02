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

from datetime import datetime

import places

_global_history = None


class GlobalHistory(object):
    def __init__(self):
        self._store = places.get_store()

    def add_page(self, uri):
        place = self._store.lookup_place(uri)
        if place:
            place.visits += 1
            place.last_visit = datetime.now()
            self._store.update_place(place)
        else:
            place = places.Place(uri)
            self._store.add_place(place)

    def set_page_title(self, uri, title):
        place = self._store.lookup_place(uri)
        if place:
            place.title = title
            self._store.update_place(place)


def get_global_history():
    global _global_history
    if _global_history is None:
        _global_history = GlobalHistory()
    return _global_history
