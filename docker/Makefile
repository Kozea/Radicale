.DEFAULT_GOAL := build

IMAGE_NAME = kozea/radicale


.PHONY: build
build:
	docker build -t $(IMAGE_NAME) ..

.PHONY: test-invokation
test-invokation: build
	docker run --rm -i $(IMAGE_NAME) --debug
