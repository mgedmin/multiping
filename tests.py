import curses
import itertools
import os
import subprocess
import sys
import time
from functools import partial

import mock
import pytest

import multiping


class FakePinger:
    def __init__(self, hostname=None, interval=1, hour=12, minute=30,
                 second=0):
        self.status = []
        self.version = 0
        self.interval = interval
        self.sent = self.received = 0
        self.started = time.mktime(
            (2000, 5, 22, hour, minute, second, 0, 0, 0))

    def start(self):
        pass

    def quit(self):
        pass

    def set(self, idx, result):
        while idx >= len(self.status):
            self.status.append(' ')
        self.status[idx] = result
        self.version += 1


def test_Ping():
    pinger = FakePinger()
    ping = multiping.Ping(pinger, 42, 'localhost')
    # this runs an actual 'ping localhost' in a subprocess, and a thread
    # doing a waitpid() on that process
    ping.start()
    # this kills the ping process
    ping.timeout(hard=True)
    ping.join()
    # we don't expect any particular result, but we expect a result
    assert pinger.status[42] in '!?#%-'


class FakePopen:
    def __init__(self, command, stdin=None, stdout=None,
                 stderr=None, returncode=0):
        self.pid = 123
        self.returncode = returncode

    def wait(self):
        return self.returncode


@pytest.mark.parametrize('delay, status, char', [
    (0, 0, '#'),
    (2, 0, '%'),
    (0, 1, '-'),
    (0, OSError(), '?'),
    (0, -9, '!'),
])
def test_Ping_run_parent(monkeypatch, delay, status, char):
    if isinstance(status, Exception):
        monkeypatch.setattr(
            subprocess, 'Popen', mock.Mock(side_effect=status))
    else:
        monkeypatch.setattr(
            subprocess, 'Popen', partial(FakePopen, returncode=status))
    now = time.time()
    monkeypatch.setattr(multiping, 'time',
                        mock.Mock(side_effect=[now, now+delay]))
    pinger = FakePinger()
    ping = multiping.Ping(pinger, 42, 'localhost')
    ping.run()
    assert pinger.status[42] == char


@pytest.mark.parametrize('exc', [OSError, TypeError])
def test_Ping_timeout_no_race(monkeypatch, exc):
    monkeypatch.setattr(os, 'kill', mock.Mock(side_effect=exc))
    # If the ping process exits after we check that it exists, but before we
    # try to kill it, os.kill() may raise an exception.  The exception can be
    # an OSError (process does not exist) or a TypeError (the waiting thread
    # set self.ping to None).
    pinger = FakePinger()
    ping = multiping.Ping(pinger, 42, 'localhost')
    ping.pid = os.getpid()  # ha ha, hope the monkeypatch worked
    ping.timeout()


def test_Pinger():
    pinger = multiping.Pinger('localhost', 0.001)
    pinger.set(42, '!')
    assert pinger.status[0] == ' '
    assert pinger.status[42] == '!'
    # this runs an actual 'ping localhost' in a subprocess, and a thread
    # doing a waitpid() on that process, and another thread waiting to
    # run even more ping processes
    pinger.start()
    assert pinger.running
    pinger.quit()
    assert not pinger.running
    pinger.join()


class LimitedPinger(multiping.Pinger):
    limit = 30

    def set(self, idx, result):
        super(LimitedPinger, self).set(idx, result)
        if idx >= self.limit:
            self.running = False


def test_Pinger_queue(monkeypatch):
    # This will actually launch 30 ping processes
    monkeypatch.setattr(multiping, 'sleep', lambda seconds: None)
    monkeypatch.setattr(multiping, 'time', lambda: 12345678)
    pinger = LimitedPinger('localhost', 1)
    pinger.run()


def test_Pinger_time_runs_fast(monkeypatch):
    # This will actually launch 30 ping processes
    monkeypatch.setattr(multiping, 'sleep', lambda seconds: None)
    timer = itertools.count(12345000)
    monkeypatch.setattr(multiping, 'time', lambda: next(timer))
    pinger = LimitedPinger('localhost', 1)
    pinger.run()


class FakePing:
    def __init__(self, pinger, idx, hostname):
        self.success = bool(idx % 2)

    def start(self):
        pass

    def timeout(self, hard=False):
        pass


def test_Pinger_counts_successes(monkeypatch):
    monkeypatch.setattr(multiping, 'sleep', lambda seconds: None)
    pinger = LimitedPinger('localhost', 1, factory=FakePing)
    pinger.run()
    assert pinger.sent == 11
    assert pinger.received == 5


