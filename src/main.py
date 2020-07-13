import argparse
import os
import json
import sys
import urllib.parse
from typing import Dict
from typing import Optional

import registries


def print_instructions_for_tag(
    definition: Dict,
    repository: str,
    tag: str,
    destination: str,
    should_push: bool = False,
):
    if definition["type"] == "mirror":
        source = f"""{definition['source_image']}:{tag}"""
        print(f"Pulling {source}", file=sys.stderr)
        print(f"docker pull {source}")
        print(f"docker tag {source} {destination}")
    elif definition["type"] == "build":
        dockerfile_path = definition["dockerfile_path"]
        build_context = definition.get("build_context") or "."
        build_args = {"TAG": tag, **(definition["tags"][tag] or {})}
        build_args_string = " ".join(
            [f'--build-arg {k}="{v}"' for k, v in build_args.items()]
        )
        print(f"Building {destination} from {dockerfile_path}", file=sys.stderr)
        print(
            f"docker build -t {destination} -f {dockerfile_path} {build_args_string} {build_context}"
        )

    if should_push:
        print(f"Pushing {destination}", file=sys.stderr)
        print(f"docker push {destination}")

    print(f"Done with {destination}", file=sys.stderr)


def run(
    registry: registries.DockerRegistry, image_definitions: Dict, should_push=False
):
    created_repositories = registry.create_repositories_if_necessary(
        list(image_definitions.keys())
    )
    if created_repositories is not None and len(created_repositories) > 0:
        print(f"Created repositories {created_repositories}", file=sys.stderr)

    # Fail immediately if any build or push fails. This script's output typically gets piped to bash.
    print("set -e")

    print(
        "Inspecting existing images to know what needs to be built...", file=sys.stderr
    )
    for repository, definition_list in image_definitions.items():
        existing_tags = registry.list_tags_on_repository(repository)

        for definition in definition_list:
            tags_to_do = set(definition["tags"]) - set(existing_tags)
            if len(tags_to_do) == 0:
                continue

            for tag in tags_to_do:
                print_instructions_for_tag(
                    definition,
                    repository,
                    tag,
                    destination=registry.get_full_image_reference(repository, tag),
                    should_push=should_push,
                )


def find_definition(image_definitions, repository, tag):
    for definition in image_definitions[repository]:
        if tag in definition["tags"]:
            return definition

    raise Exception(f"""Couldn't find definition for {repository}:{tag}""")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target", help="Only build a specific image:tag. Useful for experimentation."
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="If present, push to registries. Otherwise, just build",
    )
    parser.add_argument(
        "--registry",
        help="Registry specification. Omit or `dockerhub` for Docker Hub. "
        "Otherwise, `artifactory://<host>` or `ecr://<host>`",
    )
    parser.add_argument(
        "--registry-username",
        help="Registry username, if required (can alternately be specified with "
        "REGISTRY_USERNAME environment variable)",
    )
    parser.add_argument(
        "--repository-prefix",
        help="Prefix to put on all repository names, e.g. `dockerhubusername/`",
    )
    args = parser.parse_args()
    should_push = args.push
    target = args.target

    image_definitions = json.loads(sys.stdin.read())
    if args.target:
        repository, tag = args.target.split(":")
        definition = find_definition(image_definitions, repository, tag)
        print_instructions_for_tag(
            definition, repository, tag, destination=f"{repository}:{tag}"
        )
    else:
        registry: Optional[registries.DockerRegistry] = None
        username = args.registry_username or os.getenv("REGISTRY_USERNAME")
        password = os.getenv("REGISTRY_PASSWORD")
        if args.registry is None or args.registry == "dockerhub":
            if username is None or password is None:
                raise Exception(
                    "Docker Hub requires username and password for querying the registry API. "
                    "Use --registry-username (or REGISTRY_USERNAME) and REGISTRY_PASSWORD"
                )

            registry = registries.DockerHubRegistry(
                username=username, password=password,
            )
        else:
            parsed = urllib.parse.urlparse(args.registry)
            if parsed.scheme == "artifactory":
                if username is None or password is None:
                    raise Exception(
                        "Artifactory requires username and password for querying the registry API"
                    )

                registry = registries.ArtifactoryRegistry(
                    host=parsed.netloc, username=username, password=password,
                )
            elif parsed.scheme == "ecr":
                registry = registries.ECRRegistry(host=parsed.netloc,)
            else:
                raise Exception(f"Unexpected registry specification: {args.registry}")

        if registry is None:
            raise Exception("No registry specified")

        if args.repository_prefix:
            image_definitions = {
                f"{args.repository_prefix}{k}": v for k, v in image_definitions.items()
            }

        run(registry, image_definitions, should_push=should_push)
