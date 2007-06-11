import logging

import xpcom
from xpcom import components
from xpcom.components import interfaces
from xpcom.server.factory import Factory

class PromptService:
    _com_interfaces_ = interfaces.nsIPromptService

    cid = '{836a90cb-6304-44f0-97df-c29913b908b7}'
    description = 'Sugar Prompt Service'

    def __init__(self):
        pass
    
    def alert(self, parent, dialogTitle, text):
        logging.debug('nsIPromptService.alert()')
    
    def alertCheck(self, parent, dialogTitle, text, checkMsg, checkState):
        logging.debug('nsIPromptService.alertCheck()')
    
    def confirm(self, parent, dialogTitle, text):
        logging.debug('nsIPromptService.confirm()')
    
    def confirmCheck(self, parent, dialogTitle, text, checkMsg, checkState):
        logging.debug('nsIPromptService.confirmCheck()')
    
    def confirmEx(self, parent, dialogTitle, text, buttonFlags, button0Title,
            button1Title, button2Title, checkMsg, checkState):
        logging.debug('nsIPromptService.confirmEx()')
    
    def prompt(self, parent, dialogTitle, text, value, checkMsg, checkState):
        logging.debug('nsIPromptService.prompt()')
    
    def promptPassword(self, parent, dialogTitle, text, password, checkMsg,
            checkState):
        logging.debug('nsIPromptService.promptPassword()')
    
    def promptUsernameAndPassword(self, parent, dialogTitle, text, username,
            password, checkMsg, checkState):
        logging.debug('nsIPromptService.promptUsernameAndPassword()')
    
    def select(self, parent, dialogTitle, text, count, selectList, outSelection):
        logging.debug('nsIPromptService.select()')


components.registrar.registerFactory(PromptService.cid,
                                     PromptService.description,
                                     '@mozilla.org/embedcomp/prompt-service;1',
                                     Factory(PromptService))