class FakeCursesWindow:

    def __init__(self, width=80, height=24):
        self._resize(width, height)

    def _resize(self, width=None, height=None):
        if width:
            self._width = width
        if height:
            self._height = height
        self.move(0, 0)
        self._screen = [[' '] * self._width for _ in range(self._height)]

    def addstr(self, *args):
        # args may be (row, col, text), or (text, attr), or just (text, )
        if len(args) == 3:
            self._row, self._col, text = args
        elif len(args) == 2:
            text, attr = args
        else:
            text = args[0]
        try:
            for c in text:
                self._screen[self._row][self._col] = c
                self._col += 1
                # it is a curses.error to start drawing outside the screen,
                # but too long strings get truncated
                if self._col >= self._width:
                    break
        except IndexError:
            raise curses.error

    def move(self, row, col):
        self._row = row
        self._col = col

    def clrtoeol(self):
        try:
            for col in range(self._col, self._width):
                self._screen[self._row][col] = ' '
        except IndexError:
            raise curses.error

    def clrtobot(self):
        for row in range(self._row, self._height):
            for col in range(self._col, self._width):
                self._screen[row][col] = ' '

    def clear(self):
        self.move(0, 0)
        self.clrtobot()

    def _lines(self):
        return [
            ''.join(row).rstrip() for row in self._screen
        ]

    def _text(self):
        return '\n'.join(self._lines())


class FakeCursesScreen(FakeCursesWindow):

    def __init__(self, *args, **kwargs):
        self.input_queue = kwargs.pop('input_queue', [])
        FakeCursesWindow.__init__(self, **kwargs)

    def getmaxyx(self):
        return (self._height - 1, self._width - 1)

    def getch(self):
        while True:
            event = self.input_queue.pop(0)
            if callable(event):
                event()
            elif isinstance(event, str):
                return ord(event)
            else:
                return event

    def refresh(self):
        pass


@pytest.fixture
def fake_curses(monkeypatch):
    mock_curses = mock.Mock()
    mock_curses.COLUMNS = 80
    mock_curses.LINES = 24
    consts = 'A_BOLD KEY_RESIZE KEY_UP KEY_DOWN KEY_PPAGE KEY_NPAGE'.split()
    for const in consts:
        setattr(mock_curses, const, getattr(curses, const))
    mock_curses.color_pair = lambda pair: pair
    mock_curses.error = curses.error
    monkeypatch.setattr(multiping, 'curses', mock_curses)


def test_UI_draw(fake_curses):
    pinger = FakePinger(hour=12, minute=30, second=3)
    pinger.set(0, '#')
    pinger.set(31, '%')
    pinger.set(62, '-')
    pinger.set(93, '.')
    win = FakeCursesWindow(width=80, height=7)
    ui = multiping.UI(win, 2, 2, 30, 5, pinger, 'example.com')
    ui.draw()
    assert win._text() == '\n'.join([
        '',
        '  pinging example.com',
        '  12:30 [   #                          ]',
        '  12:30 [    %                         ]',
        '  12:31 [     -                        ]',
        '  12:31 [      .                       ]',
        '',
    ])


def test_UI_draw_screen_too_small(fake_curses):
    pinger = FakePinger(hour=12, minute=30, second=3)
    pinger.set(0, '#')
    pinger.set(31, '%')
    pinger.set(62, '-')
    pinger.set(93, '.')
    win = FakeCursesWindow(width=20, height=1)
    ui = multiping.UI(win, 1, 2, 30, 4, pinger, 'example.com')
    ui.draw()
    assert win._text() == '\n'.join([
        '  pinging example.co',
    ])


def test_UI_draw_packet_loss(fake_curses):
    pinger = FakePinger()
    pinger.sent = 3
    pinger.received = 2
    win = FakeCursesWindow(height=1)
    ui = multiping.UI(win, 1, 0, 60, 0, pinger, 'example.com')
    ui.draw()
    assert win._text() == '\n'.join([
        'pinging example.com: packet loss 33.3%',
    ])


def test_UI_draw_autoscroll(fake_curses):
    pinger = FakePinger(hour=12, minute=30, second=3)
    pinger.set(0, '#')
    pinger.set(31, '%')
    pinger.set(62, '-')
    pinger.set(93, '.')
    win = FakeCursesWindow(width=80, height=6)
    ui = multiping.UI(win, 1, 0, 30, 4, pinger, 'example.com')
    ui.draw()
    assert win._text() == '\n'.join([
        'pinging example.com',
        '12:30 [   #                          ]',
        '12:30 [    %                         ]',
        '12:31 [     -                        ]',
        '12:31 [      .                       ]',
        '',
    ])
    pinger.set(124, '!')
    ui.draw()
    assert win._text() == '\n'.join([
        'pinging example.com',
        '12:30 [    %                         ]',
        '12:31 [     -                        ]',
        '12:31 [      .                       ]',
        '12:32 [       !                      ]',
        '',
    ])


def test_UI_draw_no_autoscroll(fake_curses):
    pinger = FakePinger(hour=12, minute=30, second=3)
    pinger.set(0, '#')
    pinger.set(31, '%')
    pinger.set(62, '-')
    pinger.set(93, '.')
    win = FakeCursesWindow(width=80, height=6)
    ui = multiping.UI(win, 1, 0, 30, 4, pinger, 'example.com')
    ui.draw()
    assert win._text() == '\n'.join([
        'pinging example.com',
        '12:30 [   #                          ]',
        '12:30 [    %                         ]',
        '12:31 [     -                        ]',
        '12:31 [      .                       ]',
        '',
    ])
    ui.autoscrolling = False
    pinger.set(124, '!')
    ui.draw()
    assert win._text() == '\n'.join([
        'pinging example.com',
        '12:30 [   #                          ]',
        '12:30 [    %                         ]',
        '12:31 [     -                        ]',
        '12:31 [      .                       ]',
        '',
    ])


