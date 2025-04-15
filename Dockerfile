FROM pytorch/pytorch:2.2.2-cuda12.1-cudnn8-runtime

# 设置代理
ENV http_proxy="http://proxy2.tao.inventec:3128"
ENV https_proxy="http://proxy2.tao.inventec:3128"
#ENV PIPURL "https://nexus.itc.inventec.net/repository/pypi-proxy/simple"

# 设置工作目录
WORKDIR /app

# 安装依赖
COPY requirements.txt /app/

RUN pip install -U "magic-pdf[full]==1.3.1" && \
    pip install -r requirements.txt


# 安装包
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    ccache \
    libreoffice \
    && rm -rf /var/lib/apt/lists/*

# 复制应用代码
# COPY . /app

ENV http_proxy=""
ENV https_proxy=""
ENV no_proxy=""

EXPOSE 8752
# CMD ["python3", "startup.py"]