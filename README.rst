multiping
=========

.. image:: https://github.com/mgedmin/multiping/workflows/build/badge.svg?branch=master
    :target: https://github.com/mgedmin/multiping/actions

.. image:: https://coveralls.io/repos/mgedmin/multiping/badge.svg?branch=master
    :target: https://coveralls.io/r/mgedmin/multiping

Pings a host once every second and displays the results in an interactive
ncurses window.

.. image:: https://raw.githubusercontent.com/mgedmin/multiping/master/docs/screenshot.png


Usage: multiping *hostname*

Display:

- ``#``  ping OK
- ``%``  ping OK, response is slow (over 1000 ms)
- ``-``  ping not OK
- ``!``  ping process killed (after 20 seconds)
- ``?``  cannot execute ping

Keys:

- **q**                     - quit
- **k**, **Up**             - scroll up
- **j**, **Down**           - scroll down
- **Ctrl+U**, **Page Up**   - scroll page up
- **Ctrl+D**, **Page Down** - scroll page down
- **g**, **Home**           - scroll to top
- **G**, **End**            - scroll to bottom
- **Ctrl+L**                - redraw
