#!/usr/bin/python3
"""
Multiping by Marius Gedminas <marius@gedmin.as>
License: GPL v2 or later

Usage: multiping hostname
       sudo multiping --bluetooh bt_mac_addr

Pings a host every second and displays the results in an ncurses window.

legend:
  #  ping OK
  %  ping OK, response is slow (over 1000 ms)
  -  ping not OK
  !  ping process killed (after 20 seconds)
  ?  cannot execute ping

keys:
  q                quit
  k, up            scroll up
  j, down          scroll down
  ^U, page up      scroll page up
  ^D, page down    scroll page down
  g, home          scroll to top
  G, end           scroll to bottom
  ^L               redraw
"""

import argparse
import curses
import os
import signal
import subprocess
from threading import Thread
from time import localtime, sleep, strftime, time


__version__ = '1.3.0'
__author__ = 'Marius Gedminas <marius@gedmin.as>'
__url__ = 'https://github.com/mgedmin/scripts/blob/master/multiping.py'
__licence__ = 'GPL v2 or later'


# max number of outstanding ping subprocesses
# so we won't fill up the OS pid table or something
# (guess what event made me add this limitation? ;)
QUEUE_LEN = 20

# how many seconds for a ping to be considered slow?
SLOW_PING = 1.0


class Ping(Thread):

    command = ['ping', '-c', '1', '-n', '-q']

    def __init__(self, pinger, idx, hostname):
        Thread.__init__(self)
        self.setDaemon(True)
        self.pinger = pinger
        self.idx = idx
        self.hostname = hostname
        self.pid = None
        self.success = False

    def run(self):
        start = time()
        try:
            p = subprocess.Popen(self.command + [self.hostname],
                                 stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        except OSError:
            result = '?'
        else:
            self.pid = p.pid
            status = p.wait()
            self.pid = None
            delay = time() - start
            if status < 0:  # killed by a signal
                result = '!'
            elif status == 0:
                self.success = True
                if delay > SLOW_PING:
                    result = '%'
                else:
                    result = '#'
            else:
                result = '-'
        self.pinger.set(self.idx, result)

    def timeout(self, hard=False):
        if self.pid:
            # Note that self.pid may be set to None after the check above
            try:
                os.kill(self.pid, signal.SIGKILL if hard else signal.SIGTERM)
            except (OSError, TypeError):
                pass


class BluetoothPing(Ping):

    command = ['l2ping', '-c', '1', '-t', '10']


class Pinger(Thread):

    def __init__(self, hostname, interval, factory=Ping):
        Thread.__init__(self)
        self.setDaemon(True)
        self.factory = factory
        self.hostname = hostname
        self.interval = interval
        self.status = []
        self.version = 0
        self.running = True
        self.started = -1
        self.sent = 0
        self.received = 0

    def run(self):
        self.started = last_time = time()
        idx = 0
        queue = []
        last_one = None
        while self.running:
            self.set(idx, '.')
            p = self.factory(self, idx, self.hostname)
            queue.append(p)
            p.start()
            if len(queue) >= QUEUE_LEN:
                if last_one:
                    last_one.timeout(True)
                    self.sent += 1
                    if last_one.success:
                        self.received += 1
                last_one = queue.pop(0)
                last_one.timeout()
            next_time = self.started + (idx + 1) * self.interval
            to_sleep = next_time - time()
            if to_sleep > 0:
                sleep(to_sleep)
            last_time = time()
            idx = max(idx + 1, int((last_time - self.started) / self.interval))

    def set(self, idx, result):
        while idx >= len(self.status):
            self.status.append(' ')
        self.status[idx] = result
        self.version += 1

    def quit(self):
        self.running = False


class UI:

    def __init__(self, win, y, x, width, height, pinger, hostname):
        self.win = win
        self.y = y
        self.x = x
        self.width = width
        self.height = height
        self.pinger = pinger
        self.version = -1
        self.hostname = hostname
        self.autoscrolling = True
        self.title = "pinging %s" % hostname

        self.row = 0

        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_RED, -1)
        curses.init_pair(2, curses.COLOR_GREEN, -1)
        self.RED = curses.color_pair(1) | curses.A_BOLD
        self.GREEN = curses.color_pair(2) | curses.A_BOLD
        self.DGREEN = curses.color_pair(2)
        curses.curs_set(0)

    def _draw(self):
        win = self.win
        y = self.y
        x = self.x
        width = self.width
        height = self.height
        status = self.pinger.status
        interval = self.pinger.interval
        this_is_an_update = self.version != self.pinger.version
        self.version = self.pinger.version

        if self.pinger.sent > 0:
            loss = 100 - 100.0 * self.pinger.received / self.pinger.sent
        else:
            loss = 0
        if loss > 0:
            win.addstr(y-1, x, "%s: packet loss %.1f%%"
                               % (self.title, loss))
        else:
            win.addstr(y-1, x, self.title)
        win.clrtoeol()

        if self.autoscroll() and this_is_an_update:
            self._scroll_to_bottom()
        pos = self.row * width
        if self.pinger.started != -1:
            pos -= int(self.pinger.started) % 60
        t = self.pinger.started + pos * interval
        while pos < len(status) and height > 0:
            win.addstr(y, x, strftime("%H:%M [", localtime(t)))
            for i in range(width):
                attr = curses.A_NORMAL
                if 0 <= pos < len(status):
                    ch = status[pos]
                    if ch in ('-', '?', '!'):
                        attr = self.RED
                    elif ch == '#':
                        attr = self.GREEN
                    elif ch == '%':
                        attr = self.DGREEN
                else:
                    ch = " "
                # NB: win.addch(ch, attr) ignores attr if ch is a unicode
                # string of length 1 -- things work fine if it's a bytestring
                win.addstr(ch, attr)
                pos += 1
            win.addstr("]")
            y += 1
            t += width * interval
            height -= 1
        if height > 0:
            win.move(y, x)
            win.clrtobot()

    def draw(self):
        try:
            self._draw()
        except curses.error:
            # let's hope it's just a momentary glitch due to a temporarily
            # reduced window size or something
            pass

    def last_row_visible(self):
        max_pos = len(self.pinger.status)
        if self.pinger.started != -1:
            max_pos += int(self.pinger.started) % 60
        pos_just_past_the_screen = (self.row + self.height) * self.width
        return (pos_just_past_the_screen - self.width <= max_pos
                < pos_just_past_the_screen)

    def autoscroll(self):
        if not self.autoscrolling:
            return False
        # autoscroll only if the bottom row was visible and is no longer
        pos_just_past_the_screen = (self.row + self.height) * self.width
        max_pos = len(self.pinger.status)
        if self.pinger.started != -1:
            max_pos += int(self.pinger.started) % 60
        return pos_just_past_the_screen <= max_pos - 1

    def update(self):
        if self.version != self.pinger.version:
            self.draw()
            return True
        else:
            return False

    def scroll(self, delta):
        self.row += delta
        self.row = max(self.row, 1 - self.height)

        max_pos = len(self.pinger.status)
        if self.pinger.started != -1:
            max_pos += int(self.pinger.started) % 60
        self.row = min(self.row, int((max_pos - 1) / self.width))
        self.autoscrolling = self.last_row_visible()
        self.draw()

    def scroll_to_top(self):
        self.row = 0
        self.autoscrolling = self.last_row_visible()
        self.draw()

    def _scroll_to_bottom(self):
        max_pos = len(self.pinger.status)
        if self.pinger.started != -1:
            max_pos += int(self.pinger.started) % 60
        self.row = max(0, int((max_pos - 1) / self.width) - self.height + 1)

    def scroll_to_bottom(self):
        self._scroll_to_bottom()
        self.autoscrolling = True
        self.draw()

    def resize(self, new_height):
        self.height = new_height
        if self.autoscrolling:
            self._scroll_to_bottom()
        self.scroll(0)


