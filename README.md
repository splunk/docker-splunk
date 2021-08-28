# Docker-Splunk: Containerizing Splunk Enterprise with uid & guid=100

[![latest splunk image](https://github.com/8lex/docker-splunk/actions/workflows/splunk_image.yml/badge.svg)](https://github.com/8lex/docker-splunk/actions/workflows/splunk_image.yml)
[![GitHub release](https://img.shields.io/github/v/tag/8lex/docker-splunk?sort=semver&label=Version)](https://github.com/8lex/docker-splunk/releases)


----

A fork from splunk/docker-splunk with an automated dockerhub image

---

# why?

i wanted to have a container where the work with my vsc and wsl is possible. So its possible to to mount volumes and ansible will not overwrite them.

The Big problem was some hardcoded ARGS inside the dockerfiles.

inside this repo its changed to:
```
ARG UID=1000
ARG GID=1000
```

Two Github Actions are there to automate the build process to have finished docker images on dockerhub.

# Links

 [Dockerhub](https://hub.docker.com/repository/docker/8lex/splunk)
