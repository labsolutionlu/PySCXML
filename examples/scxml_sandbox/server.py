#!/usr/bin/python
from scxml.pyscxml_server import WebsocketWSGI
from scxml.pyscxml import register_datamodel
from scxml.datamodel import PythonDataModel
import logging
import os, json, sys
from safe_eval import safe_eval
import eventlet
from eventlet import wsgi, websocket

class SafePythonDataModel(PythonDataModel):
    def hasLocation(self, location):
        try:
            safe_eval(location, self)
            return True
        except:
            return False
        
    def evalExpr(self, expr):
        try:
            safe_eval('_x["__output"] = (%s)' % expr, self)
        except:
            raise
            
        return self["_x"]["__output"]
    
    def execExpr(self, expr):
        safe_eval(expr, self)

register_datamodel("safe_python", SafePythonDataModel)


def main(address):
    os.environ["PYSCXMLPATH"] = "example_docs:resources"
    files = dict([(x, z) for (x, y, z) in os.walk("example_docs") if ".svn" not in x])
    json.dump(files, open("example_list.json", "w"))
    
    pyscxml = WebsocketWSGI(address[0], address[1], 
                            init_sessions={"server" : "sandbox_server.xml", 
                                           "echo" : "example_docs/echo.scxml",
                                           "508" : "example_docs/raw/test508Server.xml", 
                                           "509" : "example_docs/raw/test509Server.xml", 
                                           },
                            default_datamodel="ecmascript"
                            )

    
    def eventletHandler(environ, start_response):
        pathlist = list(filter(bool, environ["PATH_INFO"].split("/")))
        session = pathlist[0]
        
        if session == "info":
            headers = {"Content-Type" : "text/plain"}
            start_response("200 OK", list(headers.items()))
            output = ["Things seem to be running smoothly. There are currently %s document(s) running." % len(list(pyscxml.sm_mapping)),
                      "Session\t\tConfiguration\t\tisFinished"]
            for sessionid, sm in list(pyscxml.sm_mapping.items()):
                output.append("%s\t\t%s\t\t%s" % (sessionid, "{" + ", ".join([s.id for s in sm.interpreter.configuration if s.id != "__main__"]) + "}", sm.isFinished()))
            return ["\n".join(output)]
        
        
        type = pathlist[1]
        
        if type == "websocket":  
            handler = websocket.WebSocketWSGI(pyscxml.websocket_handler)
            return handler(environ, start_response)
        else:
            return pyscxml.request_handler(environ, start_response)
        
        
    wsgi.server(eventlet.listen(address), eventletHandler)
    

if __name__ == '__main__':
    
    
    import sys
    isDev = len(sys.argv[1:]) == 0
    if not isDev :
        host, port, log_file = sys.argv[1:]
        logging.basicConfig(level=logging.NOTSET, filename=log_file, filemode="w")
        address = tuple([host, int(port)])
    else:
        logging.basicConfig(level=logging.NOTSET)
        address = ("localhost", 8081)
    
    try:
        main(address)
    except:
        logging.exception("Error caught in main:")
