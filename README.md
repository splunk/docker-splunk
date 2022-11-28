# Docker-Splunk: Containerizing Splunk Enterprise with uid & guid=1000

![Docker Image Version (tag latest semver)](https://img.shields.io/docker/v/8lex/splunk/latest?color=green&label=Splunk&style=for-the-badge)


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

 [Dockerhub](https://hub.docker.com/r/8lex/splunk)
