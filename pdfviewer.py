# Copyright (C) 2012, One Laptop Per Child
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
import tempfile
import threading
from gettext import gettext as _

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import EvinceDocument
from gi.repository import EvinceView
from gi.repository import WebKit

from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.graphics.toolbutton import ToolButton
from sugar3.datastore import datastore
from sugar3.activity import activity


class EvinceViewer(Gtk.Overlay):
    """PDF viewer with a toolbar overlay for basic navigation and an
    option to save to Journal.

    """
    __gsignals__ = {
        'save-to-journal': (GObject.SignalFlags.RUN_FIRST,
                            None,
                            ([])),
        'open-link': (GObject.SignalFlags.RUN_FIRST,
                      None,
                      ([str])),
   }

    def __init__(self, uri):
        GObject.GObject.__init__(self)

        self._uri = uri

        # Create Evince objects to handle the PDF in the URI:
        EvinceDocument.init()
        self._doc = EvinceDocument.Document.factory_get_document(uri)
        self._view = EvinceView.View()
        self._model = EvinceView.DocumentModel()
        self._model.set_document(self._doc)
        self._view.set_model(self._model)

        self._view.connect('external-link', self.__handle_link_cb)
        self._model.connect('page-changed', self.__page_changed_cb)

        self._back_page_button = None
        self._forward_page_button = None
        self._toolbar_box = self._create_toolbar()
        self._update_nav_buttons()

        self._toolbar_box.set_halign(Gtk.Align.FILL)
        self._toolbar_box.set_valign(Gtk.Align.END)
        self.add_overlay(self._toolbar_box)
        self._toolbar_box.show()

        scrolled_window = Gtk.ScrolledWindow()
        self.add(scrolled_window)
        scrolled_window.show()

        scrolled_window.add(self._view)
        self._view.show()

    def _create_toolbar(self):
        toolbar_box = ToolbarBox()

        zoom_out_button = ToolButton('zoom-out')
        zoom_out_button.set_tooltip(_('Zoom out'))
        zoom_out_button.connect('clicked', self.__zoom_out_cb)
        toolbar_box.toolbar.insert(zoom_out_button, -1)
        zoom_out_button.show()

        zoom_in_button = ToolButton('zoom-in')
        zoom_in_button.set_tooltip(_('Zoom in'))
        zoom_in_button.connect('clicked', self.__zoom_in_cb)
        toolbar_box.toolbar.insert(zoom_in_button, -1)
        zoom_in_button.show()

        separator = Gtk.SeparatorToolItem()
        separator.props.draw = True
        toolbar_box.toolbar.insert(separator, -1)
        separator.show()

        self._back_page_button = ToolButton('go-previous-paired')
        self._back_page_button.set_tooltip(_('Previous page'))
        self._back_page_button.props.sensitive = False
        self._back_page_button.connect('clicked', self.__go_back_page_cb)
        toolbar_box.toolbar.insert(self._back_page_button, -1)
        self._back_page_button.show()

        self._forward_page_button = ToolButton('go-next-paired')
        self._forward_page_button.set_tooltip(_('Next page'))
        self._forward_page_button.props.sensitive = False
        self._forward_page_button.connect('clicked', self.__go_forward_page_cb)
        toolbar_box.toolbar.insert(self._forward_page_button, -1)
        self._forward_page_button.show()

        separator = Gtk.SeparatorToolItem()
        separator.props.draw = True
        toolbar_box.toolbar.insert(separator, -1)
        separator.show()

        self._save_to_journal_button = ToolButton('save-to-journal')
        self._save_to_journal_button.set_tooltip(_('Save PDF to Journal'))
        self._save_to_journal_button.connect('clicked',
                                             self.__save_to_journal_button_cb)
        toolbar_box.toolbar.insert(self._save_to_journal_button, -1)
        self._save_to_journal_button.show()

        return toolbar_box

    def disable_journal_button(self):
        self._save_to_journal_button.props.sensitive = False

    def __handle_link_cb(self, widget, url):
        self.emit('open-link', url.get_uri())

    def __page_changed_cb(self, model, page_from, page_to):
        self._update_nav_buttons()

    def __zoom_out_cb(self, widget):
        self.zoom_out()

    def __zoom_in_cb(self, widget):
        self.zoom_in()

    def __go_back_page_cb(self, widget):
        self._view.previous_page()

    def __go_forward_page_cb(self, widget):
        self._view.next_page()

    def __save_to_journal_button_cb(self, widget):
        self.emit('save-to-journal')
        self._save_to_journal_button.props.sensitive = False

    def _update_nav_buttons(self):
        current_page = self._model.props.page
        self._back_page_button.props.sensitive = current_page > 0
        self._forward_page_button.props.sensitive = \
            current_page < self._doc.get_n_pages() - 1

    def zoom_in(self):
        self._model.props.sizing_mode = EvinceView.SizingMode.FREE
        self._view.zoom_in()

    def zoom_out(self):
        self._model.props.sizing_mode = EvinceView.SizingMode.FREE
        self._view.zoom_out()

    def get_pdf_title(self):
        return self._doc.get_title()


