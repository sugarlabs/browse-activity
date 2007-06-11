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

components.registrar.registerFactory(SecurityDialogs.cid,
                                     SecurityDialogs.description,
                                     '@mozilla.org/nsBadCertListener;1',
                                     Factory(SecurityDialogs))

