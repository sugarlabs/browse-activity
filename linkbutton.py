# Copyright (C) 2007, One Laptop Per Child
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Rsvg

import os
import StringIO
import cairo
from gettext import gettext as _
import re

from sugar3.graphics.palettemenu import PaletteMenuItemSeparator
from sugar3.graphics.palettemenu import PaletteMenuItem
from sugar3.graphics.palettemenu import PaletteMenuBox
from sugar3.graphics.palette import Palette
from sugar3.graphics.tray import TrayButton
from sugar3.graphics import style


class LinkButton(TrayButton, GObject.GObject):
    __gtype_name__ = 'LinkButton'
    __gsignals__ = {
        'remove_link': (GObject.SignalFlags.RUN_FIRST,
                        None, ([str])),
        }
    notes_changed_signal = GObject.Signal(
        'notes-changed', arg_types=[str, str])

    def __init__(self, buf, color, title, owner, hash, notes=None):
        TrayButton.__init__(self)

        # Color read from the Journal may be Unicode, but Rsvg needs
        # it as single byte string:
        if isinstance(color, unicode):
            color = str(color)
        self.set_image(buf, color.split(',')[1], color.split(',')[0])

        self.hash = hash
        self.notes = notes
        info = title + '\n' + owner
        self.setup_rollover_options(info)

    def set_image(self, buf, fill='#0000ff', stroke='#4d4c4f'):
        img = Gtk.Image()
        str_buf = StringIO.StringIO(buf)
        thumb_surface = cairo.ImageSurface.create_from_png(str_buf)

        xo_buddy = os.path.join(os.path.dirname(__file__), "icons/link.svg")

        bg_surface = self._read_link_background(xo_buddy, fill, stroke)

        cairo_context = cairo.Context(bg_surface)
        dest_x = style.zoom(10)
        dest_y = style.zoom(20)
        cairo_context.set_source_surface(thumb_surface, dest_x, dest_y)
        thumb_width, thumb_height = style.zoom(100), style.zoom(80)
        cairo_context.rectangle(dest_x, dest_y, thumb_width, thumb_height)
        cairo_context.fill()

        bg_width, bg_height = style.zoom(120), style.zoom(110)
        pixbuf_bg = Gdk.pixbuf_get_from_surface(bg_surface, 0, 0,
                                                bg_width, bg_height)
        img.set_from_pixbuf(pixbuf_bg)
        self.set_icon_widget(img)
        img.show()

    def _read_link_background(self, filename, fill_color, stroke_color):
        icon_file = open(filename, 'r')
        data = icon_file.read()
        icon_file.close()

        if fill_color:
            entity = '<!ENTITY fill_color "%s">' % fill_color
            data = re.sub('<!ENTITY fill_color .*>', entity, data)

        if stroke_color:
            entity = '<!ENTITY stroke_color "%s">' % stroke_color
            data = re.sub('<!ENTITY stroke_color .*>', entity, data)

        link_width, link_height = style.zoom(120), style.zoom(110)
        link_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                          link_width, link_height)
        link_context = cairo.Context(link_surface)
        link_scale_w = link_width * 1.0 / 120
        link_scale_h = link_height * 1.0 / 110
        link_context.scale(link_scale_w, link_scale_h)
        handler = Rsvg.Handle.new_from_data(data)
        handler.render_cairo(link_context)
        return link_surface

    def setup_rollover_options(self, info):
        palette = Palette(info, text_maxlen=50)
        self.set_palette(palette)

        box = PaletteMenuBox()
        palette.set_content(box)
        box.show()

        menu_item = PaletteMenuItem(_('Remove'), 'list-remove')
        menu_item.connect('activate', self.item_remove_cb)
        box.append_item(menu_item)
        menu_item.show()

        separator = PaletteMenuItemSeparator()
        box.append_item(separator)
        separator.show()

        textview = Gtk.TextView()
        textview.props.height_request = style.GRID_CELL_SIZE * 2
        textview.props.width_request = style.GRID_CELL_SIZE * 3
        textview.props.hexpand = True
        textview.props.vexpand = True
        box.append_item(textview)
        textview.show()

        buffer = textview.get_buffer()
        if self.notes is None:
            buffer.set_text(_('Take notes on this page'))
        else:
            buffer.set_text(self.notes)
        buffer.connect('changed', self.__buffer_changed_cb)

    def item_remove_cb(self, widget):
        self.emit('remove_link', self.hash)

    def __buffer_changed_cb(self, buffer):
        start, end = buffer.get_bounds()
        self.notes = buffer.get_text(start, end, False)
        self.notes_changed_signal.emit(self.hash, self.notes)
