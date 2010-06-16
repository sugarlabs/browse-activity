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

import gtk
import os
import gobject
from gettext import gettext as _
import rsvg
import re
import gc

from sugar.graphics.palette import Palette
from sugar.graphics.tray import TrayButton
from sugar.graphics import style


class LinkButton(TrayButton, gobject.GObject):
    __gtype_name__ = 'LinkButton'
    __gsignals__ = {
        'remove_link': (gobject.SIGNAL_RUN_FIRST,
                        gobject.TYPE_NONE, ([str]))
        }

    def __init__(self, url, buf, color, title, owner, index, hash):
        TrayButton.__init__(self)
        self.set_image(buf, color.split(',')[1], color.split(',')[0])

        self.hash = hash
        info = title +'\n'+ owner
        self.setup_rollover_options(info)

    def set_image(self, buf, fill='#0000ff', stroke='#4d4c4f'):
        img = gtk.Image()
        loader = gtk.gdk.PixbufLoader()
        loader.write(buf)
        loader.close()
        pixbuf = loader.get_pixbuf()
        del loader

        xo_buddy = os.path.join(os.path.dirname(__file__), "icons/link.svg")
        pixbuf_bg = self._read_link_background(xo_buddy, fill, stroke)
        pixbuf_bg = pixbuf_bg.scale_simple(style.zoom(120),
                                           style.zoom(110),
                                           gtk.gdk.INTERP_BILINEAR)
        dest_x = style.zoom(10)
        dest_y = style.zoom(20)
        w = pixbuf.get_width()
        h = pixbuf.get_height()
        scale_x = 1
        scale_y = 1

        pixbuf.composite(pixbuf_bg, dest_x, dest_y, w, h, dest_x, dest_y,
                         scale_x, scale_y, gtk.gdk.INTERP_BILINEAR, 255)
        img.set_from_pixbuf(pixbuf_bg)
        self.set_icon_widget(img)
        img.show()
        del pixbuf
        del pixbuf_bg
        gc.collect()

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

        data_size = len(data)
        return rsvg.Handle(data=data).get_pixbuf()

    def setup_rollover_options(self, info):
        palette = Palette(info, text_maxlen=50)
        self.set_palette(palette)

        menu_item = gtk.MenuItem(_('Remove'))
        menu_item.connect('activate', self.item_remove_cb)
        palette.menu.append(menu_item)
        menu_item.show()

    def item_remove_cb(self, widget):
        self.emit('remove_link', self.hash)
