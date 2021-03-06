
import sys
import json
import math
import time
import random
from glob import glob
from itertools import izip_longest
from os.path import dirname, abspath

# install_twisted_rector must be called before importing the reactor
from kivy.support import install_twisted_reactor
install_twisted_reactor()
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.uix.carousel import Carousel
from kivy.uix.boxlayout import BoxLayout
# TODO: switch from carousel to screen manager
# from kivy.uix.screenmanager import ScreenManager, Screen

from kivy.core.audio import SoundLoader
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
START_VOLUME = 0.2

EDIT_COLOR = (1.0, 1.0, 1.0)
ANON_COLOR = (46 / 255.0, 204 / 255.0, 113 / 255.0)
BOT_COLOR = (155 / 255.0, 89 / 255.0, 182 / 255.0)

CUR_PATH = dirname(abspath(__file__))
AUDIO_PATH = CUR_PATH + '/audio/'


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
        try:
            error_message = reason.getErrorMessage()
        except:
            error_message = repr(reason)
        print("Client connection failed (%s). Retrying..." % error_message)
        self.retry(connector)

    def clientConnectionLost(self, connector, reason):
        try:
            error_message = reason.getErrorMessage()
        except:
            error_message = repr(reason)

        print("Client connection lost (%s). Reconnecting..." % error_message)
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
        if self.metadata.get('is_anon'):
            self.rgb = ANON_COLOR
        elif self.metadata.get('is_bot'):
            self.rgb = BOT_COLOR
        else:
            self.rgb = EDIT_COLOR

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


class Soundboard(object):
    def load(self):
        self.sound_map = {}
        self.playback_map = {}
        for instr in ('swells', 'clav', 'celesta'):
            sound_fns = []
            self.sound_map[instr] = []
            for fn in glob(AUDIO_PATH + instr + '/*.mp3'):
                sound_fns.append(fn)
            sound_fns.sort()
            for fn in sound_fns:
                sound = SoundLoader.load(fn)
                sound.volume = START_VOLUME
                if instr == 'swells':
                    # swells sound a bit quiet and have less overlap
                    sound.volume = min(1.0, sound.volume + 0.2)
                self.sound_map[instr].append(sound)
            self.playback_map[instr] = [False] * len(self.sound_map[instr])
        self.top_pitch_idx = len(self.sound_map['celesta']) - 1  # TODO

    def _get_index(self, size):
        size = abs(size)
        max_pitch = 100.0
        log_used = 1.0715307808111486871978099
        pitch_adjust = math.log(size + log_used) / math.log(log_used)
        pitch = 100.0 - min(max_pitch, pitch_adjust)
        index = math.floor(pitch / 100.0 * (self.top_pitch_idx + 1))

        # bracket it within reason and turn it into an int
        index = int(round(max(0, min(self.top_pitch_idx, index))))
        return index

    def play_change(self, size):
        try:
            size = int(size)
        except:
            return
        idx = self._get_index(size)
        instr = 'celesta'
        if size < 0:
            instr = 'clav'
        sound_map = self.sound_map[instr]
        for cur_idx in iter_probe(len(sound_map), idx, -1, 5):
            sound = sound_map[cur_idx]
            if sound.state != 'play':
                break
        else:
            # if everything is going off, stick to the original idx
            sound = sound_map[idx]
            sound.seek(0)
        sound.play()
        return

    def play_new_user(self):
        idx = random.randint(0, 2)
        sound_map = self.sound_map['swells']
        for cur_idx in iter_probe(len(sound_map), idx):
            sound = sound_map[cur_idx]
            if sound.state != 'play':
                break
        else:
            sound = sound_map[idx]
            sound.seek(0)
        sound.play()
        return


def iter_probe(len_seq, idx, step=1, count=None):
    """Probe sequence indices up to but not including *len_seq* based on
    proximity to target index *idx*, according to *step* (1 goes up
    first, the default, whereas -1 down first), yielding a maximum of
    *count* indices. Yields only integers >= 0.

    >>> list(iter_nearest(range(10), 3))
    [3, 4, 2, 5, 1, 6, 0, 7, 8, 9]
    >>> list(iter_nearest(range(10), 3, count=5))
    [3, 4, 2, 5, 1]
    >>> list(iter_nearest(range(10), 3, step=-1))
    [3, 2, 4, 1, 5, 0, 6, 7, 8, 9]
    >>> list(iter_nearest(range(10), 3, step=-2))
    [3, 2, 5, 0, 7, 9]
    >>> list(iter_nearest(range(10), 3, count=0))
    []
    >>> list(iter_nearest(range(0), 3, count=5))
    []
    >>> list(iter_nearest(range(10), 100))
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    """
    if count is None:
        count = len_seq
    abs_step = abs(step)
    if step > 0:
        before = xrange(min(idx, len_seq - 1), -1, -abs_step)
        after = xrange(max(0, idx + 1), len_seq, abs_step)
        izipper = izip_longest(before, after)
    else:
        before = xrange(min(idx - 1, len_seq - 1), -1, -abs_step)
        after = xrange(max(0, idx), len_seq, abs_step)
        izipper = izip_longest(after, before)
    gen = (v for pair in izipper for v in pair if v is not None)
    i = 0
    while i < count:
        yield next(gen)
        i += 1
    return


class L2WVisualWidget(Widget):
    # TODO?
    def __init__(self, **kwargs):
        super(L2WVisualWidget, self).__init__(**kwargs)


class L2WApp(App):
    """TODO:

    * console_layout
    * settings_layout
    * about_layout

    Also, the position of shapes on the canvas has screens overlapping
    at the moment. ScreenManager might fix this?
    """
    def build(self):
        self.changes = []
        log.startLogging(sys.stdout)
        root = self.init_ui()
        Clock.schedule_once(self.connect_to_server, 0.1)
        return root

    def init_ui(self):
        self.carousel = Carousel(direction='right')

        self.layout = BoxLayout(orientation='vertical')

        Clock.schedule_interval(self.update_ui, 1.0 / 60.0)
        self.soundboard = Soundboard()
        self.soundboard.load()

        self._init_about_layout()
        self._init_console_layout()

        self.carousel.add_widget(self.layout)
        self.carousel.add_widget(self.console_layout)
        self.carousel.add_widget(self.about_layout)
        return self.carousel

    def _init_about_layout(self):
        self.about_layout = BoxLayout(orientation='vertical')
        self.about_text = 'Listen to Wikipedia is brought to you\nby Stephen LaPorte and Mahmoud Hashemi'
        about_label = Label(text=self.about_text)
        self.about_layout.add_widget(about_label)

    def _init_console_layout(self):
        self.console_layout = BoxLayout(orientation='vertical')

    def connect_to_server(self, delta):
        factory = L2WFactory(self, "ws://listen.hatnote.com:9000", debug=False)
        reactor.connectTCP("listen.hatnote.com", 9000, factory)

    def handle_message(self, msg):
        change_item = ChangeItem(msg, app=self)
        self.changes.append(change_item)
        if msg['page_title'] == 'Special:Log/newusers':
            self.soundboard.play_new_user()
        else:
            self.soundboard.play_change(msg['change_size'])
        if len(self.console_layout.children) > 15:
            self.console_layout.remove_widget(self.console_layout.children[-1])
        self.console_layout.add_widget(Label(text=change_item.metadata['page_title']))

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
                    # print 'removed change', change
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
