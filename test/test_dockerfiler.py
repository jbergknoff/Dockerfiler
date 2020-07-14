import contextlib
import io
import json
import secrets
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
    def test_api_integration(self):
        dockerhub_registry = dockerfiler.registries.get_registry(
            specification=None, username="z", password="z",
        )

        artifactory_registry = dockerfiler.registries.get_registry(
            specification="artifactory://fake.jfrog.io", username="z", password="z",
        )

        ecr_registry = dockerfiler.registries.get_registry(
            specification="ecr://123123123123.dkr.ecr.us-east-1.amazonaws.com",
        )

        image_definitions = dockerfiler.image_definition.ImageDefinitions.from_json(
            image_definitions_json=json.dumps(
                {
                    "myuser/project1": [
                        {
                            "type": "build",
                            "dockerfile_path": "Dockerfile1",
                            "tags": {
                                "old1.1": None,
                                "new1.2": {"FOO_VERSION": "x.y.z",},
                            },
                        }
                    ],
                    "myuser/project2": [
                        {
                            "type": "build",
                            "dockerfile_path": "Dockerfile2",
                            "build_context": "./project2-context",
                            "tags": {"old2.1": None, "new2.2": None,},
                        }
                    ],
                    "myuser/project3": [
                        {
                            "type": "mirror",
                            "source_reference": "somewhere/else",
                            "tags": {
                                "old3.1": None,
                                "old3.2": None,
                                "old3.3": None,
                                "new3.4": None,
                            },
                        },
                        {
                            "type": "build",
                            "dockerfile_path": "Dockerfile3",
                            "tags": {"new3.5": None,},
                        },
                    ],
                }
            ),
        )

        test_cases = [
            {
                "description": "interacts properly with Docker Hub",
                "registry": dockerhub_registry,
                "expected": [
                    'docker build -t myuser/project1:new1.2 -f Dockerfile1 --build-arg TAG="new1.2" --build-arg FOO_VERSION="x.y.z" .',
                    'docker build -t myuser/project2:new2.2 -f Dockerfile2 --build-arg TAG="new2.2" ./project2-context',
                    "docker pull somewhere/else:new3.4",
                    "docker tag somewhere/else:new3.4 myuser/project3:new3.4",
                    'docker build -t myuser/project3:new3.5 -f Dockerfile3 --build-arg TAG="new3.5" .',
                ],
            },
            {
                "description": "interacts properly with Artifactory",
                "registry": artifactory_registry,
                "expected": [
                    'docker build -t fake.jfrog.io/myuser/project1:new1.2 -f Dockerfile1 --build-arg TAG="new1.2" --build-arg FOO_VERSION="x.y.z" .',
                    'docker build -t fake.jfrog.io/myuser/project2:new2.2 -f Dockerfile2 --build-arg TAG="new2.2" ./project2-context',
                    "docker pull somewhere/else:new3.4",
                    "docker tag somewhere/else:new3.4 fake.jfrog.io/myuser/project3:new3.4",
                    'docker build -t fake.jfrog.io/myuser/project3:new3.5 -f Dockerfile3 --build-arg TAG="new3.5" .',
                ],
            },
            {
                "description": "interacts properly with ECR",
                "registry": ecr_registry,
                "expected": [
                    'docker build -t 123123123123.dkr.ecr.us-east-1.amazonaws.com/myuser/project1:new1.2 -f Dockerfile1 --build-arg TAG="new1.2" --build-arg FOO_VERSION="x.y.z" .',
                    'docker build -t 123123123123.dkr.ecr.us-east-1.amazonaws.com/myuser/project2:new2.2 -f Dockerfile2 --build-arg TAG="new2.2" ./project2-context',
                    "docker pull somewhere/else:new3.4",
                    "docker tag somewhere/else:new3.4 123123123123.dkr.ecr.us-east-1.amazonaws.com/myuser/project3:new3.4",
                    'docker build -t 123123123123.dkr.ecr.us-east-1.amazonaws.com/myuser/project3:new3.5 -f Dockerfile3 --build-arg TAG="new3.5" .',
                ],
            },
        ]

        for test_case in test_cases:
            with self.subTest(test_case["description"]):
                with captured_output() as (stdout, stderr):
                    dockerfiler.main.run(
                        test_case["registry"], image_definitions,
                    )

                output_lines = [
                    x for x in stdout.getvalue().split("\n") if x.startswith("docker ")
                ]
                self.assertEqual(output_lines, test_case["expected"])

    def test_should_push(self):
        dockerhub_registry = dockerfiler.registries.get_registry(
            specification=None, username="z", password="z",
        )

        image_definitions = dockerfiler.image_definition.ImageDefinitions.from_json(
            image_definitions_json=json.dumps(
                {
                    "myuser/project1": [
                        {
                            "type": "build",
                            "dockerfile_path": "Dockerfile1",
                            "tags": {
                                "old1.1": None,
                                "new1.2": {"FOO_VERSION": "x.y.z",},
                            },
                        }
                    ],
                }
            ),
        )

        expected = [
            'docker build -t myuser/project1:new1.2 -f Dockerfile1 --build-arg TAG="new1.2" --build-arg FOO_VERSION="x.y.z" .',
            "docker push myuser/project1:new1.2",
        ]

        with captured_output() as (stdout, stderr):
            dockerfiler.main.run(
                dockerhub_registry, image_definitions, should_push=True,
            )

        output_lines = [
            x for x in stdout.getvalue().split("\n") if x.startswith("docker ")
        ]
        self.assertEqual(output_lines, expected)

    def test_repository_prefix(self):
        dockerhub_registry = dockerfiler.registries.get_registry(
            specification=None, username="z", password="z",
        )

        image_definitions = dockerfiler.image_definition.ImageDefinitions.from_json(
            image_definitions_json=json.dumps(
                {
                    "project1": [
                        {
                            "type": "build",
                            "dockerfile_path": "Dockerfile1",
                            "tags": {
                                "old1.1": None,
                                "new1.2": {"FOO_VERSION": "x.y.z",},
                            },
                        }
                    ],
                }
            ),
            repository_prefix="myuser/",
        )

        expected = [
            'docker build -t myuser/project1:new1.2 -f Dockerfile1 --build-arg TAG="new1.2" --build-arg FOO_VERSION="x.y.z" .',
        ]

        with captured_output() as (stdout, stderr):
            dockerfiler.main.run(
                dockerhub_registry, image_definitions,
            )

        output_lines = [
            x for x in stdout.getvalue().split("\n") if x.startswith("docker ")
        ]
        self.assertEqual(output_lines, expected)

    def test_create_new_repository(self):
        host = "123123123123.dkr.ecr.us-east-1.amazonaws.com"
        ecr_registry = dockerfiler.registries.get_registry(
            specification=f"ecr://{host}",
        )

        repository_name = secrets.token_hex(8)
        image_definitions = dockerfiler.image_definition.ImageDefinitions.from_json(
            image_definitions_json=json.dumps(
                {
                    repository_name: [
                        {
                            "type": "build",
                            "dockerfile_path": "Dockerfile",
                            "tags": {"new4.1": None,},
                        }
                    ],
                }
            ),
        )

        expected = [
            f'docker build -t {host}/{repository_name}:new4.1 -f Dockerfile --build-arg TAG="new4.1" .',
        ]

        with captured_output() as (stdout, stderr):
            dockerfiler.main.run(
                ecr_registry, image_definitions,
            )

        assert f"Created repositories ['{host}/{repository_name}']" in stderr.getvalue()

        output_lines = [
            x for x in stdout.getvalue().split("\n") if x.startswith("docker ")
        ]
        self.assertEqual(output_lines, expected)

    def test_invalid_input(self):
        """
        There's no need to exhaustively specify the schema here (we can rely on the tests
        of the `schema` librar). This just verifies that we crash early when the input doesn't
        follow the schema.
        """

        invalid_inputs = [
            [],
            {"repo": {"type": "build", "dockerfile_path": "a",}},
        ]

        for invalid_input in invalid_inputs:
            with self.subTest():
                exception = None
                try:
                    dockerfiler.image_definition.ImageDefinitions.from_json(
                        image_definitions_json=json.dumps(invalid_input)
                    )
                except Exception as e:
                    exception = e

                assert exception is not None

    def test_authorization_failure(self):
        with self.subTest("missing credentials"):
            exception = None
            try:
                dockerfiler.registries.get_registry(specification=None, username="z")
            except Exception as e:
                exception = e

            assert exception is not None

        with self.subTest("invalid credentials"):
            exception = None
            try:
                dockerfiler.registries.get_registry(
                    specification=None, username="auth", password="failure",
                )
            except Exception as e:
                exception = e

            assert exception is not None
            assert "Failed to get access token from Docker Hub" in str(exception)

    def test_missing_repository(self):
        """
        For registries that don't require explicit creation of repositories, verify
        that we don't error out when trying to list tags on a missing repository.
        """

        dockerhub_registry = dockerfiler.registries.get_registry(
            specification=None, username="z", password="z",
        )

        image_definitions = dockerfiler.image_definition.ImageDefinitions.from_json(
            image_definitions_json=json.dumps(
                {
                    "myuser/newproject": [
                        {
                            "type": "build",
                            "dockerfile_path": "Dockerfile",
                            "tags": {"tag": None,},
                        }
                    ],
                }
            ),
        )

        expected = [
            'docker build -t myuser/newproject:tag -f Dockerfile --build-arg TAG="tag" .',
        ]

        with captured_output() as (stdout, stderr):
            dockerfiler.main.run(
                dockerhub_registry, image_definitions,
            )

        output_lines = [
            x for x in stdout.getvalue().split("\n") if x.startswith("docker ")
        ]
        self.assertEqual(output_lines, expected)


# TODO things to test
# error handling (e.g. failure to create repository, failure to list tags). Might make more sense as unit tests
