from allauth.socialaccount.models import SocialAccount
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render

from .models import BotCommand
from .models import DiscordGuild
from .utils import get_bot_status_info


@staff_member_required
def bot_status(request):
    """Display Discord bot status page"""
    status_info = get_bot_status_info()

    context = {
        **status_info,
        "recent_commands": BotCommand.objects.select_related("guild")[:10],
        "guilds": DiscordGuild.objects.filter(is_active=True).select_related("club"),
        "linked_users": SocialAccount.objects.filter(provider="discord").select_related(
            "user",
        )[:20],
    }

    if request.headers.get("Accept") == "application/json":
        return JsonResponse(
            {
                "status": "configured" if context["configured"] else "not_configured",
                "guilds_count": context["guilds_count"],
                "discord_users_count": context["discord_users_count"],
            },
        )

    return render(request, "discord/bot_status.html", context)
