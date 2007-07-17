# Copyright (C) 2007, One Laptop Per Child
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
import tempfile

from xpcom.nsError import *
from xpcom import ServerException
from xpcom import components
from xpcom.components import interfaces

from documentnode import DocumentNode

class UriListDataProvider:
    _com_interfaces_ = interfaces.nsIFlavorDataProvider
    
    def __init__(self, doc_node):
        self._doc_node = doc_node
        self._file_path = None

    def __del__(self):
        if self._file_path:
            os.remove(self._file_path)

    def getFlavorData(self, transferable, flavor):
        if flavor != 'text/uri-list':
            raise COMException(NS_ERROR_NOT_IMPLEMENTED)

        mime_type = self._doc_node.get_image_mime_type()
        image_name = self._doc_node.get_image_name()
        image_name, file_ext = os.path.splitext(image_name)
        
        if file_ext:
            file_ext = file_ext[1:]

        cls = components.classes['@mozilla.org/mime;1']
        mime_service = cls.getService(interfaces.nsIMIMEService)
        file_ext = mime_service.getPrimaryExtension(mime_type, file_ext)
            
        f, self._file_path = tempfile.mkstemp(image_name + '.' + file_ext)
        del f

        self._doc_node.save_image(self._file_path)

        cls = components.classes['@mozilla.org/supports-string;1']        
        string_supports = cls.createInstance(interfaces.nsISupportsString)
        string_supports.data = 'file://' + self._file_path

        return string_supports, 32

class DragDropHooks:
    _com_interfaces_ = interfaces.nsIClipboardDragDropHooks
    
    def __init__(self, browser):
        self._browser = browser
    
    def allowDrop(self, event, session):
        raise ServerException(NS_ERROR_NOT_IMPLEMENTED)

    def allowStartDrag(self, event):
        raise ServerException(NS_ERROR_NOT_IMPLEMENTED)

    def onPasteOrDrop(self, event, trans):
        return False

    def onCopyOrDrag(self, event, trans):
        if not event:
            logging.warning('DragDropHooks.onCopyOrDrag: no event received.')
            return True

        mouse_event = event.queryInterface(interfaces.nsIDOMMouseEvent)
        event_target = mouse_event.target
        target_node = event_target.queryInterface(interfaces.nsIDOMNode)
        document_node = DocumentNode(target_node, self._browser.web_navigation)

        if document_node.is_image():
            # Take out this flavors as they confuse the receivers:
            trans.removeDataFlavor('text/x-moz-url')
            trans.removeDataFlavor('text/html')
            trans.removeDataFlavor('text/unicode')

            data_provider = UriListDataProvider(document_node)
            trans.addDataFlavor('text/uri-list')
            trans.setTransferData('text/uri-list', data_provider, 0)

        return True

