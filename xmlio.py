#
#    Copyright (C) 2006, 2007, One Laptop Per Child
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import libxml2
import os
import logging
import base64


_logger = logging.getLogger('xmlio')


class Xmlio(object):
    ''' The xmlio of the activity. Contains methods to read and write
    the configuration for a browser session to and from xml. 
    '''
    
    def __init__(self, dtdpath, linkbar):        
        self.linkbar = linkbar        
        self.data = {}
        self.dtdpath = dtdpath
        self.data['name'] = 'first'
        self.session_data = ''
        
        try:
            self.dtd = libxml2.parseDTD(None, os.path.join(self.dtdpath, 'browser.dtd'))
        except libxml2.parserError, e:
            _logger.error('Init: no browser.dtd found ' +str(e))
            self.dtd = None
        self.ctxt = libxml2.newValidCtxt()               

    def read(self, filepath):
        ''' reads the configuration from an xml file '''
        
        try:
            doc = libxml2.parseFile(filepath)
            if doc.validateDtd(self.ctxt, self.dtd):
        
                # get the requested nodes
                xpa = doc.xpathNewContext()
                res = xpa.xpathEval("//*")

                # write their content to the data structure
                for elem in res:
                    attributes = elem.get_properties()
                    thumb = ''
                    link_name = ''
                    id = None
                    if( elem.name == 'link' ):
                        for attribute in attributes:
                            if(attribute.name == 'id'):
                                id = int(attribute.content)
                            elif(attribute.name == 'name'):
                                link_name = attribute.content
                            elif(attribute.name == 'thumb'):
                                thumb = attribute.content                                
                        self.linkbar._add_link(link_name, base64.b64decode(thumb), id)
                
                    elif( elem.name == 'session' ):
                        for attribute in attributes:
                            if(attribute.name == 'data'):                            
                                self.session_data = attribute.content
                        
                    elif( elem.name == 'browser' ):
                        for attribute in attributes:
                            if(attribute.name == 'name'):                            
                                self.data['name'] = attribute.content
                                
                xpa.xpathFreeContext()
            else:
                _logger.error('Read: Error in validation of the file')
                doc.freeDoc()
                return 1
            doc.freeDoc()
            return 0
        except libxml2.parserError, e:
            _logger.error('Read: Error parsing file ' +str(e))
            return 2
        
                
    def write(self, filepath):
        ''' writes the configuration to an xml file '''
        doc = libxml2.newDoc("1.0")
        root = doc.newChild(None, "browser", None)
        
        if(self.data.get('name', None) != None):                            
            root.setProp("name", self.data['name'])
        else:
            _logger.error('Write: No name is specified. Can not write session.')
            return 1

        elem = root.newChild(None, "session", None)
        elem.setProp("data", self.session_data)

        for child in self.linkbar.get_children():
            elem = root.newChild(None, "link", None)
            elem.setProp("id", str(self.linkbar.get_item_index(child)))
            elem.setProp("name", child.link_name)
            elem.setProp("thumb", base64.b64encode(child.buf))

                        
        if doc.validateDtd(self.ctxt, self.dtd):
            doc.saveFormatFile(filepath, 1)
        else:
            _logger.error('Write: Error in validation of the file')
            doc.freeDoc()
            return 2
        doc.freeDoc()
        return 0
        

    
