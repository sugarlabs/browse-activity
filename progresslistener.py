# Copyright (C) 2006, Red Hat, Inc.
# Copyright (C) 2007, One Laptop Per Child
# Copyright (C) 2009, Tomeu Vizoso
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

import gobject
import xpcom
from xpcom.components import interfaces


class ProgressListener(gobject.GObject):
    _com_interfaces_ = interfaces.nsIWebProgressListener

    def __init__(self):
        gobject.GObject.__init__(self)

        self._location = None
        self._loading = False
        self._progress = 0.0
        self._total_requests = 0
        self._completed_requests = 0

        self._wrapped_self = xpcom.server.WrapObject( \
                self, interfaces.nsIWebProgressListener)
        weak_ref = xpcom.client.WeakReference(self._wrapped_self)

    def setup(self, browser):
        mask = interfaces.nsIWebProgress.NOTIFY_STATE_NETWORK | \
               interfaces.nsIWebProgress.NOTIFY_STATE_REQUEST | \
               interfaces.nsIWebProgress.NOTIFY_LOCATION

        browser.web_progress.addProgressListener(self._wrapped_self, mask)

    def _reset_requests_count(self):
        self._total_requests = 0
        self._completed_requests = 0

    def onLocationChange(self, webProgress, request, location):
        self._location = location
        self.notify('location')

    def onProgressChange(self, webProgress, request, curSelfProgress,
                         maxSelfProgress, curTotalProgress, maxTotalProgress):
        pass

    def onSecurityChange(self, webProgress, request, state):
        pass

    def onStateChange(self, webProgress, request, stateFlags, status):
        if stateFlags & interfaces.nsIWebProgressListener.STATE_IS_REQUEST:
            if stateFlags & interfaces.nsIWebProgressListener.STATE_START:
                self._total_requests += 1
            elif stateFlags & interfaces.nsIWebProgressListener.STATE_STOP:
                self._completed_requests += 1

        if stateFlags & interfaces.nsIWebProgressListener.STATE_IS_NETWORK:
            if stateFlags & interfaces.nsIWebProgressListener.STATE_START:
                self._loading = True
                self._reset_requests_count()
                self.notify('loading')
            elif stateFlags & interfaces.nsIWebProgressListener.STATE_STOP:
                self._loading = False
                self.notify('loading')

        if self._total_requests < self._completed_requests:
            self._progress = 1.0
        elif self._total_requests > 0:
            self._progress = \
                    self._completed_requests / float(self._total_requests)
        else:
            self._progress = 0.0
        self.notify('progress')

    def onStatusChange(self, webProgress, request, status, message):
        pass

    def _get_location(self):
        return self._location

    location = gobject.property(type=object, getter=_get_location)

    def _get_loading(self):
        return self._loading

    loading = gobject.property(type=bool, default=False, getter=_get_loading)

    def _get_progress(self):
        return self._progress

    progress = gobject.property(type=float, getter=_get_progress)
