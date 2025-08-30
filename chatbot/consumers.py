import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from openai import AsyncOpenAI, BadRequestError
from .models import UserSetting, BotSetting, Message
import os


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close()
            return
        await self.accept()
        await self.send_json({"type": "welcome", "msg": "connected"})

    async def receive(self, text_data=None, bytes_data=None):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.send_json({"error": "unauthorized"})
            return
        if not text_data:
            return
        try:
            data = json.loads(text_data)
        except Exception:
            await self.send_json({"error": "bad_json"})
            return
        user_input = (data.get('message') or '').strip()
        if not user_input:
            await self.send_json({"error": "empty_message"})
            return

        user_setting, _ = UserSetting.objects.get_or_create(user=user)
        bot_setting = BotSetting.objects.first()

        # 选择 API Key / base_url 优先级：user -> bot -> env
        api_key = user_setting.user_api_key or (bot_setting.apikey if bot_setting and bot_setting.apikey else getattr(settings,'OPENAI_API_KEY', None) or os.getenv('OPENAI_API_KEY'))
        base_url = user_setting.user_base_url or getattr(settings, 'OPENAI_BASE_URL', None)
        if not api_key:
            await self.send_json({"error": "no_api_key"})
            return

        client = AsyncOpenAI(api_key=api_key, base_url=base_url or None)

        # conversation: 使用第一条 system 消息的 conversation_id
        first_system = Message.objects.filter(user=user, role='system').order_by('created_at').first()
        if first_system:
            conversation_id = first_system.conversation_id
        else:
            system_msg = Message.objects.create(user=user, role='system', content=user_setting.prompt)
            conversation_id = system_msg.conversation_id

        # 记录用户消息
        Message.objects.create(user=user, role='user', content=user_input, conversation_id=conversation_id)

        # 构造上下文
        token_limit = getattr(settings, 'TOKEN_CONTEXT_LIMIT', 3000)
        qs = Message.objects.filter(user=user, conversation_id=conversation_id).order_by('-created_at')
        acc = 0
        ctx = []
        for m in qs:
            acc += m.tokens or 0
            if acc > token_limit:
                break
            ctx.append(m)
        ctx.reverse()
        send_chat = [{"role": m.role, "content": m.content} for m in ctx]

        model_name = (user_setting.modelName or getattr(settings, 'OPENAI_DEFAULT_MODEL', 'gpt-3.5-turbo')).strip()

        try:
            stream = await client.chat.completions.create(model=model_name, messages=send_chat, stream=True)
            full = []
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content or ''
                if delta:
                    full.append(delta)
                    await self.send_json({"delta": delta})
            final_text = ''.join(full).strip()
            if final_text:
                Message.objects.create(user=user, role='assistant', content=final_text, conversation_id=conversation_id)
            await self.send_json({"done": True})
        except BadRequestError as e:
            await self.send_json({"error": f"model_error: {e}"})
        except Exception as e:
            await self.send_json({"error": f"exception: {e}"})

    async def send_json(self, data):
        await self.send(text_data=json.dumps(data, ensure_ascii=False))
