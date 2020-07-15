# Self-signed certificate

This self-signed TLS certificate exists so that Dockerfiler's mock server can accept TLS connections, pretending to be Docker Hub, ECR, etc.

* The mock server runs in a Docker container with "network aliases" of, e.g. `hub.docker.com`. When other containers in that same Docker network try to contact that host, the traffic is routed to the mock server instead of the real Docker Hub.
* The tests run in a container with `REQUESTS_CA_BUNDLE` set so that it will accept this sketchy-looking cert.
* The code under test is not modified to use a special endpoint or ignore certificate errors.

The certificate was generated with

```
$ make self-signed-cert
```
