from django.conf import settings
from django.db import models


class Garage61SyncLog(models.Model):
    """Log API synchronization activities"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    endpoint = models.CharField(max_length=200)
    method = models.CharField(max_length=10, default="GET")
    status_code = models.IntegerField(null=True, blank=True)
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    response_time_ms = models.IntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Garage61 Sync Log"
        verbose_name_plural = "Garage61 Sync Logs"
        ordering = ["-timestamp"]

    def __str__(self):
        status = "✅" if self.success else "❌"
        return f"{status} {self.endpoint} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
