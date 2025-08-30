# Takagi3 Chatbot Django

一个基于 Django + OpenAI Chat Completions API 的简易聊天站点（高木同学人格预设）。

## 功能概述
- 用户注册 / 登录 / 注销
- 管理后台可配置全局 BotSetting（API Key、摘要指令）
- 每个用户独立的长对话上下文与个性化 Prompt（超过阈值自动生成摘要，降低 token）
- 简单的网页聊天界面

## 架构与依赖
- Python 3.10+
- Django 4.1.7（内置 sqlite）
- openai >=1.0.0
- python-dotenv 读取 `.env`
- 使用 `uv` 作为依赖与运行管理工具（极速安装）

## 快速开始
```bash
# 1. 安装 uv (若未安装)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 克隆仓库后进入目录
cd takagi3_chatbot_django

# 3. 创建并填写环境变量
cp .env.example .env
# 编辑 .env ：SECRET_KEY / OPENAI_API_KEY / DJANGO_DEBUG / ALLOWED_HOSTS

# 4. 安装依赖
uv sync  # 读取 pyproject.toml 并生成虚拟环境 .venv

# 5. 迁移数据库
uv run python manage.py migrate

# 6. 创建超级用户（用于后台设置 BotSetting）
uv run python manage.py createsuperuser

# 7. 收集静态文件（可选：开发期 DEBUG=True 时可不做）
uv run python manage.py collectstatic --noinput

# 8. 启动开发服务器
uv run python manage.py runserver
```
浏览器访问: http://127.0.0.1:8000/ ；后台 http://127.0.0.1:8000/admin/

## 配置说明
`.env` 示例：
```
SECRET_KEY=django-insecure-xxxx
OPENAI_API_KEY=sk-xxxxx
OPENAI_BASE_URL=   # 若使用代理/自建网关/企业版，此处填完整 base url 可选
OPENAI_MODEL_DEFAULT=gpt-3.5-turbo
DJANGO_DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
```

`settings.py` 中：
- SECRET_KEY / DEBUG / ALLOWED_HOSTS 均来自环境变量（带默认回退）
- STATIC_ROOT = BASE_DIR / 'static' （已存在静态目录）

## 对话与摘要
- 全局内存 `messages` 里按 `userid` 分片。
- 超过 `UserSetting.generate_summary_num * 2` 条（因为一问一答），触发 `generate_summary`：
  1. 发送 `summary_cmd` （来自 `BotSetting`）
  2. 用新摘要替换历史大段上下文

## 生产部署简要建议
- 设置 `DJANGO_DEBUG=False`
- 使用 `uv lock --upgrade` 定期升级安全补丁
- 使用 `gunicorn` 或 `uvicorn` + 反向代理 (nginx/caddy)
- 配置持久数据库（PostgreSQL 等）并修改 `DATABASES`
- 将 `OPENAI_API_KEY` 放入安全的环境变量管理（如 systemd EnvironmentFile / k8s Secret）

## 常见问题
1. 403 / CSRF 相关：确保模板中表单含 `{% csrf_token %}`。
2. OpenAI 调用失败：
  - 优先使用后台 BotSetting.apikey
  - 否则回退 `.env` 的 `OPENAI_API_KEY`
  - 可用 `OPENAI_BASE_URL` 指向代理；无代理请留空。
3. 大量并发导致上下文错乱：当前内存模式非线程安全，生产可改为 Redis / 数据库存储最近 N 条。

## 开发工具
使用 ruff 进行基础格式与导入整理：
```bash
uv run ruff check .
uv run ruff format .
```

## 许可证
MIT License. 详见 `LICENSE`。
