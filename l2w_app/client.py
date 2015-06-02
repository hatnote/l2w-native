
import sys
import json

#install_twisted_rector must be called before importing the reactor
from kivy.support import install_twisted_reactor
install_twisted_reactor()
from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.graphics import Color, Ellipse


from twisted.python import log
from twisted.internet import reactor
from twisted.internet.protocol import ReconnectingClientFactory
from autobahn.twisted.websocket import (WebSocketClientFactory,
                                        WebSocketClientProtocol)


class L2WProtocol(WebSocketClientProtocol):
    def onConnect(self, response):
        print("Server connected: {0}".format(response.peer))

    def onOpen(self):
        print("WebSocket connection open.")

    def onMessage(self, payload, isBinary):
        try:
            msg = json.loads(payload)
        except Exception as e:
            print('could not load message: %r' % e)
            return
        self.factory.app.handle_message(msg)

    def onClose(self, wasClean, code, reason):
        print("WebSocket connection closed: {0}".format(reason))


class L2WFactory(WebSocketClientFactory, ReconnectingClientFactory):
    protocol = L2WProtocol

    def __init__(self, app, *a, **kw):
        self.app = app
        super(L2WFactory, self).__init__(*a, **kw)

    def clientConnectionFailed(self, connector, reason):
        print("Client connection failed. Retrying...")
        self.retry(connector)

    def clientConnectionLost(self, connector, reason):
        print("Client connection lost. Reconnecting...")
        self.retry(connector)


class L2WApp(App):
    connection = None

    def build(self):
        root = self.setup_gui()
        self.connect_to_server()
        return root

    def setup_gui(self):
        self.textbox = TextInput(size_hint_y=.1, multiline=False)
        self.label = Label(text='connecting...\n')
        self.layout = BoxLayout(orientation='vertical')
        self.layout.add_widget(self.label)
        self.layout.add_widget(self.textbox)
        return self.layout

    def connect_to_server(self):
        log.startLogging(sys.stdout)

        factory = L2WFactory(self, "ws://listen.hatnote.com:9000", debug=False)
        factory.protocol = L2WProtocol

        reactor.connectTCP("listen.hatnote.com", 9000, factory)
        # reactor.run()

    def on_connection(self, connection):
        self.print_message("connected succesfully!")
        self.connection = connection

    def _msg_to_dimcoord(self, page_title, height, width):
        import hashlib
        # TODO: calc size, subtract from height/width to keep circle inside
        digest = hashlib.md5(page_title).hexdigest()
        xdigest, ydigest = digest[:16], digest[16:]
        x, y = int(xdigest, 16) % height, int(ydigest, 16) % width
        return (x, y), 100

    def handle_message(self, msg):
        widget = self.layout
        with widget.canvas:
            Color(1.0, 1.0, 1.0, 0.1)
            coord, size = self._msg_to_dimcoord(msg['page_title'],
                                                widget.height,
                                                widget.width)
            Ellipse(pos=coord, size=(size, size))
        self.label.text = str(msg)

if __name__ == '__main__':
    L2WApp().run()
