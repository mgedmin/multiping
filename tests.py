import curses
import os
import sys
import time

import mock
import pytest

import multiping


class FakePinger:
    def __init__(self):
        self.results = {}

    def set(self, idx, result):
        self.results[idx] = result


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
