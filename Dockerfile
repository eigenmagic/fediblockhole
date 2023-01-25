FROM python:3-slim
#RUN apt-get update
#RUN apt-get install -y --no-install-recommends build-essential gcc

RUN pip install --no-cache-dir --upgrade pip && \
	pip install --no-cache-dir fediblockhole

CMD fediblock-sync
