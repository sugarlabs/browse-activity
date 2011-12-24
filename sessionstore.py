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

import logging

from gi.repository import WebKit


def get_session(browser):
    session_history = browser.get_back_forward_list()
    if session_history.get_back_length() == 0:
        return ''
    return _get_history(session_history)


def set_session(browser, data):
    session_history = browser.get_back_forward_list()
    _set_history(session_history, data)


def _get_history(history):
    items_list = _items_history_as_list(history)
    logging.debug('history count: %r', len(items_list))
    entries_dest = []
    for item in items_list:
        entry_dest = {'url': item.get_uri(),
                      'title': item.get_title()}
        entries_dest.append(entry_dest)

    return entries_dest


def _set_history(history, history_data):
    history.clear()
    for entry in history_data:
        uri, title = entry['url'], entry['title']
        history_item = WebKit.WebHistoryItem.new_with_data(uri, title)
        history.add_item(history_item)


def get_history_index(browser):
    """Return the index of the current item in the history."""
    history = browser.get_back_forward_list()
    history_list = _items_history_as_list(history)
    current_item = history.get_current_item()
    return history_list.index(current_item)


def set_history_index(browser, index):
    """Go to the item in the history specified by the index."""
    history = browser.get_back_forward_list()
    history_list = _items_history_as_list(history)
    last_index = len(history_list) - 1
    for i in range(last_index - index):
        browser.go_back()
    if index == last_index:
        browser.go_back()
        browser.go_forward()


def _items_history_as_list(history):
    """Return a list with the items of a WebKit.WebBackForwardList."""
    back_items = []
    for n in reversed(range(1, history.get_back_length() + 1)):
        item = history.get_nth_item(n * -1)
        back_items.append(item)

    current_item = [history.get_current_item()]

    forward_items = []
    for n in range(1, history.get_forward_length() + 1):
        item = history.get_nth_item(n)
        forward_items.append(item)

    all_items = back_items + current_item + forward_items
    return all_items
