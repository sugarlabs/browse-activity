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
from datetime import datetime, timedelta

from sugar3.activity import activity

_store = None


class Place(object):
    def __init__(self, uri=''):
        self.uri = uri
        self.title = ''
        self.bookmark = False
        self.gecko_flags = 0
        self.visits = 0
        self.last_visit = datetime.now()


class SqliteStore(object):
    MAX_SEARCH_MATCHES = 7
    EXPIRE_DAYS = 30

    def __init__(self):
        db_path = os.path.join(activity.get_activity_root(),
                               'data', 'places.db')

        self._connection = sqlite3.connect(db_path)
        cursor = self._connection.cursor()

        cursor.execute('select * from sqlite_master where name == "places"')
        if cursor.fetchone() is None:
            # Create table to store the visited places.  Note that
            # bookmark and gecko_flags fields aren't used anymore in
            # WebKit port, but are kept for backwards compatibility.
            cursor.execute("""create table places (
                                uri         text,
                                title       text,
                                bookmark    boolean,
                                gecko_flags integer,
                                visits      integer,
                                last_visit  timestamp
                              );
                           """)
        else:
            self._cleanup()

    def search(self, text):
        cursor = self._connection.cursor()

        try:
            text = '%' + text + '%'
            cursor.execute('select uri, title, bookmark, gecko_flags, '
                           'visits, last_visit from places '
                           'where uri like ? or title like ? '
                           'order by visits desc limit 0, ?',
                           (text, text, self.MAX_SEARCH_MATCHES))

            result = [self._place_from_row(row) for row in cursor]
        finally:
            cursor.close()

        return result

    def add_place(self, place):
        cursor = self._connection.cursor()

        try:
            cursor.execute('insert into places (uri, title, bookmark, '
                           'gecko_flags, visits, last_visit) '
                           'values (?, ?, ?, ?, ?, ?)',
                           (place.uri, place.title, place.bookmark,
                            place.gecko_flags, place.visits, place.last_visit))
            self._connection.commit()
        finally:
            cursor.close()

    def lookup_place(self, uri):
        cursor = self._connection.cursor()

        try:
            cursor.execute('select uri, title, bookmark, gecko_flags,visits, '
                           'last_visit from places where uri=?', (uri,))

            row = cursor.fetchone()
            if row:
                return self._place_from_row(row)
            else:
                return None
        finally:
            cursor.close()

    def update_place(self, place):
        cursor = self._connection.cursor()

        try:
            cursor.execute('update places set title=?, gecko_flags=?, '
                           'visits=?, last_visit=?, bookmark=? where uri=?',
                           (place.title, place.gecko_flags, place.visits,
                            place.last_visit, place.bookmark, place.uri))
            self._connection.commit()
        finally:
            cursor.close()

    def _place_from_row(self, row):
        place = Place()

        # Return uri and title as empty strings instead of None.
        # Previous versions of Browse were allowing to store None for
        # those fields in the places database.  See ticket #3400 .
        if row[0] is None:
            row = tuple([''] + list(row[1:]))
        if row[1] is None:
            row = tuple([row[0], ''] + list(row[2:]))

        place.uri, place.title, place.bookmark, place.gecko_flags, \
            place.visits, place.last_visit = row

        return place

    def _cleanup(self):
        cursor = self._connection.cursor()

        try:
            date = datetime.now() - timedelta(days=self.EXPIRE_DAYS)
            cursor.execute('delete from places where last_visit < ?', (date,))
            self._connection.commit()
        finally:
            cursor.close()


def get_store():
    global _store
    if _store is None:
        _store = SqliteStore()
    return _store
