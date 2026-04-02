import os
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_asgi_app = get_asgi_application()

# Import AFTER django setup to avoid AppRegistryNotReady
from apps.terminal.middleware import JWTAuthMiddleware
import apps.terminal.routing

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddleware(
        URLRouter(
            apps.terminal.routing.websocket_urlpatterns
        )
    ),
})

