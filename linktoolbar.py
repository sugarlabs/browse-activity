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

import logging

import gobject
import gtk

from gettext import gettext as _

from linkbutton import LinkButton
from sugar.graphics.palette import Palette

_logger = logging.getLogger('linktoolbar')

class LinkToolbar(gtk.Toolbar):
    __gtype_name__ = 'LinkToolbar'
    
    __gsignals__ = {
        'link-selected': (gobject.SIGNAL_RUN_FIRST,
                           gobject.TYPE_NONE,
                           ([str])),
        'link-rm': (gobject.SIGNAL_RUN_FIRST,
                           gobject.TYPE_NONE,
                           ([int]))
    }

    def __init__(self):
        gtk.Toolbar.__init__(self)       
        self.isvisible = False
        
    def _add_link(self, url, buffer, color, title, owner, pos):

        if self.get_children():
            group = self.get_children()[0]
        else:
            group = None

        info = title +'\n' + owner     
        palette = Palette(info)
        
        link = LinkButton(buffer, color, pos, group)        
        link.set_palette(palette)    
        link.connect('clicked', self._link_clicked_cb, url)
        self.insert(link, 0)
        link.show()
        
        menu_item = gtk.MenuItem(_('Remove'))
        menu_item.connect('activate', self._link_rm_palette_cb, link)
        palette.menu.append(menu_item)
        menu_item.show()
        
        if len(self.get_children()) > 0:
            self.isvisible = True
            self.show()
    
    def _link_clicked_cb(self, link, url):
        if link.get_active():
            _logger.debug('link clicked=%s' %url)
            self.emit('link-selected', url)
            
    def _rm_link(self):
        childs = self.get_children()
        for child in childs:
            if child.get_active():
                index = child.pos
                self.remove(child)
                if len(self.get_children()) is 0:
                    self.isvisible = False
                    self.hide()                    
                return index
    
    def _link_rm_palette_cb(self, widget, link):
        self.emit('link-rm', link.pos)
        self.remove(link)
        if len(self.get_children()) is 0:
            self.hide()
            
