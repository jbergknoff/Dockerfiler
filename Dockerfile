FROM python:3.8.3-alpine3.12
WORKDIR /opt/dockerfiler
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY src src
ENTRYPOINT ["python", "/opt/dockerfiler/src/main.py"]
