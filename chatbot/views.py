from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseBadRequest
from openai import OpenAI, BadRequestError
from django.conf import settings
import os
from django.contrib import auth
from django.contrib.auth.models import User
from .models import Chat, UserSetting, BotSetting, Message
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.core.cache import cache
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth import update_session_auth_hash
import random
import string

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
    # 确保有 UserSetting 以便模板访问 user.usersetting
    UserSetting.objects.get_or_create(user=user)

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
        username = request.POST.get('username','').strip()
        email = request.POST.get('email','').strip().lower()
        password1 = request.POST.get('password1','')
        password2 = request.POST.get('password2','')
        code = request.POST.get('email_code','').strip()

        ctx = {
            'prefill_username': username,
            'prefill_email': email,
        }

        # 基本校验
        if not username or not email:
            ctx['error_message'] = '用户名和邮箱必填'
            return render(request, 'register.html', ctx)
        if password1 != password2:
            ctx['error_message'] = '两次密码不一致'
            return render(request, 'register.html', ctx)
        # 使用 Django 内置验证器收集错误
        pwd_errors = []
        try:
            # 提供一个临时未保存用户对象用于相似度验证
            temp_user = User(username=username, email=email)
            validate_password(password1, user=temp_user)
            # 额外：必须同时包含字母与数字（可选增强）
            if not (any(c.isalpha() for c in password1) and any(c.isdigit() for c in password1)):
                pwd_errors.append('密码需同时包含字母与数字')
        except ValidationError as e:
            pwd_errors.extend(e.messages)
        if pwd_errors:
            ctx['error_message'] = ' / '.join(pwd_errors)
            return render(request, 'register.html', ctx)
        cache_key = f'reg_email_code:{email}'
        saved_code = cache.get(cache_key)
        attempt_key = f'reg_email_code_attempts:{email}'
        if not saved_code:
            ctx['error_message'] = '验证码已过期，请重新发送'
            return render(request, 'register.html', ctx)
        if saved_code != code:
            attempts = cache.get(attempt_key, 0) + 1
            # 记录 5 分钟窗口内错误次数
            cache.set(attempt_key, attempts, 300)
            if attempts >= 5:
                # 保护：失效旧验证码，需重新发送
                cache.delete(cache_key)
                ctx['error_message'] = '验证码错误次数过多，请重新发送'
            else:
                ctx['error_message'] = f'验证码错误，还可再尝试 {5 - attempts} 次'
            return render(request, 'register.html', ctx)
        if User.objects.filter(username=username).exists():
            ctx['error_message'] = '用户名已存在'
            return render(request, 'register.html', ctx)
        if User.objects.filter(email=email).exists():
            ctx['error_message'] = '邮箱已注册'
            return render(request, 'register.html', ctx)
        try:
            user = User.objects.create_user(username=username, email=email, password=password1)
            UserSetting.objects.create(user=user)
            cache.delete(cache_key)
            cache.delete(attempt_key)
            auth.login(request, user)
            return redirect('chatbot')
        except Exception as e:
            ctx['error_message'] = f'创建账户失败: {e}'
            return render(request, 'register.html', ctx)
    return render(request, 'register.html')

@require_POST
def send_email_code(request):
    email = request.POST.get('email','').strip().lower()
    if not email:
        return HttpResponseBadRequest('缺少邮箱')
    # 限制频率：同邮箱 60 秒
    freq_key = f'reg_email_code_freq:{email}'
    if cache.get(freq_key):
        return JsonResponse({'ok': False, 'error': '发送太频繁，请稍后再试'})
    code = ''.join(random.choices(string.digits, k=6))
    cache.set(f'reg_email_code:{email}', code, 300)  # 5 分钟有效
    cache.set(freq_key, 1, 60)
    # 重置错误尝试次数
    cache.delete(f'reg_email_code_attempts:{email}')
    try:
        send_mail('注册验证码', f'您的验证码是: {code} (5分钟内有效)', settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'发送失败: {e}'})
    return JsonResponse({'ok': True})


