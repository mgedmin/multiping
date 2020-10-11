.PHONY: all
all:
	@echo "Nothing to build."

.PHONY: test
test:                   ##: run tests
	tox -p auto

.PHONY: coverage
coverage:               ##: measure test coverage
	tox -e coverage


FILE_WITH_VERSION := multiping.py
DISTCHECK_DIFF_OPTS = $(DISTCHECK_DIFF_DEFAULT_OPTS) -x docs
include release.mk
