import logging

import discord
from allauth.socialaccount.models import SocialAccount
from asgiref.sync import sync_to_async
from discord.ext import commands
from django.conf import settings
from django.core.management.base import BaseCommand

from simlane.discord.models import BotCommand
from simlane.discord.models import DiscordGuild
from simlane.discord.utils import get_club_for_guild, get_django_user_from_discord_id
from simlane.teams.models import ClubMember, ClubRole

logger = logging.getLogger(__name__)


class SimlaneBot(commands.Bot):
    """Custom Discord bot for Simlane"""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,  # We'll create a custom help command
        )

    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info("%s has connected to Discord!", self.user)
        logger.info("Bot is in %s guilds", len(self.guilds))

        # Sync guild information
        await self.sync_guilds()

    async def on_guild_join(self, guild):
        """Called when bot joins a new guild"""
        logger.info("Joined guild: %s (%s)", guild.name, guild.id)
        await self.create_or_update_guild(guild)

    async def on_guild_remove(self, guild):
        """Called when bot leaves a guild"""
        logger.info("Left guild: %s (%s)", guild.name, guild.id)
        await self.deactivate_guild(guild.id)

    async def on_member_join(self, member):
        """
        Called when a user joins a guild. If the guild is linked to a club and the user has a Simlane account, create a ClubMember.
        """
        # Only handle real users (not bots)
        if member.bot:
            return

        # Get the club for this guild
        club = await sync_to_async(get_club_for_guild)(str(member.guild.id))
        if not club:
            return  # Guild not linked to a club

        # Get the Django user for this Discord user
        user = await sync_to_async(get_django_user_from_discord_id)(str(member.id))
        if not user:
            return  # User not registered on Simlane

        # Create ClubMember if not already present
        def create_club_member():
            obj, created = ClubMember.objects.get_or_create(
                user=user,
                club=club,
                defaults={"role": ClubRole.MEMBER},
            )
            return created

        created = await sync_to_async(create_club_member)()
        display_name = getattr(user, 'name', None) or getattr(user, 'username', None) or str(user.pk)
        if created:
            logger.info(f"Added {display_name} as ClubMember to {club.name} via Discord join event.")
        else:
            logger.info(f"{display_name} is already a ClubMember of {club.name}.")

    @sync_to_async
    def create_or_update_guild(self, guild):
        """Create or update guild in database"""
        discord_guild, created = DiscordGuild.objects.get_or_create(
            guild_id=str(guild.id),
            defaults={
                "name": guild.name,
                "is_active": True,
            },
        )
        if not created and discord_guild.name != guild.name:
            discord_guild.name = guild.name
            discord_guild.save()

        return discord_guild

    @sync_to_async
    def deactivate_guild(self, guild_id):
        """Deactivate guild in database"""
        try:
            guild = DiscordGuild.objects.get(guild_id=str(guild_id))
            guild.is_active = False
            guild.save()
        except DiscordGuild.DoesNotExist:
            pass

    @sync_to_async
    def log_command(
        self,
        ctx,
        command_name,
        success=True,  # noqa: FBT002
        error_message="",
        arguments=None,
    ):
        """Log command execution"""
        try:
            discord_guild = DiscordGuild.objects.get(guild_id=str(ctx.guild.id))

            BotCommand.objects.create(
                command_name=command_name,
                discord_user_id=str(ctx.author.id),
                username=ctx.author.name,
                guild=discord_guild,
                channel_id=str(ctx.channel.id),
                arguments=arguments or {},
                success=success,
                error_message=error_message,
            )
        except DiscordGuild.DoesNotExist:
            logger.warning("Could not log command %s - guild not found", command_name)

    async def sync_guilds(self):
        """Sync all current guilds with database"""
        for guild in self.guilds:
            await self.create_or_update_guild(guild)

    async def setup_hook(self):
        """Load dynamic cogs before the bot logs in completely."""
        try:
            from simlane.discord.bot.cogs.join_requests import JoinRequestCog
            await self.add_cog(JoinRequestCog(self))
            logger.info("JoinRequestCog loaded via setup_hook")
        except Exception as exc:
            logger.error("Failed to load JoinRequestCog in setup_hook: %s", exc)


# Bot instance
bot = SimlaneBot()

# Additional static cogs can be loaded here if needed (setup_hook already handles join-requests)


@bot.command(name="ping")
async def ping(ctx):
    """Simple ping command"""
    await ctx.send("Pong! 🏓")
    await bot.log_command(ctx, "ping")


@bot.command(name="info")
async def info(ctx):
    """Bot information"""
    embed = discord.Embed(
        title="Simlane Bot",
        description="Discord bot for Simlane racing community",
        color=discord.Color.blue(),
    )
    embed.add_field(name="Guilds", value=len(bot.guilds), inline=True)
    embed.add_field(name="Users", value=len(bot.users), inline=True)
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)

    await ctx.send(embed=embed)
    await bot.log_command(ctx, "info")


