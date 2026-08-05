from django.urls import re_path
from .consumers import TerminalConsumer
from .warroom_consumer import WarRoomConsumer
from apps.vmware_sim.baremetal_consumer import BaremetalConsumer

websocket_urlpatterns = [
    re_path(
        r"ws/terminal/(?P<session_id>[0-9a-f-]+)/$",
        TerminalConsumer.as_asgi(),
    ),
    # Multiplayer war-room. Shares the SAME AllowedHostsOriginValidator +
    # JWTAuthMiddleware wrapper as the terminal route (see config/asgi.py) —
    # no security is weakened; auth/origin validation are reused as-is.
    re_path(
        r"ws/warroom/(?P<room_key>[0-9a-f-]+)/$",
        WarRoomConsumer.as_asgi(),
    ),
    # Live bare-metal Lab Environment state push (MAAS/LXD/KVM). Same auth
    # wrapper as the terminal/war-room routes.
    re_path(
        r"ws/baremetal/(?P<session_id>[0-9a-f-]+)/$",
        BaremetalConsumer.as_asgi(),
    ),
]
