ARG BASE_IMAGE=python:3.14-slim-bookworm
FROM ${BASE_IMAGE} AS installed
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 NO_COLOR=1
COPY wheel/*.whl /wheel/
RUN python -m pip --isolated install --extra-index-url https://whl.modular.com/nightly/simple/ --report /installation.json /wheel/*.whl
COPY probe.py native_smoke.h test_import.mojo /probe/
WORKDIR /work

FROM installed AS headers
RUN apt-get update && apt-get install -y --no-install-recommends libc6-dev && rm -rf /var/lib/apt/lists/*

FROM headers AS toolchain
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