@bot.command(name="help")
async def help_command(ctx):
    """Custom help command"""
    embed = discord.Embed(
        title="Simlane Bot Commands",
        description="Available commands for the Simlane racing bot",
        color=discord.Color.green(),
    )

    embed.add_field(
        name="!ping",
        value="Check if the bot is responding",
        inline=False,
    )
    embed.add_field(
        name="!info",
        value="Display bot information and statistics",
        inline=False,
    )
    embed.add_field(
        name="!club",
        value="Display information about your racing club",
        inline=False,
    )
    embed.add_field(
        name="!link",
        value="Link your Discord account to your Simlane profile",
        inline=False,
    )

    await ctx.send(embed=embed)
    await bot.log_command(ctx, "help")


@bot.command(name="club")
async def club_info(ctx):
    """Display club information for this Discord server"""
    try:
        # Get the Discord guild from database
        discord_guild = await sync_to_async(DiscordGuild.objects.get)(
            guild_id=str(ctx.guild.id),
        )

        if discord_guild.club:
            club = discord_guild.club
            embed = discord.Embed(
                title=f"🏁 {club.name}",
                description=club.description or "No description available",
                color=discord.Color.gold(),
            )

            if club.website:
                embed.add_field(name="Website", value=club.website, inline=True)

            embed.add_field(
                name="Active",
                value="✅ Yes" if club.is_active else "❌ No",
                inline=True,
            )
            embed.add_field(
                name="Created",
                value=club.created_at.strftime("%Y-%m-%d"),
                inline=True,
            )

            if club.logo_url:
                embed.set_thumbnail(url=club.logo_url)

            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="No Club Linked",
                description="This Discord server is not linked to any racing club yet.",
                color=discord.Color.orange(),
            )
            await ctx.send(embed=embed)

        await bot.log_command(ctx, "club")

    except DiscordGuild.DoesNotExist:
        embed = discord.Embed(
            title="Server Not Registered",
            description="This Discord server is not registered with the bot yet.",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)
        await bot.log_command(
            ctx,
            "club",
            success=False,
            error_message="Guild not found",
        )


@bot.command(name="link")
async def link_account(ctx):
    """Show instructions for linking Discord account to Simlane profile"""
    # Check if user is already linked
    social_account = await sync_to_async(
        lambda: SocialAccount.objects.filter(
            provider="discord",
            uid=str(ctx.author.id),
        ).first(),
    )()

    if social_account:
        embed = discord.Embed(
            title="Account Already Linked! ✅",
            description=(
                f"Your Discord account is already linked to "
                f"**{social_account.user.username}**"
            ),
            color=discord.Color.green(),
        )
        embed.add_field(
            name="Profile",
            value=(
                f"Username: {social_account.user.username}\n"
                f"Email: {social_account.user.email}"
            ),
            inline=False,
        )
    else:
        # Get the website URL from settings or construct it
        website_url = "https://simlane.app"  # Replace with your actual domain
        login_url = f"{website_url}/accounts/discord/login/"

        embed = discord.Embed(
            title="Link Your Discord Account 🔗",
            description=(
                "Link your Discord account to your Simlane profile to "
                "access all features!"
            ),
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="How to Link",
            value=(
                f"1. Go to [Simlane Login]({login_url})\n"
                "2. Click 'Login with Discord'\n"
                "3. Authorize the connection\n"
                "4. You're all set!"
            ),
            inline=False,
        )
        embed.add_field(
            name="Benefits",
            value=(
                "• Access your racing data\n"
                "• Join club events\n"
                "• Track your progress\n"
                "• Get personalized recommendations"
            ),
            inline=False,
        )

    await ctx.send(embed=embed)
    await bot.log_command(ctx, "link")


@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    if isinstance(error, commands.CommandNotFound):
        embed = discord.Embed(
            title="Command Not Found",
            description=(
                f"The command `{ctx.message.content}` was not found. "
                "Use `!help` to see available commands."
            ),
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)
    else:
        logger.error("Command error: %s", error)
        embed = discord.Embed(
            title="Error",
            description="An error occurred while processing your command.",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)

        # Log the error
        await bot.log_command(
            ctx,
            ctx.command.name if ctx.command else "unknown",
            success=False,
            error_message=str(error),
        )


class Command(BaseCommand):
    help = "Run the Discord bot"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dev",
            action="store_true",
            help="Run in development mode with additional logging",
        )

    def handle(self, *args, **options):
        if options["dev"]:
            logging.basicConfig(level=logging.DEBUG)
            logger.setLevel(logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)
            logger.setLevel(logging.INFO)

        # Check if Discord token is configured
        if not hasattr(settings, "DISCORD_BOT_TOKEN") or not settings.DISCORD_BOT_TOKEN:
            self.stdout.write(
                self.style.ERROR("DISCORD_BOT_TOKEN is not configured in settings"),
            )
            return

        self.stdout.write(
            self.style.SUCCESS("Starting Discord bot..."),
        )

        try:
            # Run the bot
            bot.run(settings.DISCORD_BOT_TOKEN)
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.SUCCESS("Discord bot stopped"),
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Discord bot error: {e}"),
            )
            raise
