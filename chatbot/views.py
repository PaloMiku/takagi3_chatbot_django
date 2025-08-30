from django.shortcuts import render, redirect
from django.http import JsonResponse
from openai import OpenAI, BadRequestError
from django.conf import settings
import os
from django.contrib import auth
from django.contrib.auth.models import User
from .models import Chat, UserSetting, BotSetting, Message
from django.utils import timezone
from django.contrib.auth.decorators import login_required

#生成摘要的命令
summary_cmd = ""

# 系统运行时所有用户的会话
def ask_openai(user_message: str, request):
    """使用数据库中持久化的 Message 构造上下文并调用 OpenAI。"""
    user = request.user

    # 获取 / 初始化用户设置
    user_setting, _ = UserSetting.objects.get_or_create(user=user)

    # 读取 BotSetting & API Key
    api_key = None
    base_url = getattr(settings, 'OPENAI_BASE_URL', None)
    bot_setting = BotSetting.objects.first()
    # 用户自定义优先
    if user_setting.user_api_key:
        api_key = user_setting.user_api_key.strip()
    elif bot_setting and bot_setting.apikey:
        api_key = bot_setting.apikey
    else:
        api_key = getattr(settings, 'OPENAI_API_KEY', None) or os.getenv('OPENAI_API_KEY')

    summary_cmd_local = bot_setting.summary_cmd if bot_setting else "请总结我们的对话，要求不能超过200字"

    # base_url 也允许用户覆盖
    if user_setting.user_base_url:
        base_url = user_setting.user_base_url.strip()
    if not api_key:
        return "OpenAI API Key 未配置，请联系管理员或在 .env 中设置 OPENAI_API_KEY。"

    client = OpenAI(api_key=api_key, base_url=base_url or None)

    # 若还没有任何系统提示，为本会话插入一条 system prompt（后续支持多会话时需传 conversation_id）
    conversation_id = None
    first_system = Message.objects.filter(user=user, role='system').order_by('created_at').first()
    if first_system:
        conversation_id = first_system.conversation_id
    if not conversation_id:
        # 创建系统消息
        system_msg = Message.objects.create(user=user, role='system', content=user_setting.prompt, is_summary=False)
        conversation_id = system_msg.conversation_id

    # 写入当前用户输入
    user_msg_obj = Message.objects.create(user=user, role='user', content=user_message, conversation_id=conversation_id)

    # 统计当前会话消息，按时间升序
    qs = Message.objects.filter(user=user, conversation_id=conversation_id).order_by('-created_at')

    token_limit = getattr(settings, 'TOKEN_CONTEXT_LIMIT', 3000)
    accumulated = 0
    context_messages = []
    for m in qs:
        accumulated += (m.tokens or 0)
        if accumulated > token_limit:
            break
        context_messages.append(m)
    context_messages.reverse()  # 还原时间顺序

    sendChat = [
        {"role": m.role, "content": m.content} for m in context_messages
    ]

    # 检查是否需要摘要：用户消息数量（非系统/摘要）超过 generate_summary_num*2
    non_summary_pairs = Message.objects.filter(user=user, conversation_id=conversation_id, role__in=['user','assistant'], is_summary=False).count()
    if non_summary_pairs > user_setting.generate_summary_num * 2:
        summary_text = generate_summary(user, conversation_id, summary_cmd_local, client, sendChat, user_setting)
        if summary_text:
            # 删除旧的非摘要对话（保留最近两轮以免摘要突兀）
            old_msgs = Message.objects.filter(user=user, conversation_id=conversation_id, role__in=['user','assistant'], is_summary=False).order_by('-created_at')[2:]
            # 为避免直接 delete 误删最近，需要取除去前2条之后的剩余
            ids_to_delete = list(old_msgs.values_list('id', flat=True))
            if ids_to_delete:
                Message.objects.filter(id__in=ids_to_delete).delete()
            Message.objects.create(user=user, role='system', content=summary_text, is_summary=True, conversation_id=conversation_id)
            # 重新构建上下文
            qs2 = Message.objects.filter(user=user, conversation_id=conversation_id).order_by('-created_at')
            accumulated = 0
            context_messages = []
            for m in qs2:
                accumulated += (m.tokens or 0)
                if accumulated > token_limit:
                    break
                context_messages.append(m)
            context_messages.reverse()
            sendChat = [{"role": m.role, "content": m.content} for m in context_messages]

    configured_default = getattr(settings, 'OPENAI_DEFAULT_MODEL', 'gpt-3.5-turbo')
    model_name = (user_setting.modelName or configured_default).strip()

    def _invoke(model: str):
        return client.chat.completions.create(model=model, messages=sendChat)

    tried_fallback = False
    while True:
        try:
            response = _invoke(model_name)
            answer = response.choices[0].message.content.strip()
            Message.objects.create(user=user, role='assistant', content=answer, conversation_id=conversation_id)
            return answer
        except BadRequestError as e:
            if (not tried_fallback) and ('model' in str(e).lower() and 'exist' in str(e).lower()):
                tried_fallback = True
                fallback_model = configured_default
                if model_name == fallback_model:
                    fallback_model = 'gpt-3.5-turbo'
                model_name = fallback_model
                sendChat.append({"role": "system", "content": f"(注意: 原模型不可用，已自动切换为 {model_name})"})
                continue
            return f"模型调用失败：{e}. 请确认模型名称已在服务端启用。"
        except Exception as e:  # 广泛捕获防止 500 直接暴露
            return f"调用出错：{e}"

