# Use the official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:slim

# Copy local code to the container image.
ENV APP_HOME /app
WORKDIR $APP_HOME

# Install production dependencies.
RUN pip install fediblockhole

USER 1001
# Set the command on start to fediblock-sync.
ENTRYPOINT ["fediblock-sync"]
