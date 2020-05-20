all:
	@echo "Nothing to build."

test check:
	tox -p auto

FILE_WITH_VERSION := multiping.py
include release.mk
