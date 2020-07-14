import http.server
import json
import os
import re
import ssl
from typing import Dict
from typing import List


class RequestHandler(http.server.BaseHTTPRequestHandler):
    created_repositories: List[str] = []

    def do_GET(self) -> None:
        host = self.headers["host"]
        print(f"Incoming GET request to {host}{self.path}")
        if host == "fake.jfrog.io":
            self.do_artifactory_get()
        elif host == "hub.docker.com":
            self.do_dockerhub_get()
        else:
            self.send_json(404, {"error": f"Invalid request for host {host}"})

    def do_POST(self) -> None:
        host = self.headers["host"]
        data = {}
        content_length = int(self.headers["content-length"] or 0)
        if content_length > 0:
            data = json.loads(self.rfile.read(content_length).decode("utf8"))

        print(f"Incoming POST request to {host}{self.path}")
        if host == "hub.docker.com":
            self.do_dockerhub_post(data)
        elif host == "api.ecr.us-east-1.amazonaws.com":
            self.do_ecr_post(data)
        else:
            self.send_json(404, {"error": f"Invalid request for host {host}"})

    def send_json(self, status_code: int, data: Dict) -> None:
        self.send_response(status_code)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf8"))

    def get_tag_list(self, repository: str) -> List[str]:
        try:
            with open(f"data/repositories/{repository}.json") as f:
                return json.loads(f.read())
        except Exception:
            return []

    def do_artifactory_get(self) -> None:
        match = re.search(r"/v2/(.*)/tags/list", self.path)
        if match is None:
            self.send_json(404, {"error": "Unexpected request path"})
            return

        if not (self.headers["authorization"] or "").startswith("Basic "):
            self.send_json(401, {"error": "basic authorization header required"})
            return

        tag_list = self.get_tag_list(match[1])
        status_code = 200
        if len(tag_list) == 0:
            status_code = 404

        self.send_json(status_code, {"tags": tag_list})

    def do_dockerhub_get(self) -> None:
        match = re.search(r"/v2/repositories/(.*)/tags", self.path)
        if match is None:
            self.send_json(404, {"error": f"Unexpected request path {self.path}"})
            return

        if self.headers["authorization"] != "JWT faketoken":
            self.send_json(401, {"error": "authorization header required"})
            return

        tag_list = self.get_tag_list(match[1])
        status_code = 200
        if len(tag_list) == 0:
            status_code = 404

        self.send_json(
            status_code,
            {"count": len(tag_list), "results": [{"name": t} for t in tag_list],},
        )

    def do_dockerhub_post(self, data: Dict) -> None:
        if self.path != "/v2/users/login":
            self.send_json(404, {"error": f"Unexpected request path {self.path}"})
            return

        if data.get("username") is None or data.get("password") is None:
            self.send_json(400, {"error": "Send a username and password"})
            return

        if data["username"] == "auth" and data["password"] == "failure":
            self.send_json(401, {"error": "Invalid credentials"})
            return

        self.send_json(200, {"token": "faketoken"})

    def do_ecr_post(self, data: Dict) -> None:
        """
        https://docs.aws.amazon.com/AmazonECR/latest/APIReference/ecr-api.pdf
        """
        target = (self.headers["x-amz-target"] or "").split(".")[-1]
        if target == "CreateRepository":
            self.created_repositories.append(str(data.get("repositoryName")))
            self.send_json(200, {})
        elif target == "DescribeRepositories":
            repositories = self.created_repositories.copy()
            root = os.path.join("data", "repositories")
            for path, directories, files in os.walk(root):
                for file in files:
                    repositories.append(
                        os.path.join(path, file)[len(root) + 1 :].split(".json")[0]
                    )

            self.send_json(
                200, {"repositories": [{"repositoryName": r} for r in repositories]}
            )
        elif target == "DescribeImages":
            repository = str(data.get("repositoryName"))
            tag_list = self.get_tag_list(repository)
            self.send_json(200, {"imageDetails": [{"imageTags": tag_list}]})
        else:
            self.send_json(400, {"error": f"Unexpected request target: {target}"})


print("Listening")
server = http.server.HTTPServer(("0.0.0.0", 443), RequestHandler)
server.socket = ssl.wrap_socket(
    server.socket, certfile="/tls/cert.pem", keyfile="/tls/key.pem", server_side=True
)
server.serve_forever()
