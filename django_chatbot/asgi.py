"""
ASGI config for django_chatbot project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path
from chatbot.consumers import ChatConsumer

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_chatbot.settings')

django_app = get_asgi_application()

websocket_urlpatterns = [
	path('ws/chat/', ChatConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
	'http': django_app,
	'websocket': AuthMiddlewareStack(
		URLRouter(websocket_urlpatterns)
	),
})
