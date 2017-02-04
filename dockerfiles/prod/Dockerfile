############################################################
# Dockerfile to build PRO environment.
# Project dir is copied
#
# Based on Alpine + Python 3.4
############################################################

# Set the base image to Ubuntu
FROM python:3.4-alpine

MAINTAINER cgarciaarano@gmai.com

# Update the repository sources list
RUN apk update && apk add libffi-dev

# Add code
COPY . /opt/app

WORKDIR /opt/app

# Install Python packages and system build dependencies
RUN apk add g++ make && \
	pip install -r requirements/dev.txt && \
	apk del g++ make && \
	rm -rf /var/cache/apk/* 

EXPOSE 8080
CMD ["/usr/bin/python","manage.py"]