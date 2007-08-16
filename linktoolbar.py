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
                           ([str]))
    }

    def __init__(self):
        gtk.Toolbar.__init__(self)       
        
    def _add_link(self, link_name, buffer, pos):

        if self.get_children():
            group = self.get_children()[0]
        else:
            group = None

        palette = Palette(link_name)
        palette.props.position = Palette.TOP        
        
        link = LinkButton(link_name, buffer, group)        
        link.set_palette(palette)    
        link.connect('clicked', self._link_clicked_cb, link_name)
        self.insert(link, pos)
        link.show()
        
        menu_item = gtk.MenuItem(_('remove'))
        menu_item.connect('activate', self._link_rm_palette_cb, link)
        palette.menu.append(menu_item)
        menu_item.show()

        #link.props.active = True
        
        if len(self.get_children()) > 0:
            self.show()
    
    def _link_clicked_cb(self, link, link_name):
        if link.get_active():
            _logger.debug('link clicked=%s' %link_name)
            self.emit('link-selected', link_name)
            
    def _rm_link(self):
        childs = self.get_children()
        for child in childs:
            if child.get_active():
                link_name = child.link_name
                self.remove(child)
                # self.get_children()[0].props.active = True        
                if len(self.get_children()) is 0:
                    self.hide()
                return link_name   

    def _rm_link_messenger(self, linkname):
        childs = self.get_children()
        for child in childs:
            if child.link_name == linkname:
                self.remove(child)                
                if len(self.get_children()) is 0:
                    self.hide()
                return   
            
    def _link_rm_palette_cb(self, widget, link):
        self.emit('link-rm', link.link_name)
        self.remove(link)
        # self.get_children()[0].props.active = True        
        if len(self.get_children()) is 0:
            self.hide()
            
