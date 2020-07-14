import argparse
import os
import sys

import image_definition
import registries


def print_instructions_for_tag(
    definition: image_definition.ImageDefinition,
    tag: str,
    destination: str,
    should_push: bool = False,
):
    definition.print_instructions(tag=tag, destination=destination)

    if should_push:
        print(f"Pushing {destination}", file=sys.stderr)
        print(f"docker push {destination}")

    print(f"Done with {destination}", file=sys.stderr)


def run(
    registry: registries.DockerRegistry,
    image_definitions: image_definition.ImageDefinitions,
    should_push=False,
) -> None:
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
            tags_to_do = set(definition.tags) - set(existing_tags)
            if len(tags_to_do) == 0:
                continue

            for tag in tags_to_do:
                print_instructions_for_tag(
                    definition=definition,
                    tag=tag,
                    destination=registry.get_full_image_reference(repository, tag),
                    should_push=should_push,
                )


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

    image_definitions = image_definition.ImageDefinitions.from_json(
        image_definitions_json=sys.stdin.read(),
        repository_prefix=args.repository_prefix,
    )

    if args.target:
        repository, tag = args.target.split(":")
        definition = image_definitions.find_definition(repository, tag)
        print_instructions_for_tag(
            definition=definition, tag=tag, destination=f"{repository}:{tag}"
        )
    else:
        registry = registries.get_registry(
            specification=args.registry,
            username=args.registry_username or os.getenv("REGISTRY_USERNAME"),
            password=os.getenv("REGISTRY_PASSWORD"),
        )

        run(registry, image_definitions, should_push=should_push)
