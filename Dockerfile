############################
# 1) 构建阶段（builder）   #
############################
FROM python:3.11-slim AS builder

# 基础环境
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 安装编译期依赖，仅用于构建 wheels/安装依赖
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        gnupg \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv 与 gunicorn（gunicorn 随依赖一并复制到运行层）
RUN pip install --no-cache-dir uv gunicorn

# 复制全部源码（.dockerignore 已排除不必要文件）
COPY . .

# 安装项目及依赖到系统 Python（builder 层）
RUN uv pip install --system --no-cache-dir .

############################
# 2) 运行阶段（runtime）    #
############################
FROM python:3.11-slim AS runtime

# 仅运行所需环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=run.py \
    FLASK_ENV=production

WORKDIR /app

# 从构建层复制已安装的 site-packages 与可执行文件（包含 gunicorn）
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 仅复制运行所需代码
COPY app app
COPY scripts scripts
COPY run.py config.py logging_config.py start.sh ./

# 创建必要目录与最小权限用户
RUN mkdir -p logs data \
    && adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app \
    && chmod +x /app/start.sh

USER appuser

# 暴露端口
EXPOSE 5000

# 健康检查：使用 Python 实现，避免额外安装 curl
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/', timeout=5)"

# 启动应用
CMD ["/app/start.sh"]
