"""ASGI config for django_chatbot project.

IMPORTANT: DJANGO_SETTINGS_MODULE must be set *before* importing any Django
modules or application code that touches Django settings/models. The previous
version imported `chatbot.consumers` first, which indirectly imported Django
auth models and triggered the ImproperlyConfigured error when running daphne.
"""

import os

# Set settings module early to avoid ImproperlyConfigured during initial imports
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_chatbot.settings")

from django.core.asgi import get_asgi_application  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.auth import AuthMiddlewareStack  # noqa: E402
from django.urls import path  # noqa: E402

django_app = get_asgi_application()

# Import ChatConsumer only after Django setup completes so models are registered.
from chatbot.consumers import ChatConsumer  # noqa: E402  pylint: disable=wrong-import-position

websocket_urlpatterns = [
	path('ws/chat/', ChatConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
	'http': django_app,
	'websocket': AuthMiddlewareStack(
		URLRouter(websocket_urlpatterns)
	),
})
