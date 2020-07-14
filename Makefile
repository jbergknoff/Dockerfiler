python_image = python:3.8.3-slim-buster

container = docker run -i --rm -u $$(id -u):$$(id -g) -v "$$(pwd)":"$$(pwd)" -w "$$(pwd)" $(3) $(1) $(2)
compose = PYTHON_IMAGE=$(python_image) docker-compose -f test/docker-compose.yml $(1)
compose_run = $(call compose, run --rm -u $$(id -u):$$(id -g) -v "$$(pwd)":"$$(pwd)" -w "$$(pwd)" $(3) $(1) $(2))

user_cache_dir := $(HOME)/.cache

format:
	$(call container, dockerizedtools/black:19.10b0, .)

check: check-format check-types check-lint

check-types:
	$(call container, dockerizedtools/mypy:0.782, --ignore-missing-imports dockerfiler)

check-lint:
	$(call container, dockerizedtools/flake8:3.8.3, --max-line-length 120 --ignore E231 dockerfiler)

check-format:
	$(call container, dockerizedtools/black:19.10b0, --check .)

dependencies:
	$(call container, python:3.8.3-slim-buster, pip install --user -r requirements.txt, \
		-e PYTHONUSERBASE=vendor \
		-v "$(user_cache_dir)":"$(user_cache_dir)" -e XDG_CACHE_HOME="$(user_cache_dir)")

test-setup:
	$(call compose, up -d)

.PHONY: test
test:
	$(call compose_run, tests, python -m unittest -v)

test-cleanup:
	-$(call compose, down -t 0)

image:
	docker build -t dockerizedtools/dockerfiler:$(version) .
