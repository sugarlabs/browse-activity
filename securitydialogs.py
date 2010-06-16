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

import logging

import xpcom
from xpcom import components
from xpcom.components import interfaces
from xpcom.server.factory import Factory


class SecurityDialogs:
    _com_interfaces_ = interfaces.nsIBadCertListener

    cid = '{267d2fc2-1810-11dc-8314-0800200c9a66}'
    description = 'Sugar Security Dialogs'

    def __init__(self):
        pass

    def confirmCertExpired(socketInfo, cert):
        logging.debug('UNIMPLEMENTED: SecurityDialogs.confirmCertExpired()')
        return interfaces.nsIBadCertListener.ADD_TRUSTED_FOR_SESSION, True

    def confirmMismatchDomain(socketInfo, targetURL, cert):
        logging.debug('UNIMPLEMENTED: SecurityDialogs.confirmMismatchDomain()')
        return interfaces.nsIBadCertListener.ADD_TRUSTED_FOR_SESSION, True

    def confirmUnknownIssuer(socketInfo, cert, certAddType):
        logging.debug('UNIMPLEMENTED: SecurityDialogs.confirmUnknownIssuer()')
        return interfaces.nsIBadCertListener.ADD_TRUSTED_FOR_SESSION, True

    def notifyCrlNextupdate(socketInfo, targetURL, cert):
        logging.debug('UNIMPLEMENTED: SecurityDialogs.notifyCrlNextupdate()')

"""
components.registrar.registerFactory(SecurityDialogs.cid,
                                     SecurityDialogs.description,
                                     '@mozilla.org/nsBadCertListener;1',
                                     Factory(SecurityDialogs))
"""
