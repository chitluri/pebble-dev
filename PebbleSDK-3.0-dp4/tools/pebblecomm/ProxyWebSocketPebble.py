from WebSocketPebble import *
from struct import pack, unpack
import logging

WS_PROXY_URL = "wss://ws-proxy.getpebble.com/tool"

# WIP, does not handle auth failures or disconnects
class ProxyWebSocketPebble(WebSocketPebble):
   def __init__(self, account, *args, **kwargs):
       super(ProxyWebSocketPebble, self).__init__(*args, **kwargs)
       self.account = account
       self.login_attempts = 0

   def connect(self, *args, **kwargs):
       super(ProxyWebSocketPebble, self).connect(*args, **kwargs)
       self.login()

   def login(self):
       token = self.account.get_access_token().encode('ascii')
       logging.debug("Sending auth token " + token)
       data = pack('b', len(token)) + token

       self.write(data, ws_cmd = WS_CMD_PROXY_AUTHENTICATION)
       self.read()

   def handle_cmd(self, ws_cmd, data):
       if ws_cmd == WS_CMD_PROXY_AUTHENTICATION:
           status = unpack('!b', data[1])[0]
           if len(data) == 2 and status == 0x00:
               logger.info("Auth success")
           else:
               logger.error("Auth failed")
               raise Exception('Cloud auth failed')
           return (None, None, None, data)
       elif ws_cmd == WS_CMD_PROXY_CONNECTION_UPDATE:
           return (None, None, None, data)
       else:
           return super(ProxyWebSocketPebble, self).handle_cmd(ws_cmd, data)

def create_connection(account, timeout = None, connect_timeout = None, **options):
   try:
       sockopt = options.get("sockopt", ())
       websock = ProxyWebSocketPebble(account, sockopt=sockopt)
       websock.settimeout(connect_timeout is not None and connect_timeout or default_timeout)
       websock.connect(WS_PROXY_URL, **options)
       websock.settimeout(timeout is not None and timeout or default_timeout)
   except socket.timeout as e:
       logging.error("Could not connect to phone at. Connection timed out")
       os._exit(-1)
   except socket.error as e:
       if e.errno == errno.ECONNREFUSED:
           logging.error("Could not connect to phone. "
                     "Ensure that 'Developer Connection' is enabled in the Pebble app.")
           os._exit(-1)
       else:
           raise e
   except WebSocketConnectionClosedException as e:
       logging.error("Connection was rejected. The Pebble app is already connected to another client.")
       os._exit(-1)
   return websock

