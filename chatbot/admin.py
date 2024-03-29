from django.contrib import admin
from .models import Chat , UserSetting, BotSetting

# Register your models here.
admin.site.register(Chat)
admin.site.register(UserSetting)
admin.site.register(BotSetting)