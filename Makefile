run_container = docker run -i --rm -v "$$(pwd)":"$$(pwd)" -w "$$(pwd)" $(3) $(1) $(2)

format:
	$(call run_container, dockerizedtools/black:19.10b0, .)

lint:
	echo TODO

.PHONY: test
test:
	echo TODO

image:
	echo TODO
