"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

import django
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()


from channels.auth import AuthMiddlewareStack #noqa
from channels.routing import ProtocolTypeRouter, URLRouter #noqa

import code_cup.routing #noqa

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": AuthMiddlewareStack(
            URLRouter(code_cup.routing.websocket_urlpatterns)
        ),
    }
)
