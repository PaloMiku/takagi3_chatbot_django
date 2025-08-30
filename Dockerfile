FROM python:3.12-slim AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
# 安装仅运行依赖（锁定）：
RUN uv sync --frozen --no-dev

# 复制源代码
COPY . .

# 收集静态资源
RUN .venv/bin/python manage.py collectstatic --noinput

# 可选：创建非 root 用户
RUN useradd -m appuser
USER appuser

# 运行阶段
EXPOSE 8000
# 使用 daphne（Channels 推荐）
CMD [".venv/bin/daphne", "-b", "0.0.0.0", "-p", "8000", "django_chatbot.asgi:application"]