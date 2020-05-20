all:
	@echo "Nothing to build."

test check:
	tox -p auto

coverage:
	tox -e coverage

FILE_WITH_VERSION := multiping.py
include release.mk
