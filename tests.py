import curses
import sys

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
