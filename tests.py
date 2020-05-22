import curses
import os
import sys
import time
from collections import defaultdict

import mock
import pytest

import multiping


class FakePinger:
    def __init__(self, hour=12, minute=30, second=0):
        self.results = defaultdict(lambda: ' ')
        self.version = 0
        self.interval = 1
        self.status = self.results
        self.sent = self.received = 0
        self.started = time.mktime(
            (2000, 5, 22, hour, minute, second, 0, 0, 0))

    def set(self, idx, result):
        self.results[idx] = result
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
    assert 42 in pinger.results


def test_Ping_run_child(monkeypatch):
    # This is a silly test, good only for catching typos
    monkeypatch.setattr(os, 'fork', lambda: 0)
    monkeypatch.setattr(os, 'dup2', lambda fd1, fd2: None)
    monkeypatch.setattr(os, 'execlp', lambda *argv: None)
    monkeypatch.setattr(sys, 'exit', lambda rc: None)
    pinger = FakePinger()
    ping = multiping.Ping(pinger, 42, 'localhost')
    ping.run()


@pytest.mark.parametrize('delay, status, char', [
    # this assumes a certain implementation of WIFSIGNALED and WEXITSTATUS,
    # i.e. the low 7 bits are signal number, the high 8 bits are exit status
    (0, 0, '#'),
    (2, 0, '%'),
    (0, 1 << 8, '-'),
    (0, 99 << 8, '?'),
    (0, 9, '!'),
])
def test_Ping_run_parent(monkeypatch, delay, status, char):
    # This is a silly test, good only for catching typos
    monkeypatch.setattr(os, 'fork', lambda: 1234)
    monkeypatch.setattr(os, 'waitpid', lambda pid, flags: (pid, status))
    now = time.time()
    monkeypatch.setattr(multiping, 'time',
                        mock.Mock(side_effect=[now, now+delay]))
    pinger = FakePinger()
    ping = multiping.Ping(pinger, 42, 'localhost')
    ping.run()
    assert pinger.results[42] == char


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
    pinger = LimitedPinger('localhost', 1)
    pinger.run()


class FakeCursesWindow:

    def __init__(self, width=80, height=24):
        self._screen = [[' '] * width for _ in range(height)]
        self._row = 0
        self._col = 0
        self._width = width
        self._height = height

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

    def _lines(self):
        return [
            ''.join(row).rstrip() for row in self._screen
        ]

    def _text(self):
        return '\n'.join(self._lines())


@pytest.fixture
def fake_curses(monkeypatch):
    monkeypatch.setattr(curses, 'use_default_colors', lambda: None)
    monkeypatch.setattr(curses, 'init_pair', lambda pair, fg, bg: None)
    monkeypatch.setattr(curses, 'curs_set', lambda visibility: None)
    monkeypatch.setattr(curses, 'color_pair', lambda pair: pair)


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
    ui = multiping.UI(win, 1, 2, 30, 5, pinger, 'example.com')
    ui.draw()
    assert win._text() == '\n'.join([
        '  pinging example.com',
        '  12:30 [   #                          ]',
        '  12:30 [    %                         ]',
        '  12:31 [     -                        ]',
        '  12:31 [      .                       ]',
        '',
    ])


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
