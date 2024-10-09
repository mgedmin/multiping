Changelog
==========

1.4.0 (2024-10-09)
------------------

- Add support for Python 3.9, 3.10, 3.11, and 3.12.
- Drop support for Python 3.6.
- Experimental Windows support (but not for --bluetooth).


1.3.0 (2020-10-12)
------------------

- Add support for --bluetooth pinging (via l2ping; requires root).
- Drop support for Python 3.5 and Python 2.7.


1.2.0 (2020-05-20)
------------------

- Moved to https://github.com/mgedmin/multiping.
- Added a setup.py, a changelog, and a bunch of other files.
- First release to PyPI.


1.1.1 (2019-09-27)
------------------

- Fix crash on terminal resize, when the terminal becomes too small.


1.1.0 (2019-09-16)
------------------

- Better time management, should prevent random gaps.
- Show fractional packet loss numbers.
- Suppress traceback on Ctrl+C.


1.0.0 (2019-08-01)
------------------

- Ported to Python 3.
- Now available from https://github.com/mgedmin/scripts/blob/master/multiping.py


0.9.4 (2015-04-02)
------------------

- First version published as a Gist at
  https://gist.github.com/mgedmin/b65af068e0d239fe9c66
