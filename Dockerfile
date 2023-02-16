FROM python:3-slim

RUN pip install --no-cache-dir --upgrade pip && \
	pip install --no-cache-dir fediblockhole

CMD fediblock-sync
