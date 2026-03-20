#!/bin/bash
# Tail live colored logs from pl-dashboard container (Ctrl+C to stop)
DOCKER_HOST="${DOCKER_HOST:-unix:///Users/lenin/.docker/run/docker.sock}"
export DOCKER_HOST
docker logs -f pl-dashboard
