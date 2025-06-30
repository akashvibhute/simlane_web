from allauth.socialaccount.models import SocialAccount
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .models import BotCommand
from .models import DiscordGuild
from .utils import get_bot_status_info, link_discord_guild_to_club


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


@require_GET
def bot_oauth_callback(request):
    """
    Handle Discord bot OAuth2 callback.
    Links the Discord guild to the club using the state (club_id) and guild_id from query params.
    """
    club_id = request.GET.get("state")
    guild_id = request.GET.get("guild_id")
    error = request.GET.get("error")

    context = {}
    if error:
        context["error"] = error
        return render(request, "discord/bot_oauth_callback.html", context, status=400)

    if not club_id or not guild_id:
        return HttpResponseBadRequest("Missing required parameters: state (club_id) and guild_id.")

    result = link_discord_guild_to_club(guild_id, club_id)
    if result:
        context["success"] = True
        context["guild_id"] = guild_id
        context["club_id"] = club_id
    else:
        context["success"] = False
        context["guild_id"] = guild_id
        context["club_id"] = club_id
        context["error"] = "Could not link Discord guild to club. Please contact support."

    return render(request, "discord/bot_oauth_callback.html", context)
