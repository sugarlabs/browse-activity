# Copyright (C) 2007, One Laptop Per Child
# Copyright (C) 2009, Tomeu Vizoso, Lucian Branescu
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
import dbus
import cairo
import StringIO
import tempfile

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GObject

from sugar3.datastore import datastore
from sugar3 import profile
from sugar3 import mime
from sugar3.graphics.alert import Alert, TimeoutAlert
from sugar3.graphics.icon import Icon
from sugar3.activity import activity

try:
    from sugar3.activity.activity import launch_bundle, get_bundle
    _HAS_BUNDLE_LAUNCHER = True
except ImportError:
    _HAS_BUNDLE_LAUNCHER = False


DS_DBUS_SERVICE = 'org.laptop.sugar.DataStore'
DS_DBUS_INTERFACE = 'org.laptop.sugar.DataStore'
DS_DBUS_PATH = '/org/laptop/sugar/DataStore'

_active_downloads = []
_dest_to_window = {}

PROGRESS_TIMEOUT = 3000
SPACE_THRESHOLD = 52428800  # 50 Mb


def format_float(f):
    return "%0.2f" % f


def can_quit():
    return len(_active_downloads) == 0


def num_downloads():
    return len(_active_downloads)


def remove_all_downloads():
    for download in _active_downloads:
        download.cancel()
        if download.dl_jobject is not None:
            datastore.delete(download.dl_jobject.object_id)
        download.cleanup()

def overall_downloads_progress():
    '''
    Returns the average progress of "all" the concurrent
    downloads running in background
    '''
    if len(_active_downloads) != 0:
        total_progress = 0.0
        for download in _active_downloads:
            total_progress += (download._progress / 100.0)
        return (total_progress / num_downloads())
    else:
        return 0.0


