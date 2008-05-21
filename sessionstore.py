# Copyright (C) 2007, One Laptop Per Child
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

# Based on
# http://lxr.mozilla.org/seamonkey/source/browser/components/sessionstore

import logging

from xpcom import components
from xpcom.components import interfaces

def get_session(browser):
    session_history = browser.web_navigation.sessionHistory
        
    if session_history.count == 0:
        return ''        
    return _get_history(session_history)            
    
def set_session(browser, data):
    _set_history(browser.web_navigation.sessionHistory, data)
        
    if data:
        browser.web_navigation.gotoIndex(len(data) - 1)
    else:
        browser.load_uri('about:blank')

def _get_history(history):
    logging.debug('%r' % history.count)
    entries_dest = []
    for i in range(0, history.count):
        entry_orig = history.getEntryAtIndex(i, False)
        entry_dest = {'url':    entry_orig.URI.spec,
                      'title':  entry_orig.title}

        entries_dest.append(entry_dest)

    return entries_dest

def _set_history(history, history_data):
    history_internal = history.queryInterface(interfaces.nsISHistoryInternal)
    
    if history_internal.count > 0:
        history_internal.purgeHistory(history_internal.count)

    for entry_dict in history_data:
        logging.debug('entry_dict: %r' % entry_dict)
        entry_class = components.classes[ \
                "@mozilla.org/browser/session-history-entry;1"]
        entry = entry_class.createInstance(interfaces.nsISHEntry)
                  
        io_service_class = components.classes[ \
                "@mozilla.org/network/io-service;1"]
        io_service = io_service_class.getService(interfaces.nsIIOService)
        entry.setURI(io_service.newURI(entry_dict['url'], None, None))
        entry.setTitle(entry_dict['title'])

        history_internal.addEntry(entry, True)

