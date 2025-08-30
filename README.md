# Takagi3 Chatbot Django

一个基于 Django + Channels + OpenAI Chat Completions API 的简易聊天站点（高木同学人格预设）。

> 注意：仓库初始不再附带默认的 `db.sqlite3`，首次启动需自行迁移创建。

## 功能概述
* 用户注册 / 登录 / 注销（注册含邮箱验证码、密码强度校验）
* 管理后台可配置全局 BotSetting（全局 API Key、摘要指令）
* 用户独立会话上下文（Message 表持久化，按 `conversation_id` 分组）
* 超阈值自动摘要（减少历史 token，插入 `is_summary` system message）
* WebSocket 实时流式回复（`/ws/chat/`）+ 普通表单 POST 兼容
* 用户自定义：模型名、专属 API Key、Base URL、头像 URL、昵称
* 静态资源与 WhiteNoise 压缩缓存

## 目录结构速览
```
django_chatbot/    # 项目配置、ASGI/WSGI/urls/settings
chatbot/           # 应用：models / views / consumers / urls
templates/         # HTML 模板（login, register, chatbot, user_settings 等）
static/            # 前端静态资源 (css/js/img)
pyproject.toml     # 依赖与构建（使用 uv）
.env.example       # 环境变量示例
```

## 运行环境与依赖
* Python >= 3.10
* Django 4.2.x
* channels 4.x + daphne 4.x （ASGI & WebSocket）
* openai >= 1.0.0
* python-dotenv 加载环境变量
* whitenoise 提供静态文件（生产无需额外 Nginx 托管静态）
* uv （极速包管理 & 虚拟环境）

## 一键快速启动 (开发模式)
```bash
# 1. 安装 uv (若未安装)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 克隆仓库并进入
git clone https://github.com/PaloMiku/takagi3_chatbot_django.git
cd takagi3_chatbot_django

# 3. 初始化环境变量
cp .env.example .env
# 必填: SECRET_KEY / OPENAI_API_KEY
# 可选: OPENAI_BASE_URL / OPENAI_MODEL_DEFAULT / 邮件配置

# 4. 安装依赖 (自动创建 .venv)
uv sync

# 5. 生成数据库
uv run python manage.py migrate

# 6. 创建后台超级用户
uv run python manage.py createsuperuser

# 7. (可选) 收集静态文件
uv run python manage.py collectstatic --noinput

# 8. 启动开发服务器
uv run python manage.py runserver

```
访问：
* 前台：http://127.0.0.1:8000/
* 后台：http://127.0.0.1:8000/admin/
* WebSocket Endpoint：`ws://127.0.0.1:8000/ws/chat/`（需已登录 Cookie 会话）

## `.env` 配置详解
参考 `.env.example`：
```
SECRET_KEY=django-insecure-xxxx              # 生产务必更换
OPENAI_API_KEY=sk-xxxxx                     # 可被用户或 BotSetting 覆盖
OPENAI_BASE_URL=https://api.deepseek.com/v1 # 可选: 自建代理/兼容端点
OPENAI_MODEL_DEFAULT=deepseek-chat          # 默认模型
DJANGO_DEBUG=True                           # 生产改 False
ALLOWED_HOSTS=127.0.0.1,localhost           # 多个以逗号分隔

# 邮件（注册验证码）
EMAIL_HOST=smtp.example.com
EMAIL_PORT=465
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
DEFAULT_FROM_EMAIL=no-reply@example.com

# 可选：上下文 token 粗算上限（字符/4）
TOKEN_CONTEXT_LIMIT=3000
```

## 切换到生产数据库 (PostgreSQL 示例)
1. 安装驱动：
```bash
uv add psycopg2-binary
```
2. 修改 `django_chatbot/settings.py` 中 `DATABASES`：
```python
DATABASES = {
  'default': {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': os.getenv('PG_NAME','takagi'),
    'USER': os.getenv('PG_USER','takagi'),
    'PASSWORD': os.getenv('PG_PASSWORD',''),
    'HOST': os.getenv('PG_HOST','127.0.0.1'),
    'PORT': os.getenv('PG_PORT','5432'),
  }
}
```
3. 新增相关环境变量并执行迁移：
```bash
uv run python manage.py migrate
```

## 许可证
MIT License. 详见 `LICENSE`。
