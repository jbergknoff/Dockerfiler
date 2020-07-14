import json
import sys
from typing import Dict
from typing import List
from typing import Optional

import schema

tag_schema = {"tag": schema.Or(None, {"build_argument": str,})}

image_definition_schema = schema.Schema(
    schema.And(
        {
            "repository": [
                schema.Or(
                    schema.And(
                        {
                            "type": schema.Literal("build"),
                            "dockerfile_path": str,
                            schema.Optional("build_context"): str,
                            "tags": tag_schema,
                        },
                        schema.Use(
                            lambda x: BuildImageDefinition(
                                dockerfile_path=x.get("dockerfile_path"),
                                build_context=x.get("build_context"),
                                tags=x.get("tags"),
                            )
                        ),
                    ),
                    schema.And(
                        {
                            "type": schema.Literal("mirror"),
                            "source_reference": str,
                            "tags": tag_schema,
                        },
                        schema.Use(
                            lambda x: MirrorImageDefinition(
                                source_reference=x.get("source_reference"),
                                tags=x.get("tags"),
                            )
                        ),
                    ),
                )
            ]
        },
        schema.Use(lambda x: ImageDefinitions(image_definitions=x)),
    )
)


class ImageDefinition:
    def __init__(self, tags: Optional[Dict[str, str]]):
        self.tags = tags

    def print_instructions(self, tag: str, destination: str) -> None:
        pass


class MirrorImageDefinition(ImageDefinition):
    def __init__(self, source_reference: str, tags: Dict[str, str]):
        super().__init__(tags=tags)
        self.source_reference = source_reference

    def print_instructions(self, tag: str, destination: str) -> None:
        source = f"{self.source_reference}:{tag}"
        print(f"Pulling {source}", file=sys.stderr)
        print(f"docker pull {source}")
        print(f"docker tag {source} {destination}")


class BuildImageDefinition(ImageDefinition):
    def __init__(
        self,
        dockerfile_path: str,
        tags: Dict[str, str],
        build_context: Optional[str] = None,
    ):
        super().__init__(tags=tags)
        self.dockerfile_path = dockerfile_path
        self.build_context = build_context or "."

    def print_instructions(self, tag: str, destination: str) -> None:
        build_arguments = {"TAG": tag, **(self.tags or dict())}
        build_arguments_string = " ".join(
            [f'--build-arg {k}="{v}"' for k, v in build_arguments.items()]
        )
        print(f"Building {destination} from {self.dockerfile_path}", file=sys.stderr)
        print(
            f"docker build -t {destination} -f {self.dockerfile_path} {build_arguments_string} {self.build_context}"
        )


class ImageDefinitions(dict):
    def __init__(self, image_definitions: Dict[str, List[ImageDefinition]]):
        self.update(image_definitions)

    @staticmethod
    def from_json(
        image_definitions_json: str, repository_prefix: Optional[str] = None
    ) -> "ImageDefinitions":
        """
        Deserialize JSON into an ImageDefinitions object. This is only complicated in order to do
        schema validation and give helpful error messages.
        """
        try:
            parsed = json.loads(image_definitions_json)
        except Exception as e:
            raise Exception("Failed parsing image definitions as JSON") from e

        image_definitions = image_definition_schema.validate(parsed)
        if repository_prefix:
            image_definitions = ImageDefinitions(
                {f"{repository_prefix}{k}": v for k, v in image_definitions.items()}
            )

        return image_definitions

    def find_definition(self, repository: str, tag: str) -> ImageDefinition:
        for image_definition in self.get(repository) or []:
            if tag in image_definition.tags:
                return image_definition

        raise Exception(f"No definition found for {repository}:{tag}")
