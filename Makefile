run_container = docker run -i --rm -u $$(id -u):$$(id -g) -v "$$(pwd)":"$$(pwd)" -w "$$(pwd)" $(3) $(1) $(2)

user_cache_dir := $(HOME)/.cache

format:
	$(call run_container, dockerizedtools/black:19.10b0, .)

check: check-format check-types check-lint

check-types:
	$(call run_container, dockerizedtools/mypy:0.782, --ignore-missing-imports src)

check-lint:
	$(call run_container, dockerizedtools/flake8:3.8.3, --max-line-length 120 --ignore E231 src)

check-format:
	$(call run_container, dockerizedtools/black:19.10b0, --check .)

vendor:
	$(call run_container, python:3.8.3-slim-buster, pip install --user -r requirements.txt, \
		-e PYTHONUSERBASE=vendor \
		-v "$(user_cache_dir)":"$(user_cache_dir)" -e XDG_CACHE_HOME="$(user_cache_dir)")

.PHONY: test
test:
	echo TODO

image:
	echo TODO
