from django.urls import path
from . import views

urlpatterns = [
    path('', views.chatbot, name='chatbot'),
    path('login', views.login, name='login'),
    path('register', views.register, name='register'),
    path('register/send_code', views.send_email_code, name='send_email_code'),
    path('password/send_reset_code', views.send_reset_code, name='send_reset_code'),
    path('password/reset', views.password_reset_request, name='password_reset_request'),
    path('password/reset/confirm', views.password_reset_confirm, name='password_reset_confirm'),
    path('register/pwd_validate', views.password_validate, name='password_validate'),
    path('logout', views.logout, name='logout'),
    path('user/settings', views.user_settings, name='user_settings'),
    path('user/settings/update', views.user_settings_update, name='user_settings_update'),
    path('user/settings/change_password', views.inline_change_password, name='inline_change_password'),
    path('api/chat/history', views.get_chat_history, name='get_chat_history'),
]