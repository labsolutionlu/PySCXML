''' 
This file is part of pyscxml.

    pyscxml is free software: you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    pyscxml is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public License
    along with pyscxml.  If not, see <http://www.gnu.org/licenses/>.
'''

from . import logger
from .compiler import Compiler
from .interpreter import Interpreter
from louie import dispatcher

import time
from threading import Thread, RLock


def default_logfunction(label, msg):
    if not label: label = "Log"
    print(("%s: %s" % (label, msg)))


class StateMachine(object):
    '''
    This class provides the entry point for the pyscxml library. 
    '''
    
    def __init__(self, xml, logger=logger, log_function=default_logfunction):
        '''
        @param xml: the scxml document to parse, expressed as a string.
        @param logger_handler: the logger will log to this handler, using 
        the logging.getLogger("pyscxml") logger.
        @param log_function: the function to execute on a <log /> element. 
        signature is f(label, msg), where label is a string and msg a string. 
        '''

        self.is_finished = False
        self._lock = RLock()
        self.interpreter = Interpreter(logger)
        dispatcher.connect(self.on_exit, "signal_exit", self.interpreter)
        self.compiler = Compiler(logger)
        self.compiler.log_function = lambda label, msg: logger.info("Log: %s", msg) 
        #self.send = self.interpreter.send
        #self.In = self.interpreter.In
        self.doc = self.compiler.parseXML(xml, self.interpreter)
        self.doc.datamodel["_x"] = {"self" : self}
        self.datamodel = self.doc.datamodel
        self.name = self.doc.name
    
    def send(self, name, data={}, invokeid = None, toQueue = None):
        with self._lock:
            self.interpreter.send(name, data, invokeid, toQueue)
        
    def In(self, name):
        with self._lock:
            self.interpreter.In(name)
    
    def _start(self, parentQueue=None, invokeid=None):
        with self._lock:
            self.compiler.instantiate_datamodel()
            self.interpreter.interpret(self.doc, parentQueue, invokeid)
            
    def start(self, parentQueue=None, invokeid=None):
        '''Takes the statemachine to its initial state'''
        self._start(parentQueue, invokeid)
        self.interpreter.mainEventLoop()
    
    def start_threaded(self, parentQueue=None, invokeid=None):
        self._start(parentQueue, invokeid)
        t = Thread(target=self.interpreter.mainEventLoop)
        t.start()     
        
    def isFinished(self):
        with self._lock:
            '''Returns True if the statemachine has reached it top-level final state'''
            return self.is_finished
    
    def on_exit(self, sender):
        with self._lock:
            if sender is self.interpreter:
                self.is_finished = True
                dispatcher.send("signal_exit", self)
        

class MultiSession(object):
    
    def __init__(self, default_scxml_doc=None, init_sessions={}):
        '''
        MultiSession is a local runtime for multiple StateMachine sessions. Use 
        this class for supporting the send target="_scxml_sessionid" syntax described
        in the W3C standard. Note that  
        @param default_scxml_doc: an scxml document expressed as a string.
        If one is provided, each call to a sessionid will initialize a new 
        StateMachine instance at that session, running the default document.
        @param init_sessions: the optional keyword arguments run 
        make_session(key, value) on each init_sessions pair, thus initalizing 
        a set of sessions. Set value to None as a shorthand for deferring to the 
        default xml for that session. 
        '''
        self.default_scxml_doc = default_scxml_doc
        self.sm_mapping = {}
        self.get = self.sm_mapping.get
        for sessionid, xml in list(init_sessions.items()):
            self.make_session(sessionid, xml)
            
    def __iter__(self):
        return iter(list(self.sm_mapping.values()))
    
    def __delitem__(self, val):
        del self.sm_mapping[val]
    
    def __getitem__(self, val):
        return self.sm_mapping[val]
    
    #TODO:remove this
#    def __setitem__(self, key, val):
#        self.make_session(key, valu)
#        for sessionid, session in self.sm_mapping.items():
#            self[sm.datamodel["_sessionid"]] = sm
#            sm.datamodel["_x"]["sessions"][sessionid] = session
    
    def start(self):
        ''' launches the initialized sessions by calling start() on each sm'''
        for sm in self:
            sm.start_threaded()
            
    
    def make_session(self, sessionid, xml):
        '''initalizes and starts a new StateMachine 
        session at the provided sessionid.
        @param xml: A string. if None or empty, the statemachine at this 
        sesssionid will run the document specified as default_scxml_doc 
        in the constructor. Otherwise, the xml will be run. 
        @return: the resulting scxml.pyscxml.StateMachine instance. It has 
        not been started, only initialized.
         '''
        assert xml or self.default_scxml_doc
        sm = StateMachine(xml or self.default_scxml_doc)
        self.sm_mapping[sessionid] = sm
        sm.datamodel["_x"]["sessions"] = self
        sm.datamodel["_sessionid"] = sessionid
        dispatcher.connect(self.on_sm_exit, "signal_exit", sm)
        return sm
    
    def on_sm_exit(self, sender):
        if sender.datamodel["_sessionid"] in self:
            del self[sender.datamodel["_sessionid"]]



if __name__ == "__main__":
    
    xml = open("/Users/johan/Development/workspace_helios/pyscxml/examples/websockets/websocket_server.xml").read()
#    xml = open("../../resources/history_variant.xml").read()
#    xml = open("../../unittest_xml/history.xml").read()
#    xml = open("../../unittest_xml/invoke.xml").read()
#    xml = open("../../unittest_xml/invoke_soap.xml").read()
#    xml = open("../../unittest_xml/factorial.xml").read()
#    xml = open("../../unittest_xml/error_management.xml").read()
    
    
    sm = StateMachine(xml)
    sm.start()
    

