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

import os.path
import urlparse

from xpcom.nsError import *
from xpcom import COMException
from xpcom import components
from xpcom.components import interfaces

class DocumentNode:
    def __init__(self, DOM_node, web_navigation):
        self._DOM_node = DOM_node
        self._image_element = None
        self._image_name = None
        self._image_mime_type = None
        self._image_properties = None
        self._web_navigation = web_navigation

    def is_image(self):
        if self._image_element:
            return True

        if self._DOM_node.nodeType == interfaces.nsIDOMNode.ELEMENT_NODE:
            element = self._DOM_node.queryInterface(interfaces.nsIDOMHTMLElement)
            if element.localName.lower() == "img":
                self._image_element = element.queryInterface(
                        interfaces.nsIDOMHTMLImageElement)
                return True

        return False

    def _get_image_properties(self):
        if not self.is_image():
            return None

        if not self._image_properties:
            cls = components.classes['@mozilla.org/network/simple-uri;1']
            uri = cls.createInstance(interfaces.nsIURI)
            uri.spec = self._image_element.src
            
            cls = components.classes['@mozilla.org/image/cache;1']
            image_cache = cls.getService(interfaces.imgICache)
            self._image_properties = image_cache.findEntryProperties(uri)

        return self._image_properties

    def get_image_mime_type(self):
        if not self.is_image():
            return None

        if not self._image_mime_type:
            properties = self._get_image_properties()
            self._image_mime_type = properties.get('type',
                        interfaces.nsISupportsCString).data

        return self._image_mime_type

    def get_image_name(self):
        if not self.is_image():
            return None

        if not self._image_name:
            properties = self._get_image_properties()
            if properties.has('content-disposition'):
                content_disposition = properties.get('content-disposition',
                            interfaces.nsISupportsCString).data

                cls = components.classes['@mozilla.org/network/mime-hdrparam;1']
                header_param = cls.getService(interfaces.nsIMIMEHeaderParam)
                self._image_name = header_param.getParameter(content_disposition,
                                'filename', '', True, None)

                if not self._image_name:
                    self._image_name = header_param.getParameter(content_disposition,
                                'name', '', True, None)

        if not self._image_name:
            url = urlparse.urlparse(self._image_element.src)
            path = url[2]
            self._image_name = os.path.split(path)[1]

        return self._image_name

    def save_image(self, file_path):
        """ Based on nsWebBrowserPersist::OnDataAvailable:
        http://lxr.mozilla.org/seamonkey/source/embedding/components/webbrowserpersist/src/nsWebBrowserPersist.cpp
        """
        cls = components.classes['@mozilla.org/network/io-service;1']
        io_service = cls.getService(interfaces.nsIIOService)
        uri = io_service.newURI(self._image_element.src, None, None)

        cls = components.classes['@mozilla.org/file/local;1']
        dest_file = cls.createInstance(interfaces.nsILocalFile)
        dest_file.initWithPath(file_path)

        cls = components.classes['@mozilla.org/network/io-service;1']
        io_service = cls.getService(interfaces.nsIIOService)
        input_channel = io_service.newChannelFromURI(uri)

        session_history = self._web_navigation.sessionHistory
        entry = session_history.getEntryAtIndex(session_history.index, False)
        entry = entry.queryInterface(interfaces.nsISHEntry)
        post_data = entry.postData
        if post_data:
            http_channel = input_channel.queryInterface(interfaces.nsIHttpChannel)
            stream = post_data.queryInterface(interfaces.nsISeekableStream)
            stream.seek(interfaces.nsISeekableStream.NS_SEEK_SET, 0)

            upload_channel = http_channel.queryInterface(interfaces.nsIUploadChannel)
            upload_channel.setUploadStream(post_data, '', -1)

        http_input_stream = input_channel.open()

        cls = components.classes['@mozilla.org/network/file-output-stream;1']
        file_output_stream = cls.createInstance(interfaces.nsIFileOutputStream)
        file_output_stream.init(dest_file, -1, -1, 0)

        # TODO: this is not reliable, sometimes reports 4096
        bytes_to_read = http_input_stream.available()
        while bytes_to_read:
            buf = str(http_input_stream.read(min(8192, bytes_to_read)))
            bytes_read = len(buf)
            print "bytes_read %i" % bytes_read
            bytes_to_write = bytes_read
            while bytes_to_write:
                bytes_written = file_output_stream.write(buf, bytes_read)
                print "bytes_written %i" % bytes_written
                bytes_to_write -= bytes_written

            bytes_to_read -= bytes_read

        http_input_stream.close()
        file_output_stream.close()

