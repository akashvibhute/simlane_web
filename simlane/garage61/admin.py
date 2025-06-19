from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from .models import Garage61SyncLog


@admin.register(Garage61SyncLog)
class Garage61SyncLogAdmin(ModelAdmin):
    list_display = [
        "status_icon",
        "endpoint",
        "user",
        "method",
        "status_code",
        "response_time_ms",
        "timestamp",
    ]
    list_filter = ["success", "method", "status_code", "timestamp"]
    search_fields = ["endpoint", "user__username", "error_message"]
    readonly_fields = ["timestamp"]
    date_hierarchy = "timestamp"

    @admin.display(
        description="Status",
    )
    def status_icon(self, obj):
        if obj.success:
            return format_html('<span style="color: green;">✅</span>')
        return format_html('<span style="color: red;">❌</span>')

    def has_add_permission(self, request):
        return False  # These are created automatically
