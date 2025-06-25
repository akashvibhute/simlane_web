from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path
from simlane.sim.consumers import AppConsumer
from simlane.core.middleware import CombinedAuthMiddleware

websocket_application = ProtocolTypeRouter({
    "websocket": CombinedAuthMiddleware(
        URLRouter([
            path("ws/app/", AppConsumer.as_asgi()),
        ])
    ),
})
