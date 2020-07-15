# Dockerfiler

Dockerfiler is a tool for declaratively managing a set of images built from Dockerfiles.

This isn't for managing images built from your own projects, which will typically have their own processes for building and deploying artifacts. Instead, this is for those tools that you use in development or in CI which can benefit from Docker as a distribution mechanism. Docker is an [excellent means of distributing those sorts of tools](https://jonathan.bergknoff.com/journal/run-more-stuff-in-docker/). Dockerfiler helps you maintain a library (public or private) of images that you control.

Note that Dockerfiler never destroys data. It never deletes repositories/images/tags (even if they're present in the registry but missing from the manifest passed in). It does not modify image contents if a tag is already present in the registry; it doesn't check content at all, just presence of the tag, and leaves anything alone if it's already there. Dockerfiler will only append to the registry.

Supported registries: Docker Hub, Artifactory, ECR.

## Example

Dockerfiler takes your image manifest on stdin and prints a sequence of `docker` commands to stdout.

Suppose we give this **manifest.json** as input to Dockerfiler on stdin:

```json
{
  "myuser/openssl": [
    {
      "type": "build",
      "dockerfile_path": "openssl.Dockerfile",
      "tags": {
        "1.1.1g": {
          "PACKAGE_VERSION": "1.1.1g-r0"
        }
      }
    }
  ],
  "myuser/terraform": [
    {
      "type": "mirror",
      "source_reference": "hashicorp/terraform",
      "tags": {
        "0.12.27": null,
        "0.12.28": null
      }
    }
  ]
}
```

and suppose that `myuser/terraform:0.12.27` already exists in our registry, but `myuser/openssl:1.1.1g` and `myuser/terraform:0.12.28` don't. We invoke Dockerfiler:

```sh
$ docker run -i --rm dockerizedtools/dockerfiler --push < manifest.json
set -ex
docker build -t myuser/openssl:1.1.1g --build-arg TAG="1.1.1g" --build-arg PACKAGE_VERSION="1.1.1g-r0" -f openssl.Dockerfile .
docker push myuser/openssl:1.1.1g
docker pull hashicorp/terraform:0.12.28
docker tag hashicorp/terraform:0.12.28 myuser/terraform:0.12.28
docker push myuser/terraform:0.12.28
```

The `myuser/terraform:0.12.27` tag already in the registry is left alone. Only the new tags get built and pushed.

This output is a list of commands which is not executed. Think of it as a dry run. If we actually want to execute these steps, we would pipe that output to a shell where we have credentials to do the `docker push`.

## Usage

Dockerfiler should be invoked as a Docker image:

```sh
$ alias dockerfiler='docker run -i --rm ... dockerizedtools/dockerfiler'
$ dockerfiler --registry-username myuser | bash
```

Docker Hub, Artifactory and ECR are supported as registries. Dockerfiler's interaction with the registries is limited to

* Read-only access to list repositories and tags
* For registries where repositories aren't lazily created upon push (ECR), also creates repositories as needed

Note that Dockerfiler doesn't build or push images itself. It outputs a list of `docker` commands which can be piped to a shell to be executed in an environment with `docker push` access.

TODO: example usage in a Dockerfile repo, explaining how to use Dockerfiler in CI.

#### Command line arguments

* `--registry [specification]`: what Docker registry to point at.
  * Docker Hub: omit this or specify `dockerhub`
  * Artifactory: `artifactory://<host>` (e.g. `--registry artifactory://yourdomain.jfrog.io`)
  * ECR: `ecr://<host>` (e.g. `--registry ecr://0123456789012.dkr.ecr.us-east-1.amazonaws.com`)

    Only one registry is supported at a time. To push to multiple registries, call Dockerfiler more than once with different registry specifications.

* `--registry-username [username]`: username for the registry, if applicable.
  * ECR doesn't require a username, but AWS credentials must be provided instead. Usually, this will be via environment variables `AWS_ACCESS_KEY_ID`/etc. or `AWS_PROFILE`. Please be aware that these will need to be made available in the container running Dockerfiler. That may look like:

    ```sh
    $ docker run -i --rm -v ~/.aws:/.aws -u $(id -u):$(id -g) -e AWS_PROFILE dockerizedtools/dockerfiler ...
    ```
  * This can alternately be supplied as an environment variable `REGISTRY_USERNAME`.

* `--registry-password [password]`: password for the registry user, if applicable.
  * ECR: See comments on `--registry-username`, above.
  * This can alternately be supplied as an environment variable `REGISTRY_PASSWORD`.

* `--push`: if supplied, Dockerfiler will output `docker push` commands. By default, this is off, which is useful for validating which images will be built (and/or that they build successfully).

* `--repository-prefix [prefix]`: optional prefix to put on all repository names.
  * If the manifest JSON lists a repository like `project1` and `--repository-prefix myuser/` is passed, then Dockerfiler will operate on the repository `myuser/project1`. This can be useful for using the same manifest in multiple registries.

* `--target [repository:tag]`: process just the image/tag specified. This is only for development use, validating that a given image can build successfully. There is no interaction with the registry, so no credentials are required.

#### Manifest format

The image manifest passed in on stdin is a JSON map with repository names as keys, and a list of image definitions as values. The image definitions can be either "mirror" image definitions, mirroring tags of an image published elsewhere, or "build" image definitions which get built from a Dockerfile that you supply.

Here's a full example:

```
{
  "myuser/tool1": [
    {
      "type": "build",
      "dockerfile_path": "tool1.Dockerfile",
      "build_context": "tool1context",
      "tags": {
        "v1": null,
        "v2": {
          "SOME_ARGUMENT": "1.2.3"
        }
      }
    },
    {
      "type": "mirror",
      "source_reference": "anotheruser/tool1",
      "tags": {
        "v1beta": null
      }
    }
  ],
  ...
}
```

It can be useful to have more than one image definition (i.e. more than one element in the list) when, for instance, you switch from using a publicly available image to building your own, or your normal Dockerfile for the tool installs from a binary, but some situation calls for a different Dockerfile which builds from source.

Each tag listed in the image definition can specify a map of build arguments that will be passed to `docker build`. The tag will always, itself, be passed as a build argument `TAG`. If no other build arguments are necessary, specify `null` as the value for the tag.

The `build_context` parameter for a "build" image definition is optional (defaulting to `.`). This controls the last argument to `docker build`, i.e. which files are provided as context during the `docker build`.

For more detail on the schema of this data, refer to [dockerfiler/image_definition.py](dockerfiler/image_definition.py).

#### Dockerfiles

See the discussion above about specifying build arguments and build context. Here's an example Dockerfile making use of the `TAG` build argument:

```
FROM python:3.8.3-alpine3.12
ARG TAG
RUN pip install flake8==$TAG
ENTRYPOINT ["flake8"]
```

Here's one using build context to add an entrypoint script:

```
FROM alpine:3.12
COPY entrypoint.sh /usr/bin
ENTRYPOINT ["entrypoint.sh"]
```

This would require that your manifest includes a `build_context` pointing at the directory containing `entrypoint.sh`.

If you supply a build argument which should control the base image, note that you must declare `ARG` before `FROM`:

```
ARG ALPINE_VERSION
FROM alpine:$ALPINE_VERSION
RUN ...
```

## FAQ

* **Why does this print `docker` commands instead of building/pushing by itself?** The current implementation is simple in some nice ways: no need to operate on the Docker socket, no need to reinvent the wheel of displaying build/push progress, no need to pass registry credentials with write access, no need to actually have access to your Dockerfiles or build context. It's easy to do a dry run, easy to test the tool (both for development and for actual use). Unix philosophy, separation of concerns, etc. This tool could work in other ways, but there are some benefits to doing it like this.

* **What's the point of `mirror`?** Docker tags are mutable, so it's often useful to simply take somebody else's image and make your own copy that you control. If you're pointing at a public image, you run the risk of the image being removed, or its contents changing over time.

* **Why no delete?** As mentioned at the top, Dockerfiler never deletes images, and it doesn't inspect image contents. The risks/rewards there are not favorable.

* **Will the image's Dockerfile show up on Docker Hub?** Unfortunately, no. You may want to set up a repository description/README linking to the responsible Dockerfile.

* **Why use this instead of Docker Hub's automated builds?** Dockerfiler can be used to automate builds/pushes to private registries, including non-Docker-Hub registries.

## Contributing

Contributions are always appreciated.

#### Development

Development uses `docker`, `docker-compose`, and `make`.

To run tests:

```sh
$ make test-setup
$ make test # iterate here
$ make test-cleanup
```

To format and run code checks:

```sh
$ make format check
```

See the Makefile for more details.

#### CI

CI happens in GitHub Actions:

* Upon any push, code checks and tests run
* Upon release, an artifact is built and pushed to Docker Hub (`dockerizedtools/dockerfiler`)
