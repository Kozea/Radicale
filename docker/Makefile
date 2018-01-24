.DEFAULT_GOAL = build

REPO_NAME = kozea/radicale
VERSION = $(shell grep "VERSION = " ../setup.py | cut -d"=" -f2 | tr -d ' "')
export IMAGE_NAME = $(REPO_NAME):$(VERSION)
export GIT_SHA1 = $(shell git rev-parse HEAD)


.PHONY: build
build:
	hooks/build

.PHONY: test-invokation
test-invokation: build
	docker run --rm -i $(IMAGE_NAME) --debug
