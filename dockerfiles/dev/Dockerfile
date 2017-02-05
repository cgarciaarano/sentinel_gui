############################################################
# Dockerfile to build gitlabhub DEV environment.
# Project dir is mounted
#
# Based on Alpine Python 3.4
############################################################

# Set the base image to Ubuntu
FROM python:3.4-alpine

MAINTAINER cgarciaarano@gmail.com

# Update the repository sources list
RUN apk update && apk add libffi-dev redis

# Add requirements
COPY requirements/ /opt/app/requirements/

WORKDIR /opt/app

# Install Python packages and system build dependencies
RUN apk add g++ make && \
	pip install -r requirements/dev.txt && \
	apk del g++ make && \
	rm -rf /var/cache/apk/* 