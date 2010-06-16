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

from xpcom import components
from xpcom.components import interfaces
from xpcom.server.factory import Factory

import places


class GlobalHistory:
    _com_interfaces_ = interfaces.nsIGlobalHistory, \
                       interfaces.nsIGlobalHistory2, \
                       interfaces.nsIGlobalHistory3

    cid = '{2a53cf28-c48e-4a01-ba18-3d3fef3e2985}'
    description = 'Sugar Global History'

    def __init__(self):
        self._store = places.get_store()

    def addPage(self, url):
        self.addURI(url, False, True, None)

    def isVisited(self, uri):
        place = self._store.lookup_place(uri.spec)
        return place != None

    def addURI(self, uri, redirect, toplevel, referrer):
        place = self._store.lookup_place(uri.spec)
        if place:
            place.visits += 1
            place.last_visit = datetime.now()
            self._store.update_place(place)
        else:
            place = places.Place(uri.spec)
            self._store.add_place(place)

    def setPageTitle(self, uri, title):
        place = self._store.lookup_place(uri.spec)
        if place:
            place.title = title
            self._store.update_place(place)

    def addDocumentRedirect(self, old_channel, new_channel, flags, toplevel):
        pass

    def getURIGeckoFlags(self, uri):
        place = self._store.lookup_place(uri.spec)
        if place:
            return place.gecko_flags
        else:
            return 0

    def setURIGeckoFlags(self, uri, flags):
        place = self._store.lookup_place(uri.spec)
        if place:
            place.gecko_flags = flags
            self._store.update_place(place)


components.registrar.registerFactory(GlobalHistory.cid,
                                     GlobalHistory.description,
                                     '@mozilla.org/browser/global-history;2',
                                     Factory(GlobalHistory))
