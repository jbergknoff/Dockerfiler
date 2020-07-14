import contextlib
import io
import json
import sys
import unittest

import dockerfiler.main
import dockerfiler.image_definition
import dockerfiler.registries

# Context manager for capturing stdout
# cf. https://stackoverflow.com/a/17981937/349427
@contextlib.contextmanager
def captured_output():
    new_out, new_err = io.StringIO(), io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = new_out, new_err
        yield sys.stdout, sys.stderr
    finally:
        sys.stdout, sys.stderr = old_out, old_err


class TestDockerfiler(unittest.TestCase):
	def test_something(self):
		registry = dockerfiler.registries.get_registry(
			specification=None,
			username='z',
			password='z',
		)

		image_definitions = dockerfiler.image_definition.ImageDefinitions.from_json(
			image_definitions_json=json.dumps(
				{
					"myuser/project1": [{
						"type": "build",
						"dockerfile_path": "anywhere",
						"tags": {
							"thing": None,
						}
					}],
					"myuser/project2": [{
						"type": "build",
						"dockerfile_path": "anywhere",
						"tags": {
							"thing": None,
						}
					}],
					"myuser/project3": [{
						"type": "build",
						"dockerfile_path": "anywhere",
						"tags": {
							"thing": None,
						}
					}],
				}
			),
        	repository_prefix=None,
		)

		with captured_output() as (stdout, stderr):
			dockerfiler.main.run(registry, image_definitions, should_push=False)

		print(stdout.getvalue())
