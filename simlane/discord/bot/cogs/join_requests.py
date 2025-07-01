from __future__ import annotations

"""Discord Cog allowing club admins to approve / reject join-requests from within Discord.

Loaded by run_discord_bot management command.  Relies on existing Celery
wrapper tasks to update embeds & perform side-effects.
"""

import asyncio
import logging
from typing import Optional

import discord
from discord.ext import commands
from asgiref.sync import sync_to_async

from simlane.teams.models import ClubJoinRequest
from simlane.discord.models import ClubDiscordSettings
from simlane.discord.tasks import (
    send_join_request_approved_notification,
    send_join_request_rejected_notification,
)

logger = logging.getLogger(__name__)


class JoinRequestCog(commands.Cog):
    """Commands: !approve  |  !reject <reason> (must reply to bot embed)"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------

    async def _get_referenced_join_request(
        self, ctx: commands.Context
    ) -> Optional[ClubJoinRequest]:
        """Return the ClubJoinRequest that matches the replied-to message."""
        if ctx.message.reference is None or ctx.message.reference.message_id is None:
            await ctx.reply(
                "ℹ️  Please **reply** to the join-request message first.",
                mention_author=False,
            )
            return None

        ref_id = ctx.message.reference.message_id
        jr = await sync_to_async(
            lambda: ClubJoinRequest.objects.filter(discord_message_id=str(ref_id)).first()
        )()
        if jr is None:
            await ctx.reply("❓ Couldn't locate a join-request for that message.", mention_author=False)
        return jr

    async def _has_permission(self, ctx: commands.Context, jr: ClubJoinRequest) -> bool:
        """Check that invoking member has an allowed role from settings."""
        club_id = jr.club_id  # simple int/uuid, safe to access
        try:
            settings = await sync_to_async(ClubDiscordSettings.objects.get)(club_id=club_id)
        except ClubDiscordSettings.DoesNotExist:
            await ctx.reply("⚙️ Discord settings not configured for this club.", mention_author=False)
            return False

        allowed_ids = {
            settings.admin_role_id,
            settings.teams_manager_role_id,
        } - {"", None}
        if not allowed_ids:
            # Fall back to allowing anyone (unlikely in production)
            return True

        invoker_role_ids = {str(r.id) for r in ctx.author.roles if r}
        if invoker_role_ids.isdisjoint(allowed_ids):
            await ctx.reply("⛔ You don't have permission to action join-requests.", mention_author=False)
            return False
        return True

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    @commands.command(name="approve")
    async def approve(self, ctx: commands.Context):
        """Approve the referenced join request."""
        try:
            jr = await self._get_referenced_join_request(ctx)
            if not jr:
                return
            if not await self._has_permission(ctx, jr):
                return
            if jr.status != "pending":
                await ctx.reply(f"Already **{jr.status}**.", mention_author=False)
                return

            await sync_to_async(jr.approve, thread_sensitive=False)(None)
            send_join_request_approved_notification.delay(jr.id, None)
            await ctx.reply(
                f"✅ Approved **{jr.user.username}**.", mention_author=False,
            )
        except Exception as exc:
            logger.exception("Error approving join request: %s", exc)
            await ctx.reply("❌ Error processing approval.", mention_author=False)

    @commands.command(name="reject")
    async def reject(self, ctx: commands.Context, *, reason: str = ""):
        """Reject the referenced join request, optional reason."""
        try:
            jr = await self._get_referenced_join_request(ctx)
            if not jr:
                return
            if not await self._has_permission(ctx, jr):
                return
            if jr.status != "pending":
                await ctx.reply(f"Already **{jr.status}**.", mention_author=False)
                return

            await sync_to_async(jr.reject, thread_sensitive=False)(None, reason)
            send_join_request_rejected_notification.delay(jr.id)
            await ctx.reply("❌ Rejected.", mention_author=False)
        except Exception as exc:
            logger.exception("Error rejecting join request: %s", exc)
            await ctx.reply("❌ Error processing rejection.", mention_author=False)


async def setup(bot: commands.Bot):
    """Cog loader used by discord.py's load_extension."""
    await bot.add_cog(JoinRequestCog(bot)) 