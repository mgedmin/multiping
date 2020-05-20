all:
	@echo "Nothing to build."

test check:
	tox -p auto

coverage:
	tox -e coverage

FILE_WITH_VERSION := multiping.py
DISTCHECK_DIFF_OPTS = $(DISTCHECK_DIFF_DEFAULT_OPTS) -x docs
include release.mk
