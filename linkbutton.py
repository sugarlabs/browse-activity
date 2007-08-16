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

from sugar.graphics.palette import Palette, WidgetInvoker
from sugar.graphics import style

class LinkButton(gtk.RadioToolButton):
    def __init__(self, buffer, pos, group=None):
        gtk.RadioToolButton.__init__(self, group=group)
        self._palette = None
        self.set_image(buffer)
        self.pos = pos
        
    def set_image(self, buffer):
        img = gtk.Image()                    
        loader = gtk.gdk.PixbufLoader()
        loader.write(buffer)
        loader.close()
        pixbuf = loader.get_pixbuf()
        del loader            

        img.set_from_pixbuf(pixbuf)
        self.set_icon_widget(img)
        img.show()

    def get_palette(self):
        return self._palette
    
    def set_palette(self, palette):
        self._palette = palette
        self._palette.props.invoker = WidgetInvoker(self.child)

    def set_tooltip(self, text):
        self._palette = Palette(text)
        self._palette.props.invoker = WidgetInvoker(self.child)
    
    palette = property(get_palette, set_palette)