CTRL_D = ord('D') - ord('@')
CTRL_L = ord('L') - ord('@')
CTRL_U = ord('U') - ord('@')


def _main(stdscr, hostname, *, interval=1, bluetooth=False):
    title = "pinging {}{}".format(
        hostname, " over bluetooth" if bluetooth else "")
    stdscr.addstr(0, 0, title)
    pinger = Pinger(
        hostname, interval, factory=BluetoothPing if bluetooth else Ping)
    pinger.start()
    ui = UI(stdscr, 1, 0, 60, curses.LINES - 1, pinger, hostname)
    ui.title = title
    ui.draw()
    stdscr.refresh()
    curses.halfdelay(interval * 5)
    while 1:
        c = stdscr.getch()
        if ui.update():
            stdscr.refresh()
        if c == ord('q'):
            pinger.quit()
            return
        elif c == curses.KEY_RESIZE:
            ui.resize(stdscr.getmaxyx()[0] - 1)
            stdscr.refresh()
        elif c == CTRL_L:  # ^L
            stdscr.clear()
            ui.draw()
            stdscr.refresh()
        elif c in (ord('k'), curses.KEY_UP):
            ui.scroll(-1)
            stdscr.refresh()
        elif c in (ord('j'), curses.KEY_DOWN):
            ui.scroll(1)
            stdscr.refresh()
        elif c in (CTRL_U, curses.KEY_PPAGE):
            ui.scroll(1 - ui.height)
            stdscr.refresh()
        elif c in (CTRL_D, curses.KEY_NPAGE):
            ui.scroll(ui.height - 1)
            stdscr.refresh()
        elif c in (ord('g'), curses.KEY_HOME):
            ui.scroll_to_top()
            stdscr.refresh()
        elif c in (ord('G'), curses.KEY_END):
            ui.scroll_to_bottom()
            stdscr.refresh()
        elif c == ord('f'):     # fake ping response for debugging
            pinger.status.append('F')
            ui.draw()
            stdscr.refresh()
        elif c == ord('F'):     # fake ping response for debugging
            pinger.status.extend(['F'] * 60 * 10)
            ui.draw()
            stdscr.refresh()


def main():
    parser = argparse.ArgumentParser(
        description="ping a host every second"
        " and display the results in an ncurses window",
        epilog=__doc__[__doc__.index('legend:'):],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version",
        version="%(prog)s version " + __version__)
    parser.add_argument(
        '--bluetooth', action="store_true",
        help='ping a Bluetooth MAC address (needs root)')
    parser.add_argument(
        'hostname',
        help='hostname or IP address to ping')
    args = parser.parse_args()
    try:
        curses.wrapper(_main, args.hostname, bluetooth=args.bluetooth)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
