# Copyright (C) 2016 Utkarsh Tiwari <iamutkarshtiwari@gmail.com>
# Copyright (C) 2016 Sam Parkinson <sam@sam.today>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''
The progress toolbutton is a :class:`sugar3.graphics.progressicon.ProgressIcon`
that fits into a toolbar.  It is a great way to convey progress of an
ongoing background operation, especially if you want to have a palette with
more detailed information.

Using the progress toolbutton is just like using a regular toolbutton; you
set the icon name and add it to the toolbar.  You can then use the `update`
function as the operation progresses to change the fill percentage.

Example::

    self._download_icon = ProgressToolButton(icon_name='emblem-downloads')
    self._download_icon.props.tooltip = _('No Download Running')
    toolbar.insert(self._download_icon, -1)
    self._download_icon.show()

    def __download_progress_cb(self, progress):
        self._download_icon.props.tooltip = _('Downloading')
        self._download_icon.update(progress)
'''

from gi.repository import Gtk
from gi.repository import GObject

from sugar3.graphics import style
from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics.progressicon import ProgressIcon
from sugar3.graphics.xocolor import XoColor


class ProgressToolButton(ToolButton):
    '''
    This button is just like a normal tool button, except that the
    icon can dynamically fill based on a progress number.
    '''

    __gtype_name__ = 'SugarProgressToolButton'

    def __init__(self, **kwargs):
        self._xo_color = XoColor('insensitive')
        self._icon_name = None
        self._direction = 'vertical'
        self._progress = 0.0

        ToolButton.__init__(self, **kwargs)
        # GObject should do this, but something down the ToolButton chain of
        # parents is not passing the kwargs to GObject
        if 'xo_color' in kwargs:
            self.props.xo_color = kwargs['xo_color']
        if 'icon_name' in kwargs:
            self.props.icon_name = kwargs['icon_name']
        if 'direction' in kwargs:
            self.props.direction = kwargs['direction']
        self._updated()

    @GObject.property
    def xo_color(self):
        '''
        This property defines the stroke and fill of the icon, and is
        the type :class:`sugar3.graphics.xocolor.XoColor`
        '''
        return self._xo_color

    @xo_color.setter
    def xo_color(self, new):
        self._xo_color = new
        self._updated()

    @GObject.property
    def icon_name(self):
        '''
        Icon name (same as with a :class:`sugar3.graphics.icon.Icon`), as the
        type :class:`str`
        '''
        return self._icon_name

    @icon_name.setter
    def icon_name(self, new):
        self._icon_name = new
        self._updated()

    @GObject.property
    def direction(self):
        '''
        Direction for the icon to fill as it progresses, filling either,
        * :class:`Gtk.Orientation.VERTICAL` - bottom to top
        * :class:`Gtk.Orientation.HORIZONTAL` - user's text direction
        '''
        return Gtk.Orientation.VERTICAL if self._direction == 'vertical' \
               else Gtk.Orientation.HORIONTAL

    @direction.setter
    def direction(self, new):
        self._direction = 'vertical' if new == Gtk.Orientation.VETICAL \
                          else Gtk.Orientation.HORIZONTAL
        self._updated()

    def _updated(self):
        self._icon = ProgressIcon(
            self._icon_name,
            style.STANDARD_ICON_SIZE,
            self._xo_color.get_stroke_color(),
            self._xo_color.get_fill_color(),
            self._direction)
        self._icon.update(self._progress)
        self.set_icon_widget(self._icon)
        self._icon.show()

    def update(self, progress):
        '''
        Redraw the icon with a different percentage filled in

        Args:
            progress (float): a value from 0.0 to 1.0, where 1.0 fully
                fills the icon and 0.0 results in only the stroke being
                visible
        '''
        self._progress = progress
        self._icon.update(progress)
        self.queue_draw()