@require_POST
def send_reset_code(request):
    """发送用于密码找回的验证码（邮件 HTML 美化）。"""
    email = request.POST.get('email','').strip().lower()
    if not email:
        return HttpResponseBadRequest('缺少邮箱')
    freq_key = f'pwd_reset_code_freq:{email}'
    if cache.get(freq_key):
        return JsonResponse({'ok': False, 'error': '发送太频繁，请稍后再试'})
    code = ''.join(random.choices(string.digits, k=6))
    cache.set(f'pwd_reset_code:{email}', code, 300)  # 5 分钟有效
    cache.set(freq_key, 1, 60)
    cache.delete(f'pwd_reset_code_attempts:{email}')
    # 发送 HTML 邮件
    try:
        subject = '密码重置验证码 - Takagi AI'
        # 尝试获取站点域名
        site_url = getattr(settings, 'SITE_URL', None)
        if not site_url:
            try:
                site = get_current_site(request)
                site_url = f'https://{site.domain}'
            except Exception:
                site_url = '/'
        html_content = render_to_string('email/password_reset_email.html', {'code': code, 'site_url': site_url, 'email': email})
        text_content = strip_tags(html_content)
        msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [email])
        msg.attach_alternative(html_content, 'text/html')
        msg.send(fail_silently=False)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'发送失败: {e}'})
    return JsonResponse({'ok': True})


def password_reset_request(request):
    """渲染邮箱输入页面，用户提交邮箱以接收验证码。"""
    if request.method == 'POST':
        email = request.POST.get('email','').strip().lower()
        if not email:
            return render(request, 'password_reset_request.html', {'error': '请输入邮箱'})
        # 只要发送验证码（不校验邮箱是否存在），前端会提示
        # 使用 AJAX 调用 send_reset_code
        return render(request, 'password_reset_request.html', {'sent': True, 'email': email})
    return render(request, 'password_reset_request.html')


def password_reset_confirm(request):
    """用户提交验证码与新密码以完成重置。"""
    if request.method == 'POST':
        email = request.POST.get('email','').strip().lower()
        code = request.POST.get('code','').strip()
        new1 = request.POST.get('new_password1','')
        new2 = request.POST.get('new_password2','')
        ctx = {'email': email}
        if not email or not code or not new1 or not new2:
            ctx['error'] = '请填写所有字段'
            return render(request, 'password_reset_confirm.html', ctx)
        if new1 != new2:
            ctx['error'] = '两次新密码不一致'
            return render(request, 'password_reset_confirm.html', ctx)
        saved_code = cache.get(f'pwd_reset_code:{email}')
        if not saved_code:
            ctx['error'] = '验证码已过期，请重新获取'
            return render(request, 'password_reset_confirm.html', ctx)
        if saved_code != code:
            attempts = cache.get(f'pwd_reset_code_attempts:{email}', 0) + 1
            cache.set(f'pwd_reset_code_attempts:{email}', attempts, 300)
            if attempts >= 5:
                cache.delete(f'pwd_reset_code:{email}')
                ctx['error'] = '验证码错误次数过多，请重新获取'
            else:
                ctx['error'] = f'验证码错误，还可再尝试 {5 - attempts} 次'
            return render(request, 'password_reset_confirm.html', ctx)
        # 验证通过，查找用户并设置新密码
        try:
            user = User.objects.filter(email=email).first()
            if not user:
                # 为了安全不暴露是否存在用户，仍提示成功
                cache.delete(f'pwd_reset_code:{email}')
                return render(request, 'password_reset_confirm.html', {'ok': True})
            # 验证新密码强度
            try:
                validate_password(new1, user=user)
                if not (any(c.isalpha() for c in new1) and any(c.isdigit() for c in new1)):
                    return render(request, 'password_reset_confirm.html', {'error': '密码需同时包含字母与数字', 'email': email})
            except ValidationError as e:
                return render(request, 'password_reset_confirm.html', {'error': ' / '.join(e.messages), 'email': email})
            user.set_password(new1)
            user.save()
            cache.delete(f'pwd_reset_code:{email}')
            # 自动登录用户
            auth.login(request, user)
            return render(request, 'password_reset_confirm.html', {'ok': True})
        except Exception as e:
            return render(request, 'password_reset_confirm.html', {'error': f'重置失败: {e}', 'email': email})
    # GET
    email = request.GET.get('email','').strip().lower()
    return render(request, 'password_reset_confirm.html', {'email': email})

