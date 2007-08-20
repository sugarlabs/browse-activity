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

import rsvg
import re

from sugar.graphics.palette import Palette, WidgetInvoker
from sugar.graphics import style


class LinkButton(gtk.RadioToolButton):
    def __init__(self, buffer, color, pos, group=None):
        gtk.RadioToolButton.__init__(self, group=group)
        self._palette = None        
        self.set_image(buffer, color.split(',')[1], color.split(',')[0])
        self.pos = pos
        
    def set_image(self, buffer, fill='#0000ff', stroke='#4d4c4f'):
        img = gtk.Image()                    
        loader = gtk.gdk.PixbufLoader()
        loader.write(buffer)
        loader.close()
        pixbuf = loader.get_pixbuf()
        del loader            

        xo_buddy = os.path.join(os.path.dirname(__file__), "icons/buddy-link.svg")
        pixbuf_xo = self._read_xo_icon(xo_buddy, fill, stroke)

        width  = pixbuf_xo.get_width()
        height = pixbuf_xo.get_height()

        dest_x = style.zoom(105) 
        dest_y = style.zoom(65) 
        w = width*0.7
        h = height*0.7 
        scale_x = 0.7
        scale_y = 0.7
        
        pixbuf_xo.composite(pixbuf, dest_x, dest_y, w, h, dest_x, dest_y, scale_x, scale_y, gtk.gdk.INTERP_BILINEAR, 255)

        img.set_from_pixbuf(pixbuf)
        self.set_icon_widget(img)
        img.show()

    def _read_xo_icon(self, filename, fill_color, stroke_color):
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

    def get_palette(self):
        return self._palette
    
    def set_palette(self, palette):
        self._palette = palette
        self._palette.props.invoker = WidgetInvoker(self.child)

    def set_tooltip(self, text):
        self._palette = Palette(text)
        self._palette.props.invoker = WidgetInvoker(self.child)
    
    palette = property(get_palette, set_palette)
