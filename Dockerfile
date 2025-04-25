FROM registry.inventec/proxy/pytorch/pytorch:2.2.2-cuda12.1-cudnn8-runtime

ENV http_proxy="http://172.123.100.103:3128"
ENV https_proxy="http://172.123.100.103:3128"
# ENV PIPURL "https://nexus.itc.inventec.net/repository/pypi-proxy/simple"

WORKDIR /app

COPY requirements.txt /app/

RUN pip install -U "magic-pdf[full]==1.3.3" && \
    pip install -r requirements.txt


RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    ccache \
    libreoffice \
    && rm -rf /var/lib/apt/lists/*

# COPY . /app

ENV http_proxy=""
ENV https_proxy=""
ENV no_proxy=""

EXPOSE 8752
# CMD ["python3", "startup.py"]