@require_POST
def password_validate(request):
    """AJAX 密码验证：返回内置验证器错误与自定义强度信息。"""
    pwd = request.POST.get('password','')
    username = request.POST.get('username','')
    email = request.POST.get('email','')
    errors = []
    if not pwd:
        return JsonResponse({'ok': False, 'errors': ['密码为空']})
    try:
        temp_user = User(username=username or 'tempuser', email=email)
        validate_password(pwd, user=temp_user)
        if not (any(c.isalpha() for c in pwd) and any(c.isdigit() for c in pwd)):
            errors.append('需同时包含字母与数字')
    except ValidationError as e:
        errors.extend(e.messages)
        if not (any(c.isalpha() for c in pwd) and any(c.isdigit() for c in pwd)):
            # 避免重复信息
            msg = '需同时包含字母与数字'
            if msg not in errors:
                errors.append(msg)
    # 简单强度评分与级别
    score = 0
    if len(pwd) >= 8: score += 1
    if any(c.islower() for c in pwd) and any(c.isupper() for c in pwd): score += 1
    if any(c.isdigit() for c in pwd): score += 1
    if any(not c.isalnum() for c in pwd): score += 1
    if len(pwd) >= 12: score += 1
    levels = ['弱','较弱','一般','较强','很强']
    level = levels[score-1] if score>0 else '极弱'
    return JsonResponse({'ok': len(errors)==0, 'errors': errors, 'score': score, 'level': level})

def logout(request):
    auth.logout(request)
    return redirect('login')

@login_required
def user_settings(request):
    user_setting, _ = UserSetting.objects.get_or_create(user=request.user)
    
    # Reset daily count if date has changed
    if not request.user.is_superuser and not user_setting.user_api_key:
        today = timezone.now().date()
        if user_setting.last_message_date != today:
            user_setting.daily_message_count = 0
            user_setting.last_message_date = today
            user_setting.save()

    saved = False
    error = None
    if request.method == 'POST':
        model_name = request.POST.get('modelName', '').strip()
        user_api_key = request.POST.get('user_api_key', '').strip()
        user_base_url = request.POST.get('user_base_url', '').strip()
        avatar_url = request.POST.get('avatar_url', '').strip()
        nickname = request.POST.get('nickname', '').strip()
        # 简单校验
        if len(model_name) > 100:
            error = '模型名称过长'
        else:
            user_setting.modelName = model_name or user_setting.modelName
            user_setting.user_api_key = user_api_key or None
            user_setting.user_base_url = user_base_url or None
            user_setting.avatar_url = avatar_url or None
            if nickname and len(nickname) <= 150 and nickname != request.user.username:
                request.user.username = nickname
                request.user.save(update_fields=['username'])
            user_setting.save()
            saved = True
    return render(request, 'user_settings.html', {
        'user_setting': user_setting,
        'saved': saved,
        'error': error,
    })

@login_required
@require_POST
def user_settings_update(request):
    """前端浮窗 AJAX 保存用户设置。返回 JSON。"""
    user_setting, _ = UserSetting.objects.get_or_create(user=request.user)
    model_name = request.POST.get('modelName', '').strip()
    user_api_key = request.POST.get('user_api_key', '').strip()
    user_base_url = request.POST.get('user_base_url', '').strip()
    avatar_url = request.POST.get('avatar_url', '').strip()
    nickname = request.POST.get('nickname', '').strip()
    if model_name and len(model_name) > 100:
        return JsonResponse({'ok': False, 'error': '模型名称过长'})
    if nickname and len(nickname) > 150:
        return JsonResponse({'ok': False, 'error': '昵称过长'})
    if model_name:
        user_setting.modelName = model_name
    user_setting.user_api_key = user_api_key or None
    user_setting.user_base_url = user_base_url or None
    user_setting.avatar_url = avatar_url or None
    user_setting.save()
    if nickname and nickname != request.user.username:
        request.user.username = nickname
        request.user.save(update_fields=['username'])
    return JsonResponse({'ok': True, 'nickname': request.user.username, 'avatar': user_setting.avatar_url})


@login_required
@require_POST
def inline_change_password(request):
    """AJAX: 内联设置弹窗中的修改密码接口，返回 JSON。"""
    old = request.POST.get('old_password','')
    new1 = request.POST.get('new_password1','')
    new2 = request.POST.get('new_password2','')
    if not old or not new1 or not new2:
        return JsonResponse({'ok': False, 'error': '请填写所有字段'})
    if new1 != new2:
        return JsonResponse({'ok': False, 'error': '两次新密码不一致'})
    user = request.user
    if not user.check_password(old):
        return JsonResponse({'ok': False, 'error': '旧密码错误'})
    # 强度校验
    try:
        validate_password(new1, user=user)
        if not (any(c.isalpha() for c in new1) and any(c.isdigit() for c in new1)):
            return JsonResponse({'ok': False, 'error': '密码需同时包含字母与数字'})
    except ValidationError as e:
        return JsonResponse({'ok': False, 'error': ' / '.join(e.messages)})
    try:
        user.set_password(new1)
        user.save()
        # 保持 session 不被登出
        update_session_auth_hash(request, user)
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'修改失败: {e}'})

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