class DummyBrowser(GObject.GObject):
    """Has the same interface as browser.Browser ."""
    __gsignals__ = {
        'new-tab': (GObject.SignalFlags.RUN_FIRST, None, ([str])),
        'tab-close': (GObject.SignalFlags.RUN_FIRST, None, ([object])),
        'selection-changed': (GObject.SignalFlags.RUN_FIRST, None, ([])),
    }

    __gproperties__ = {
        "title": (object, "title", "Title", GObject.PARAM_READWRITE),
        "uri": (object, "uri", "URI", GObject.PARAM_READWRITE),
        "progress": (object, "progress", "Progress", GObject.PARAM_READWRITE),
        "load-status": (object, "load status", "a WebKit LoadStatus",
                        GObject.PARAM_READWRITE),
    }

    def __init__(self, tab):
        GObject.GObject.__init__(self)
        self._tab = tab
        self._title = ""
        self._uri = ""
        self._progress = 0.0
        self._load_status = WebKit.LoadStatus.PROVISIONAL

    def do_get_property(self, prop):
        if prop.name == 'title':
            return self._title
        elif prop.name == 'uri':
            return self._uri
        elif prop.name == 'progress':
            return self._progress
        elif prop.name == 'load-status':
            return self._load_status
        else:
            raise AttributeError, 'Unknown property %s' % prop.name

    def do_set_property(self, prop, value):
        if prop.name == 'title':
            self._title = value
        elif prop.name == 'uri':
            self._uri = value
        elif prop.name == 'progress':
            self._progress = value
        elif prop.name == 'load-status':
            self._load_status = value
        else:
            raise AttributeError, 'Unknown property %s' % prop.name

    def get_title(self):
        return self._title

    def get_uri(self):
        return self._uri

    def get_progress(self):
        return self._progress

    def get_load_status(self):
        return self._load_status

    def emit_new_tab(self, uri):
        self.emit('new-tab', uri)

    def emit_close_tab(self):
        self.emit('tab-close', self._tab)

    def get_history(self):
        return [{'url': self.props.uri, 'title': self.props.title}]

    def can_undo(self):
        return False

    def can_redo(self):
        return False

    def can_go_back(self):
        return False

    def can_go_forward(self):
        return False

    def can_copy_clipboard(self):
        return False

    def can_paste_clipboard(self):
        return False

    def set_history_index(self, index):
        pass

    def get_history_index(self):
        return 0

    def stop_loading(self):
        self._tab.cancel_download()

    def reload(self):
        pass


