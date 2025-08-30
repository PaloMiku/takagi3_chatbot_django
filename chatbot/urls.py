from django.urls import path
from . import views

urlpatterns = [
    path('', views.chatbot, name='chatbot'),
    path('login', views.login, name='login'),
    path('register', views.register, name='register'),
    path('register/send_code', views.send_email_code, name='send_email_code'),
    path('register/pwd_validate', views.password_validate, name='password_validate'),
    path('logout', views.logout, name='logout'),
    path('user/settings', views.user_settings, name='user_settings'),
    path('user/settings/update', views.user_settings_update, name='user_settings_update'),
]