# Create your views here.
def chatbot(request):
    user=request.user
    if user.id is None:
        return redirect('login')
    else:
        # 兼容旧 Chat 表：仍用于显示历史（后续可改用 Message）
        chats = Chat.objects.filter(user=request.user).order_by('created_at')

    if request.method == 'POST':
        message = request.POST.get('message')
        response = ask_openai(message, request)
        # 仍写入旧 Chat 表，保持模板兼容
        Chat.objects.create(user=request.user, message=message, response=response, created_at=timezone.now())
        return JsonResponse({'message': message, 'response': response})
    return render(request, 'chatbot.html', {'chats': chats})

def login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = auth.authenticate(request, username=username, password=password)
        if user is not None:
            auth.login(request, user)
            return redirect('chatbot')
        else:
            error_message = '账号或密码错误'
            return render(request, 'login.html', {'error_message': error_message})
    else:
        return render(request, 'login.html')

def register(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password1 = request.POST['password1']
        password2 = request.POST['password2']

        if password1 == password2:
            try:
                user = User.objects.create_user(username, email, password1)
                user.save()
                UserSetting.objects.create(user=user)
                auth.login(request, user)
                return redirect('chatbot')
            except:
                error_message = '创建帐户出错'
                return render(request, 'register.html', {'error_message': error_message})
        else:
            error_message = '密码不匹配'
            return render(request, 'register.html', {'error_message': error_message})
    return render(request, 'register.html')

def logout(request):
    auth.logout(request)
    return redirect('login')

@login_required
def user_settings(request):
    user_setting, _ = UserSetting.objects.get_or_create(user=request.user)
    saved = False
    error = None
    if request.method == 'POST':
        model_name = request.POST.get('modelName', '').strip()
        user_api_key = request.POST.get('user_api_key', '').strip()
        user_base_url = request.POST.get('user_base_url', '').strip()
        # 简单校验
        if len(model_name) > 100:
            error = '模型名称过长'
        else:
            user_setting.modelName = model_name or user_setting.modelName
            user_setting.user_api_key = user_api_key or None
            user_setting.user_base_url = user_base_url or None
            user_setting.save()
            saved = True
    return render(request, 'user_settings.html', {
        'user_setting': user_setting,
        'saved': saved,
        'error': error,
    })

def generate_summary(user, conversation_id, summary_cmd_local, client, current_send_chat, user_setting):
    """生成摘要文本。current_send_chat 已含上下文。"""
    # 添加一条用户指令 summary 到临时消息副本
    temp = current_send_chat + [{"role": "user", "content": summary_cmd_local}]
    configured_default = getattr(settings, 'OPENAI_DEFAULT_MODEL', 'gpt-3.5-turbo')
    model_name = (user_setting.modelName or configured_default).strip()

    def _invoke(model: str):
        return client.chat.completions.create(model=model, messages=temp)

    tried_fallback = False
    while True:
        try:
            response = _invoke(model_name)
            return response.choices[0].message.content.strip()
        except BadRequestError as e:
            if (not tried_fallback) and ('model' in str(e).lower() and 'exist' in str(e).lower()):
                tried_fallback = True
                fallback_model = configured_default
                if model_name == fallback_model:
                    fallback_model = 'gpt-3.5-turbo'
                model_name = fallback_model
                continue
            return None
        except Exception:
            return None