def test_UI_update_no_changes(fake_curses):
    pinger = FakePinger(hour=12, minute=30)
    win = FakeCursesWindow(width=80, height=5)
    ui = multiping.UI(win, 1, 0, 30, 4, pinger, 'example.com')
    # first update draws
    assert ui.update()
    # second doesn't because nothing changed
    assert not ui.update()
    # third update draws again
    pinger.set(0, '#')
    assert ui.update()


HELLO = [
    (0, 1), (0, 4),
    (1, 1), (1, 4),
    (2, 1), (2, 2), (2, 3), (2, 4),
    (3, 1), (3, 4),
    (4, 1), (4, 4),

    (0, 7), (0, 8), (0, 9), (0, 10),
    (1, 7),
    (2, 7), (2, 8),
    (3, 7),
    (4, 7), (4, 8), (4, 9), (4, 10),

    (0, 13),
    (1, 13),
    (2, 13),
    (3, 13),
    (4, 13), (4, 14), (4, 15), (4, 16),

    (0, 19),
    (1, 19),
    (2, 19),
    (3, 19),
    (4, 19), (4, 20), (4, 21), (4, 22),

    (0, 26), (0, 27),
    (1, 25), (1, 28),
    (2, 25), (2, 28),
    (3, 25), (3, 28),
    (4, 26), (4, 27),
]


def test_UI_update_resize(fake_curses):
    pinger = FakePinger(hour=12, minute=30)
    for y, x in HELLO:
        pinger.set(y*30+x, '#')
    win = FakeCursesWindow(width=80, height=6)
    ui = multiping.UI(win, 1, 0, 30, 5, pinger, 'example.com')
    ui.draw()
    assert win._text() == '\n'.join([
        'pinging example.com',
        '12:30 [ #  #  ####  #     #      ##  ]',
        '12:30 [ #  #  #     #     #     #  # ]',
        '12:31 [ ####  ##    #     #     #  # ]',
        '12:31 [ #  #  #     #     #     #  # ]',
        '12:32 [ #  #  ####  ####  ####   ##  ]',
    ])
    win._resize(height=4)
    ui.resize(3)
    assert win._text() == '\n'.join([
        'pinging example.com',
        '12:31 [ ####  ##    #     #     #  # ]',
        '12:31 [ #  #  #     #     #     #  # ]',
        '12:32 [ #  #  ####  ####  ####   ##  ]',
    ])
    ui.scroll_to_top()
    assert win._text() == '\n'.join([
        'pinging example.com',
        '12:30 [ #  #  ####  #     #      ##  ]',
        '12:30 [ #  #  #     #     #     #  # ]',
        '12:31 [ ####  ##    #     #     #  # ]',
    ])
    assert not ui.autoscrolling
    ui.scroll_to_bottom()
    assert win._text() == '\n'.join([
        'pinging example.com',
        '12:31 [ ####  ##    #     #     #  # ]',
        '12:31 [ #  #  #     #     #     #  # ]',
        '12:32 [ #  #  ####  ####  ####   ##  ]',
    ])
    assert ui.autoscrolling


def test_UI_before_start(fake_curses):
    pinger = FakePinger(hour=12, minute=30)
    pinger.started = -1
    win = FakeCursesWindow(width=80, height=6)
    ui = multiping.UI(win, 1, 0, 30, 5, pinger, 'example.com')
    ui.draw()
    ui.scroll(0)
    ui.scroll_to_top()
    ui.scroll_to_bottom()


CTRL_L = ord('L') - ord('@')


def test_main(monkeypatch, fake_curses):
    pinger = FakePinger()
    monkeypatch.setattr(multiping, 'Pinger', lambda *args, **kw: pinger)
    win = FakeCursesScreen(
        width=80, height=6,
        input_queue=[
            lambda: pinger.set(0, '.'),
            'j', 'k', 'g', 'G', CTRL_L, curses.KEY_PPAGE, curses.KEY_NPAGE,
            curses.KEY_RESIZE, 'f', 'F', ' ', 'q'],
    )
    multiping._main(win, 'localhost')


@pytest.mark.parametrize('argv', [
    'multiping'.split(),
    'multiping -h'.split(),
    'multiping --help'.split(),
])
def test_main_prints_help(monkeypatch, argv):
    monkeypatch.setattr(sys, 'argv', argv)
    with pytest.raises(SystemExit):
        multiping.main()


def test_main_swallows_keyboard_interrupt(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['multiping', 'localhost'])
    monkeypatch.setattr(curses, 'wrapper',
                        mock.Mock(side_effect=KeyboardInterrupt))
    multiping.main()
