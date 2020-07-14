openssl = docker run -i --rm -v "$$(pwd)":"$$(pwd)" -w "$$(pwd)" -u $$(id -u):$$(id -g) $(2) \
	dockerizedtools/openssl:1.1.1g-r0 $(1)

# Generate a self-signed certificate (cert.pem) and private key (key.pem)
# Based off of https://serverfault.com/a/845788
self-signed-cert:
	rm -f openssl.cnf
	$(call openssl, -c 'cp /etc/ssl/openssl.cnf .', --entrypoint sh)
	echo '[SAN]' >> openssl.cnf
	echo 'subjectAltName=DNS:hub.docker.com, DNS:fake.jfrog.io, DNS:api.ecr.us-east-1.amazonaws.com' >> openssl.cnf

	$(call openssl, \
		req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -nodes -days 3650 \
			-subj '/CN=localhost' \
			-reqexts SAN \
			-extensions SAN \
			-config openssl.cnf \
	)

	rm openssl.cnf
