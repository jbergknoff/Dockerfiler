from typing import List

import boto3
import requests


class DockerRegistry:
    host: str = None

    def list_tags_on_repository(self, repository: str) -> List[str]:
        pass

    def create_repositories_if_necessary(self, repository_list: List[str]) -> None:
        pass

    def get_full_image_reference(self, repository: str, tag: str) -> str:
        return f"{self.host}/{repository}:{tag}"


class ArtifactoryRegistry(DockerRegistry):
    host: str = None
    requests_session: requests.Session = None

    def __init__(self, host: str, username: str, password: str):
        self.host = host
        self.requests_session = requests.Session()
        self.requests_session.auth = (username, password)

    def list_tags_on_repository(self, repository: str) -> List[str]:
        response = self.requests_session.get(
            f"https://{self.host}/v2/{repository}/tags/list",
        )

        return response.json().get("tags") or []


class DockerHubRegistry(DockerRegistry):
    """
	Docker Hub API usage following https://success.docker.com/article/how-do-i-authenticate-with-the-v2-api because
	Docker Hub's API does not follow the API specification here: https://docs.docker.com/registry/spec/api/.
	For example, the API spec has `GET /v2/{repository}/tags/list`, but that returns a 404, stating
	that the `list` tag doesn't exist.
	"""

    host: str = None
    requests_session: requests.Session = None

    def __init__(self, username: str, password: str):
        self.host = "hub.docker.com"
        self.requests_session = requests.Session()
        login_response = self.requests_session.post(
            f"https://{self.host}/v2/users/login",
            json={"username": username, "password": password,},
        )

        try:
            login_response.raise_for_status()
            token = login_response.json()["token"]
        except Exception as e:
            raise Exception(
                f"Failed to get access token from Docker Hub (username {username})"
            ) from e

        self.requests_session.headers.update({"authorization": f"JWT {token}"})

    def list_tags_on_repository(self, repository: str) -> List[str]:
        page_number = 1
        tags: List[str] = []
        while page_number is not None:
            response = self.requests_session.get(
                f"https://{self.host}/v2/repositories/{repository}/tags",
                params={"page": page_number, "page_size": 1000,},
            )

            try:
                response.raise_for_status()
                result_data = response.json()
                page_count = int(result_data["count"])
                tags += [x["name"] for x in result_data["results"]]
            except Exception as e:
                raise Exception(
                    f"Failed fetching tags for Docker Hub repository {repository}"
                ) from e

            if page_count == 0 or result_data.get("next") is None:
                page_number = None
            else:
                page_number += 1

        return tags

    def get_full_image_reference(self, repository: str, tag: str) -> str:
        return f"{repository}:{tag}"


class ECRRegistry(DockerRegistry):
    host: str = None
    ecr: botocore.client.ECR = None

    def __init__(self, host: str):
        self.host = host
        self.ecr = boto3.client("ecr")

    def create_repositories_if_necessary(self, repository_list):
        page_generator = self.ecr.get_paginator("describe_repositories").paginate()

        existing_repositories: List[str] = []
        for page in page_generator:
            for repository_details in page.get("repositories", []):
                existing_repositories.append(repository_details["repositoryName"])

        repositories_to_create = list(set(repository_list) - set(existing_repositories))

        created = []
        for repository in repositories_to_create:
            self.ecr.create_repository(repositoryName=repository)
            created.append(repository)

        return created

    def list_tags_on_repository(self, repository: str) -> List[str]:
        page_generator = self.ecr.get_paginator("describe_images").paginate(
            repositoryName=repository, filter={"tagStatus": "TAGGED"}
        )

        tags: List[str] = []
        for page in page_generator:
            for image in page.get("imageDetails", []):
                tags += image.get("imageTags", [])

        return tags
