
import sys
import json
import time

#install_twisted_rector must be called before importing the reactor
from kivy.support import install_twisted_reactor
install_twisted_reactor()
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.graphics import Color, Ellipse


from twisted.python import log
from twisted.internet import reactor
from twisted.internet.protocol import ReconnectingClientFactory
from autobahn.twisted.websocket import (WebSocketClientFactory,
                                        WebSocketClientProtocol)

MIN_SIZE = 3
SCALE_FACTOR = 5
START_OPACITY = 1.0
FADEOUT_SECONDS = 15.0


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


class ChangeItem(object):
    def __init__(self, metadata, app):
        self.create_time = time.time()
        self._app = app
        self.metadata = metadata
        self._set_color()
        self._set_radius()
        self._set_position()

    def _set_color(self):
        self.rgb = (1.0, 1.0, 1.0)

    def _set_radius(self):
        size = self.metadata['change_size']
        self.radius = max((abs(size or 0) ** 0.5) * SCALE_FACTOR, MIN_SIZE)

    def _set_position(self):
        import hashlib
        width, height = self._app.layout.width, self._app.layout.height
        title = self.metadata['page_title'].encode('utf8')
        digest = hashlib.md5(title).hexdigest()
        xdigest, ydigest = digest[:8], digest[-8:]
        x, y = int(xdigest, 16) % width, int(ydigest, 16) % height
        self.pos = (x, y)

    def __repr__(self):
        cn = self.__class__.__name__
        return ('<%s title=%r user=%r size=%r>'
                % (cn, self.metadata['page_title'],
                   self.metadata['user'], self.metadata['change_size']))


class L2WApp(App):
    connection = None

    def build(self):
        self.changes = []
        root = self.setup_gui()
        self.connect_to_server()
        return root

    def setup_gui(self):
        self.textbox = TextInput(size_hint_y=.1, multiline=False)
        self.label = Label(text='connecting...\n')
        self.layout = BoxLayout(orientation='vertical')
        self.layout.add_widget(self.label)
        self.layout.add_widget(self.textbox)

        Clock.schedule_interval(self.update_ui, 1.0 / 60.0)

        return self.layout

    def connect_to_server(self):
        log.startLogging(sys.stdout)

        factory = L2WFactory(self, "ws://listen.hatnote.com:9000", debug=False)

        reactor.connectTCP("listen.hatnote.com", 9000, factory)
        # reactor.run()

    def on_connection(self, connection):
        self.print_message("connected succesfully!")
        self.connection = connection

    def handle_message(self, msg):
        change_item = ChangeItem(msg, app=self)
        self.changes.append(change_item)
        self.label.text = str(msg).encode('utf8')

    def update_ui(self, dt):
        layout = self.layout
        layout.canvas.clear()
        with layout.canvas:
            cur_time = time.time()
            next_changes = []
            for change in self.changes:
                fade = ((cur_time - change.create_time) / FADEOUT_SECONDS)
                opacity = START_OPACITY - fade
                if opacity <= 0:
                    print 'removed change', change
                    continue
                next_changes.append(change)
                color = change.rgb + (opacity,)
                Color(*color)
                Ellipse(pos=change.pos, size=(change.radius, change.radius))
            self.changes[:] = next_changes
        return


if __name__ == '__main__':
    L2WApp().run()


"""
        import hashlib
        page_title = msg['page_title'].encode('utf8')
        change_size = msg['change_size']
        digest = hashlib.md5(page_title).hexdigest()
        xdigest, ydigest = digest[:8], digest[-8:]
        x, y = int(xdigest, 16) % width, int(ydigest, 16) % height

"""


"""
        import zlib
        title = msg['page_title'].encode('utf8')
        change_size = msg['change_size']
        odd_chars = ''.join([c for i, c in enumerate(title) if i % 2 == 1])
        even_chars = ''.join([c for i, c in enumerate(title) if i % 2 == 0])
        xdigest, ydigest = zlib.adler32(even_chars), zlib.adler32(odd_chars)
        x, y = xdigest % width, ydigest % height

"""