class Download(object):

    def __init__(self, webkit_download, activity):
        self._download = webkit_download
        self._activity = activity

        self._source = self._download.get_request().get_uri()
        logging.debug('START Download %s', self._source)

        self.datastore_deleted_handler = None

        self.dl_jobject = None
        self._object_id = None
        self._stop_alert = None

        self._dest_path = ''
        self._progress = 0
        self._last_update_progress = 0
        self._progress_sid = None

        self.temp_path = os.path.join(
            self._activity.get_activity_root(), 'instance')
        if not os.path.exists(self.temp_path):
            os.makedirs(self.temp_path)

        self._download.connect('failed', self.__download_failed_cb)
        self._download.connect('finished', self.__download_finished_cb)
        self._download.connect('received-data',
                               self.__download_received_data_cb)

        # Notify response is called before decide destination
        self._download.connect('notify::response', self.__notify_response_cb)
        self._download.connect('decide-destination',
                               self.__decide_destination_cb)
        self._download.connect('created-destination',
                               self.__created_destination_cb)

    def __notify_response_cb(self, download, pspec):
        logging.debug('__notify_response_cb')
        response = download.get_response()

        # Check free space and cancel the download if there is not enough.
        total_size = response.get_content_length()
        logging.debug('Total size of the file: %s', total_size)
        enough_space = self.enough_space(
            total_size, path=self.temp_path)
        if not enough_space:
            logging.debug('Download canceled because of Disk Space')
            self.cancel()

            self._canceled_alert = Alert()
            self._canceled_alert.props.title = _('Not enough space '
                                                 'to download')

            total_size_mb = total_size / 1024.0 ** 2
            free_space_mb = (self._free_available_space(
                path=self.temp_path) - SPACE_THRESHOLD) \
                / 1024.0 ** 2
            filename = response.get_suggested_filename()
            self._canceled_alert.props.msg = \
                _('Download "%{filename}" requires %{total_size_in_mb}'
                  ' MB of free space, only %{free_space_in_mb} MB'
                  ' is available' %
                  {'filename': filename,
                   'total_size_in_mb': format_float(total_size_mb),
                   'free_space_in_mb': format_float(free_space_mb)})
            ok_icon = Icon(icon_name='dialog-ok')
            self._canceled_alert.add_button(Gtk.ResponseType.OK,
                                            _('Ok'), ok_icon)
            ok_icon.show()
            self._canceled_alert.connect('response',
                                         self.__stop_response_cb)
            self._activity.add_alert(self._canceled_alert)

    def __decide_destination_cb(self, download, suggested_filename):
        logging.debug('__decide_desintation_cb suggests %s',
                      suggested_filename)
        alert = TimeoutAlert(9)
        alert.props.title = _('Download started')
        alert.props.msg = suggested_filename
        self._activity.add_alert(alert)
        alert.connect('response', self.__start_response_cb)
        alert.show()

        self._suggested_filename = suggested_filename
        # figure out download URI
        self._dest_path = tempfile.mktemp(
            dir=self.temp_path, suffix=suggested_filename,
            prefix='tmp')
        logging.debug('Download destination path: %s' % self._dest_path)
        self._download.set_destination('file://' + self._dest_path)
        logging.error(self._download.get_destination)
        return True

    def __created_destination_cb(self, download, dest):
        logging.debug('__created_destination_cb at %s', dest)
        self._create_journal_object()
        self._object_id = self.dl_jobject.object_id

    def _update_progress(self):
        if self._progress > self._last_update_progress:
            self._last_update_progress = self._progress
            self.dl_jobject.metadata['progress'] = str(self._progress)
            datastore.write(self.dl_jobject)

        self._progress_sid = None
        return False

    def __download_received_data_cb(self, download, data_size):
        self._progress = int(self._download.get_estimated_progress() * 100)

        if self._progress_sid is None:
            self._progress_sid = GObject.timeout_add(
                PROGRESS_TIMEOUT, self._update_progress)

    def __download_finished_cb(self, download):
        logging.error('__download_finished_cb')

        if self._progress_sid is not None:
            GObject.source_remove(self._progress_sid)

        self.dl_jobject.metadata['title'] = self._suggested_filename
        self.dl_jobject.metadata['description'] = _('From: %s') \
            % self._source
        self.dl_jobject.metadata['progress'] = '100'
        self.dl_jobject.file_path = self._dest_path

        mime_type = download.get_response().get_mime_type()
        self.dl_jobject.metadata['mime_type'] = mime_type

        if mime_type in ('image/bmp', 'image/gif', 'image/jpeg',
                         'image/png', 'image/tiff'):
            preview = self._get_preview()
            if preview is not None:
                self.dl_jobject.metadata['preview'] = \
                    dbus.ByteArray(preview)

        datastore.write(self.dl_jobject,
                        transfer_ownership=True,
                        reply_handler=self.__internal_save_cb,
                        error_handler=self.__internal_error_cb,
                        timeout=360)

        # update the alert
        self._stop_alert = Alert()
        self._stop_alert.props.title = _('Download completed')
        self._stop_alert.props.msg = self._suggested_filename
        open_icon = Icon(icon_name='zoom-activity')
        self._stop_alert.add_button(Gtk.ResponseType.APPLY,
                                    _('Show in Journal'), open_icon)
        open_icon.show()
        ok_icon = Icon(icon_name='dialog-ok')
        self._stop_alert.add_button(Gtk.ResponseType.OK, _('Ok'), ok_icon)
        ok_icon.show()
        self._activity.add_alert(self._stop_alert)
        self._stop_alert.connect('response', self.__stop_response_cb)
        self._stop_alert.show()

    def __download_failed_cb(self, download, error):
        logging.error('Error downloading URI due to %s'
                      % error)
        self.cleanup()

    def __internal_save_cb(self):
        logging.debug('Object saved succesfully to the datastore.')
        self.cleanup()

    def __internal_error_cb(self, err):
        logging.debug('Error saving activity object to datastore: %s' % err)
        self.cleanup()

    def __start_response_cb(self, alert, response_id):
        if response_id is Gtk.ResponseType.CANCEL:
            logging.debug('Download Canceled')
            self.cancel()
            try:
                datastore.delete(self._object_id)
            except Exception, e:
                logging.warning('Object has been deleted already %s' % e)

            self.cleanup()
            if self._stop_alert is not None:
                self._activity.remove_alert(self._stop_alert)

        self._activity.remove_alert(alert)

    def __stop_response_cb(self, alert, response_id):
        if response_id == Gtk.ResponseType.APPLY:
            logging.debug('Start application with downloaded object')
            launch_bundle(object_id=self._object_id)
        if response_id == Gtk.ResponseType.ACCEPT:
            activity.show_object_in_journal(self._object_id)
        self._activity.remove_alert(alert)

    def cleanup(self):
        global _active_downloads
        if self in _active_downloads:
            _active_downloads.remove(self)

        if self.datastore_deleted_handler is not None:
            self.datastore_deleted_handler.remove()
            self.datastore_deleted_handler = None

        if os.path.isfile(self._dest_path):
            os.remove(self._dest_path)

        if self.dl_jobject is not None:
            self.dl_jobject.destroy()
            self.dl_jobject = None

    def cancel(self):
        self._download.cancel()

    def enough_space(self, size, path='/'):
        """Check if there is enough (size) free space on path

        size -- free space requested in Bytes

        path -- device where the check will be done. For example: '/tmp'

        This method is useful to check the free space, for example,
        before starting a download from internet, creating a big map
        in some game or whatever action that needs some space in the
        Hard Disk.
        """

        free_space = self._free_available_space(path=path)
        return free_space - size > SPACE_THRESHOLD

    def _free_available_space(self, path='/'):
        """Return available space in Bytes

        This method returns the available free space in the 'path' and
        returns this amount in Bytes.
        """

        s = os.statvfs(path)
        return s.f_bavail * s.f_frsize

    def _create_journal_object(self):
        logging.error('_create_journal_object')
        self.dl_jobject = datastore.create()
        filename = self._download.get_response().get_suggested_filename()
        self.dl_jobject.metadata['title'] = \
            _('Downloading %(filename)s from \n%(source)s.') % \
            {'filename': filename, 'source': self._source}

        self.dl_jobject.metadata['progress'] = '0'
        self.dl_jobject.metadata['keep'] = '0'
        self.dl_jobject.metadata['buddies'] = ''
        self.dl_jobject.metadata['preview'] = ''
        self.dl_jobject.metadata['icon-color'] = \
            profile.get_color().to_string()
        self.dl_jobject.metadata['mime_type'] = ''
        self.dl_jobject.file_path = self._dest_path
        datastore.write(self.dl_jobject)

        bus = dbus.SessionBus()
        obj = bus.get_object(DS_DBUS_SERVICE, DS_DBUS_PATH)
        datastore_dbus = dbus.Interface(obj, DS_DBUS_INTERFACE)
        self.datastore_deleted_handler = datastore_dbus.connect_to_signal(
            'Deleted', self.__datastore_deleted_cb,
            arg0=self.dl_jobject.object_id)

    def _get_preview(self):
        # This code borrows from sugar3.activity.Activity.get_preview
        # to make the preview with cairo, and also uses GdkPixbuf to
        # load any GdkPixbuf supported format.
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(self._dest_path)
        image_width = pixbuf.get_width()
        image_height = pixbuf.get_height()

        preview_width, preview_height = activity.PREVIEW_SIZE
        preview_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                             preview_width, preview_height)
        cr = cairo.Context(preview_surface)

        scale_w = preview_width * 1.0 / image_width
        scale_h = preview_height * 1.0 / image_height
        scale = min(scale_w, scale_h)

        translate_x = int((preview_width - (image_width * scale)) / 2)
        translate_y = int((preview_height - (image_height * scale)) / 2)

        cr.translate(translate_x, translate_y)
        cr.scale(scale, scale)

        cr.set_source_rgba(1, 1, 1, 0)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.paint()
        Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
        cr.paint()

        preview_str = StringIO.StringIO()
        preview_surface.write_to_png(preview_str)
        return preview_str.getvalue()

    def __datastore_deleted_cb(self, uid):
        logging.debug('Downloaded entry has been deleted'
                      ' from the datastore: %r', uid)
        global _active_downloads
        if self in _active_downloads:
            self.cancel()
            self.cleanup()


_ignore_pdf_uris = []
_started_callbacks = []


def ignore_pdf(uri):
    _ignore_pdf_uris.append(uri)


def connect_donwload_started(callback):
    _started_callbacks.append(callback)


def add_download(webkit_download, activity):
    uri = webkit_download.get_request().get_uri()
    if uri in _ignore_pdf_uris:
        # The pdf viewer will handle this download`
        _ignore_pdf_uris.remove(uri)
        return

    download = Download(webkit_download, activity)
    _active_downloads.append(download)

    for cb in _started_callbacks:
        cb()