class PDFTabPage(Gtk.HBox):
    """Shows a basic PDF viewer, download the file first if the PDF is
    in a remote location.

    """
    def __init__(self):
        GObject.GObject.__init__(self)
        self._browser = DummyBrowser(self)
        self._evince_viewer = None
        self._pdf_uri = None
        self._requested_uri = None

    def setup(self, requested_uri, title=None):
        self._requested_uri = requested_uri

        # The title may be given from the Journal:
        if title is not None:
            self._browser.props.title = title
        else:
            self._browser.props.title = os.path.basename(requested_uri)

        self._browser.props.uri = requested_uri
        self._browser.props.load_status = WebKit.LoadStatus.PROVISIONAL

        # show PDF directly if the file is local (from the system tree
        # or from the journal)

        if requested_uri.startswith('file://'):
            self._pdf_uri = requested_uri
            self._show_pdf()

        elif requested_uri.startswith('journal://'):
            self._pdf_uri = self._get_path_from_journal(requested_uri)
            self._show_pdf(from_journal=True)

        # download first if file is remote

        elif requested_uri.startswith('http://'):
            self._download_from_http(requested_uri)

    def _get_browser(self):
        return self._browser

    browser = GObject.property(type=object, getter=_get_browser)

    def _show_pdf(self, from_journal=False):
        self._evince_viewer = EvinceViewer(self._pdf_uri)
        self._evince_viewer.connect('save-to-journal',
                                    self.__save_to_journal_cb)
        self._evince_viewer.connect('open-link',
                                    self.__open_link_cb)

        # disable save to journal if the PDF is already loaded from
        # the journal:
        if from_journal:
            self._evince_viewer.disable_journal_button()

        self._evince_viewer.show()
        self.pack_start(self._evince_viewer, True, True, 0)

        # if the PDF has a title, show it instead of the URI:
        pdf_title = self._evince_viewer.get_pdf_title()
        if pdf_title is not None:
            self._browser.props.title = pdf_title

    def _get_path_from_journal(self, journal_uri):
        """Get the system tree URI of the file for the Journal object."""
        journal_id = self.__journal_id_from_uri(journal_uri)
        jobject = datastore.get(journal_id)
        return 'file://' + jobject.file_path

    def _download_from_http(self, remote_uri):
        """Download the PDF from a remote location to a temporal file."""

        # Figure out download URI
        temp_path = os.path.join(activity.get_activity_root(), 'instance')
        if not os.path.exists(temp_path):
            os.makedirs(temp_path)

        fd, dest_path = tempfile.mkstemp(dir=temp_path)

        self._pdf_uri = 'file://' + dest_path

        network_request = WebKit.NetworkRequest.new(remote_uri)
        self._download = WebKit.Download.new(network_request)
        self._download.set_destination_uri('file://' + dest_path)

        self._download.connect('notify::progress', self.__download_progress_cb)
        self._download.connect('notify::status', self.__download_status_cb)
        self._download.connect('error', self.__download_error_cb)

        self._download.start()

    def __download_progress_cb(self, download, data):
        progress = download.get_progress()
        self._browser.props.progress = progress

    def __download_status_cb(self, download, data):
        status = download.get_status()
        if status == WebKit.DownloadStatus.STARTED:
            self._browser.props.load_status = WebKit.LoadStatus.PROVISIONAL
        elif status == WebKit.DownloadStatus.FINISHED:
            self._browser.props.load_status = WebKit.LoadStatus.FINISHED
            self._show_pdf()
        elif status == WebKit.DownloadStatus.CANCELLED:
            logging.debug('Download PDF canceled')

    def __download_error_cb(self, download, err_code, err_detail, reason):
        logging.debug('Download error! code %s, detail %s: %s' % \
                          (err_code, err_detail, reason))

    def cancel_download(self):
        self._download.cancel()
        self._browser.emit_close_tab()

    def __journal_id_to_uri(self, journal_id):
        """Return an URI for a Journal object ID."""
        return "journal://" + journal_id + ".pdf"

    def __journal_id_from_uri(self, journal_uri):
        """Return a Journal object ID from an URI."""
        return journal_uri[len("journal://"):-len(".pdf")]

    def __save_to_journal_cb(self, widget):
        """Save the PDF in the Journal.

        Put the PDF title as the title, or if the PDF doesn't have
        one, use the filename instead.  Put the requested uri as the
        description.

        """
        jobject = datastore.create()

        jobject.metadata['title'] = self._browser.props.title
        jobject.metadata['description'] = _('From: %s') % self._requested_uri

        jobject.metadata['mime_type'] = "application/pdf"
        jobject.file_path = self._pdf_uri[len("file://"):]
        datastore.write(jobject)

        # display the new URI:
        self._browser.props.uri = self.__journal_id_to_uri(jobject.object_id)

    def __open_link_cb(self, widget, uri):
        """Open the external link of a PDF in a new tab."""
        self._browser.emit_new_tab(uri)
