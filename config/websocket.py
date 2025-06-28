from channels.routing import ProtocolTypeRouter
from channels.routing import URLRouter
from django.urls import path

from simlane.core.middleware import CombinedAuthMiddleware
from simlane.sim.consumers import AppConsumer

websocket_application = ProtocolTypeRouter(
    {
        "websocket": CombinedAuthMiddleware(
            URLRouter(
                [
                    path("ws/app/", AppConsumer.as_asgi()),
                ]
            ),
        ),
    }
)
