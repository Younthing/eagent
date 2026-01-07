# syntax=docker/dockerfile:1.6
FROM ghcr.io/astral-sh/uv:python3.13-bookworm

WORKDIR /workspace
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# 安装运行时依赖
# libgomp1: OpenMP支持
# poppler-utils: PDF解析工具
# libgl1: OpenGL库(Docling可能需要)
# libglib2.0-0: GLib库
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgomp1 \
        poppler-utils \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 复制所有源码和项目文件
COPY . .

# 安装依赖
RUN uv sync --frozen --no-dev

ENTRYPOINT ["rob2"]
CMD ["-h"]
