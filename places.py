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

import os
import sqlite3

from sugar.activity import activity

_store = None

class Place(object):
    def __init__(self, uri=None):
        self.uri = uri
        self.title = None
        self.gecko_flags = 0
        self.visits = 0

class SqliteStore(object):
    def __init__(self):
        db_path = os.path.join(activity.get_activity_root(),
                               'data', 'places.db')

        self._con = sqlite3.connect(db_path)
        cur = self._con.cursor()

        cur.execute('select * from sqlite_master where name == "places"')
        if cur.fetchone() == None:
            cur.execute("""create table places (
                             uri         TEXT,
                             title       TEXT,
                             gecko_flags INTEGER,
                             visits      INTEGER
                           );
                        """)

    def search(self, text):
        cur = self._con.cursor()

        text = '%' + text + '%'
        cur.execute('select * from places where uri like ? or title like ? ' \
                    'order by visits desc limit 0, 30', (text, text))

        return [_place_from_row(row) for row in cur]

    def add_place(self, place):
        cur = self._con.cursor()

        cur.execute('insert into places values (?, ?, ?, ?)', \
                    (place.uri, place.title, place.gecko_flags, place.visits))

        self._con.commit()

    def lookup_place(self, uri):
        cur = self._con.cursor()
        cur.execute('select * from places where uri=?', (uri,))

        row = cur.fetchone()
        if row:
            return _place_from_row(row)
        else:
            return None

    def update_place(self, place):
        cur = self._con.cursor()

        cur.execute('update places set title=?, gecko_flags=?, visits=? ' \
                    'where uri=?', (place.title, place.gecko_flags,
                    place.visits, place.uri))

        self._con.commit()

def _place_from_row(row):
    place = Place()
    place.uri, place.title, place.gecko_flags, place.visits = row
    return place

def get_store():
    global _store
    if _store == None:
        _store = SqliteStore()
    return _store
