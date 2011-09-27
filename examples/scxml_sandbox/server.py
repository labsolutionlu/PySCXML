from scxml.pyscxml_server import PySCXMLServer, TYPE_WEBSOCKET, TYPE_DEFAULT, TYPE_RESPONSE, ioprocessor
import logging
logging.basicConfig(level=logging.NOTSET)

server = PySCXMLServer("mac21.svenska.gu.se", 8081, 
                        init_sessions={"server" : open("sandbox_server.xml").read()},
                        server_type=TYPE_RESPONSE | TYPE_WEBSOCKET
                        )


server.serve_forever()

#from wsgiref.simple_server import make_server
#from time import sleep
#from ws4py.server.wsgi.middleware import WebSocketUpgradeMiddleware
#
#from eventlet import wsgi, websocket
#import eventlet


#def hello_world_app(environ, start_response):
#    print environ["PATH_INFO"].split("/")
#    if environ["PATH_INFO"].split("/")[2] == "sse":
#        status = '200 OK' # HTTP Status
#        headers = [('Content-type', 'text/event-stream')] # HTTP Headers
#        start_response(status, headers)
#        
#        def gen():
#            for n in range(10):
#                yield "data:%s\n" % str(n)
#                sleep(1)
#        
#        return gen()
#    else:
#        status = '200 OK' # HTTP Status
#        headers = [('Content-type', 'text/html')] # HTTP Headers
#        start_response(status, headers)
#        return [""]

@websocket.WebSocketWSGI
def websocket_handler(ws):
    print "handle"
    ws.send("hello")
#    while True:
#        message = ws.wait()
#        if message is None:
#            break
#        print "message received:", message
#        ws.send(message)

#httpd = make_server('', 8081, WebSocketUpgradeMiddleware(websocket_handler))
wsgi.server(eventlet.listen(('localhost', 8081)), websocket_handler)
print "Serving on port 8081..."

# Serve until process is killed
httpd.serve_forever()