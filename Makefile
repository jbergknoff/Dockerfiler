run_container = docker run -i --rm -u $$(id -u):$$(id -g) -v "$$(pwd)":"$$(pwd)" -w "$$(pwd)" $(3) $(1) $(2)

user_cache_dir := $(HOME)/.cache

format:
	$(call run_container, dockerizedtools/black:19.10b0, .)

lint:
	$(call run_container, dockerizedtools/mypy:0.782, --ignore-missing-imports src)
	echo flake8 TODO

vendor:
	$(call run_container, python:3.8.3-slim-buster, pip install --user -r requirements.txt, \
		-e PYTHONUSERBASE=vendor \
		-v "$(user_cache_dir)":"$(user_cache_dir)" -e XDG_CACHE_HOME="$(user_cache_dir)")

.PHONY: test
test:
	echo TODO

image:
	echo TODO
