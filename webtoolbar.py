# Copyright (C) 2006, Red Hat, Inc.
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
import logging
from gettext import gettext as _

import hippo
import gtk

from addressentry import AddressEntry

from sugar.graphics.toolbar import Toolbar
from sugar.graphics.iconbutton import IconButton
from sugar.graphics.filechooser import FileChooserDialog

class WebToolbar(Toolbar):
    def __init__(self, embed):
        Toolbar.__init__(self)
        
        self._back = IconButton(icon_name='theme:stock-back')
        self._back.props.active = False
        self._back.connect("activated", self._go_back_cb)
        self.append(self._back)

        self._forward = IconButton(icon_name='theme:stock-forward')
        self._forward.props.active = False
        self._forward.connect("activated", self._go_forward_cb)
        self.append(self._forward)

        self._stop_and_reload = IconButton(icon_name='theme:stock-close')
        self._stop_and_reload.connect("activated", self._stop_and_reload_cb)
        self.append(self._stop_and_reload)

        self._entry = AddressEntry()
        self._entry.connect("activated", self._entry_activate_cb)
        self.append(self._entry, hippo.PACK_EXPAND)

        self._post = IconButton(icon_name='theme:stock-add')
        self._post.props.active = False
        self._post.connect("activated", self._post_cb)
        self.append(self._post)
        
        self._open = IconButton(icon_name='theme:stock-open')
        self._open.connect("activated", self._open_cb)
        self.append(self._open)
        
        self._save = IconButton(icon_name='theme:stock-save')
        self._save.connect("activated", self._save_cb)
        self.append(self._save)

        self._embed = embed
        self._embed.connect("notify::progress", self._progress_changed_cb)
        self._embed.connect("notify::loading", self._loading_changed_cb)
        self._embed.connect("notify::address", self._address_changed_cb)
        self._embed.connect("notify::title", self._title_changed_cb)
        self._embed.connect("notify::can-go-back",
                            self._can_go_back_changed_cb)
        self._embed.connect("notify::can-go-forward",
                            self._can_go_forward_changed_cb)

        self._update_stop_and_reload_icon()

    def set_links_controller(self, links_controller):
        self._links_controller = links_controller
        self._post.props.active = True

    def _update_stop_and_reload_icon(self):
        if self._embed.props.loading:
            self._stop_and_reload.props.icon_name = 'theme:stock-close'
        else:
            self._stop_and_reload.props.icon_name = 'theme:stock-continue'

    def _progress_changed_cb(self, embed, spec):
        self._entry.props.progress = embed.props.progress

    def _loading_changed_cb(self, embed, spec):
        self._update_stop_and_reload_icon()

    def _address_changed_cb(self, embed, spec):
        self._entry.props.address = embed.props.address

    def _title_changed_cb(self, embed, spec):
        self._entry.props.title = embed.props.title

    def _can_go_back_changed_cb(self, embed, spec):
        self._back.props.active = embed.props.can_go_back

    def _can_go_forward_changed_cb(self, embed, spec):
        self._forward.props.active = embed.props.can_go_forward

    def _entry_activate_cb(self, entry):
        self._embed.load_url(entry.props.text)
        self._embed.grab_focus()

    def _go_back_cb(self, button):
        self._embed.go_back()
    
    def _go_forward_cb(self, button):
        self._embed.go_forward()

    def _stop_and_reload_cb(self, button):
        if self._embed.props.loading:
            self._embed.stop_load()
        else:
            self._embed.reload(0)

    def _post_cb(self, button):
        title = self._embed.get_title()
        address = self._embed.get_location()
        self._links_controller.post_link(title, address)

    def _save_cb(self, button):
        filename = self._embed.props.document_metadata.filename
        print filename
        if not filename:
            filename = self._embed.get_title() + '.html'

        chooser = FileChooserDialog(title=None,
                                    parent=self._embed.get_toplevel(),
                                    action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                    buttons=(gtk.STOCK_CANCEL,
                                             gtk.RESPONSE_CANCEL,
                                             gtk.STOCK_SAVE,
                                             gtk.RESPONSE_OK))
        chooser.set_default_response(gtk.RESPONSE_OK)
        chooser.set_current_folder(os.path.expanduser('~'))
        chooser.set_current_name(filename)
        response = chooser.run()

        if response == gtk.RESPONSE_OK:
            if not self._embed.save_document(chooser.get_filename()):
                logging.error("Couldn't save to %s." % chooser.get_filename())

        chooser.destroy()

    def _open_cb(self, button):
        chooser = FileChooserDialog(title=None,
                                    parent=self._embed.get_toplevel(),
                                    action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                    buttons=(gtk.STOCK_CANCEL,
                                             gtk.RESPONSE_CANCEL,
                                             gtk.STOCK_OPEN,
                                             gtk.RESPONSE_OK))
        chooser.set_default_response(gtk.RESPONSE_OK)
        chooser.set_current_folder(os.path.expanduser('~'))

        file_filter = gtk.FileFilter()
        file_filter.set_name(_("All supported formats"))
        file_filter.add_mime_type("text/html")
        file_filter.add_mime_type("application/xhtml+xml")
        file_filter.add_mime_type("text/xml")
        file_filter.add_mime_type("image/png")
        file_filter.add_mime_type("image/jpeg")
        file_filter.add_mime_type("image/gif")
        chooser.add_filter(file_filter)

        file_filter = gtk.FileFilter()
        file_filter.set_name(_("Web pages"))
        file_filter.add_mime_type("text/html")
        file_filter.add_mime_type("application/xhtml+xml")
        file_filter.add_mime_type("text/xml")
        chooser.add_filter(file_filter)

        file_filter = gtk.FileFilter()
        file_filter.set_name(_("Images"))
        file_filter.add_mime_type("image/png")
        file_filter.add_mime_type("image/jpeg")
        file_filter.add_mime_type("image/gif")
        chooser.add_filter(file_filter)

        file_filter = gtk.FileFilter()
        file_filter.set_name(_("All files"))
        file_filter.add_pattern("*")
        chooser.add_filter(file_filter)

        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            self._embed.load_url(chooser.get_filename())
            self._embed.grab_focus()
            logging.debug('Opened %s.' % chooser.get_filename())

        chooser.destroy()
