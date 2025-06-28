import json

from channels.generic.websocket import AsyncWebsocketConsumer


class AppConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if user.is_anonymous:
            await self.close()
            return
        self.user_group = f"user_{user.id}"
        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "user_group"):
            await self.channel_layer.group_discard(self.user_group, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if text_data:
            data = json.loads(text_data)
            msg_type = data.get("type")
            if msg_type == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))
            # Add more client-initiated message types here

    async def sync_status(self, event):
        # Called by group_send from Celery or Django
        await self.send(
            text_data=json.dumps(
                {
                    "type": "sync_status",
                    "status": event["status"],
                    "profile_id": event.get("profile_id"),
                }
            )
        )

    # Add more server-initiated message handlers here (e.g., chat_message, notification)
