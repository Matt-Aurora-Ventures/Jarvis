"""
Discord Bot for Jarvis Community.

Commands:
- /leaderboard - Show top 10 traders
- /myprofile - Show your profile
- /stats - Weekly/monthly stats
- /vote FEATURE - Vote on features
- /challenge STATUS - Show monthly challenge standings

Alerts:
- User makes top 10
- Achievement badge earned
- Challenge updates

Integration:
- Linked with Telegram bot (same user system)
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("jarvis.discord")

# Discord.py import with graceful fallback
DISCORD_AVAILABLE = False
discord = None
tasks = None

try:
    import discord
    from discord import app_commands
    from discord.ext import commands, tasks
    DISCORD_AVAILABLE = True
except ImportError:
    logger.warning("discord.py not installed. Install with: pip install discord.py")


class JarvisDiscordBot:
    """
    Discord bot for Jarvis community features.

    Usage:
        bot = JarvisDiscordBot(token="YOUR_TOKEN")
        await bot.start()
    """

    def __init__(
        self,
        token: str = None,
        guild_id: int = None,
    ):
        """
        Initialize the Discord bot.

        Args:
            token: Discord bot token (or from env DISCORD_BOT_TOKEN)
            guild_id: Optional guild ID for faster command syncing
        """
        if not DISCORD_AVAILABLE:
            raise ImportError("discord.py is required. Install with: pip install discord.py")

        self.token = token or os.getenv("DISCORD_BOT_TOKEN")
        self.guild_id = guild_id or (int(os.getenv("DISCORD_GUILD_ID")) if os.getenv("DISCORD_GUILD_ID") else None)

        if not self.token:
            raise ValueError("Discord bot token is required")

        # Initialize bot
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        self.bot = commands.Bot(
            command_prefix="!",
            intents=intents,
            description="Jarvis Community Bot",
        )

        # Track linked users (Discord ID -> Jarvis user ID)
        self._linked_users = {}

        # Setup events and commands
        self._setup_events()
        self._setup_commands()

    def _setup_events(self):
        """Setup bot event handlers."""

        @self.bot.event
        async def on_ready():
            logger.info(f"Discord bot logged in as {self.bot.user}")

            # Sync commands
            if self.guild_id:
                guild = discord.Object(id=self.guild_id)
                self.bot.tree.copy_global_to(guild=guild)
                await self.bot.tree.sync(guild=guild)
            else:
                await self.bot.tree.sync()

            logger.info("Commands synced")

            # Start background tasks
            if not self.check_achievements.is_running():
                self.check_achievements.start()

        @self.bot.event
        async def on_member_join(member):
            logger.info(f"New member joined: {member.name}")
            # Welcome message could go here

    def _setup_commands(self):
        """Setup slash commands."""
        tree = self.bot.tree

        @tree.command(name="leaderboard", description="Show top 10 traders")
        @app_commands.describe(
            period="Time period: overall, weekly, monthly",
            metric="Ranking metric: profit, win_rate, trades"
        )
        async def leaderboard(
            interaction: discord.Interaction,
            period: str = "overall",
            metric: str = "profit",
        ):
            await interaction.response.defer()

            try:
                from core.community.leaderboard import Leaderboard
                lb = Leaderboard()
                rankings = lb.get_rankings(by=metric, period=period, limit=10)

                if not rankings:
                    await interaction.followup.send("No rankings available yet.")
                    return

                # Build embed
                embed = discord.Embed(
                    title=f"Leaderboard - {period.title()} ({metric.replace('_', ' ').title()})",
                    color=discord.Color.gold(),
                    timestamp=datetime.now(timezone.utc),
                )

                leaderboard_text = ""
                medals = ["1.", "2.", "3."]

                for i, entry in enumerate(rankings):
                    rank_prefix = medals[i] if i < 3 else f"{i+1}."
                    username = entry.get("username", "Anonymous")
                    pnl = entry.get("total_pnl", 0)
                    win_rate = entry.get("win_rate", 0) * 100

                    leaderboard_text += f"{rank_prefix} **{username}** - ${pnl:,.2f} ({win_rate:.1f}% WR)\n"

                embed.description = leaderboard_text
                embed.set_footer(text="Updated")

                await interaction.followup.send(embed=embed)

            except Exception as e:
                logger.error(f"Leaderboard error: {e}")
                await interaction.followup.send(f"Error fetching leaderboard: {str(e)}")

        @tree.command(name="myprofile", description="Show your trading profile")
        async def myprofile(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)

            try:
                user_id = self._get_linked_user(interaction.user.id)
                if not user_id:
                    await interaction.followup.send(
                        "Your Discord account is not linked. Use `/link` to connect your Jarvis account.",
                        ephemeral=True,
                    )
                    return

                from core.community.user_profile import UserProfileManager
                from core.community.achievements import AchievementManager

                profile_mgr = UserProfileManager()
                achievements = AchievementManager()

                profile = profile_mgr.get_profile(user_id)
                badges = achievements.get_user_badges_detailed(user_id)

                if not profile:
                    await interaction.followup.send("Profile not found.", ephemeral=True)
                    return

                embed = discord.Embed(
                    title=f"Profile: {profile['username']}",
                    color=discord.Color.blue(),
                )

                embed.add_field(
                    name="Stats",
                    value=f"PnL: ${profile.get('total_pnl', 0):,.2f}\n"
                          f"Win Rate: {profile.get('win_rate', 0)*100:.1f}%\n"
                          f"Total Trades: {profile.get('total_trades', 0)}",
                    inline=True,
                )

                if badges:
                    badge_text = ", ".join(b["name"] for b in badges[:5])
                    if len(badges) > 5:
                        badge_text += f" +{len(badges)-5} more"
                    embed.add_field(name="Badges", value=badge_text, inline=True)

                embed.add_field(
                    name="Privacy",
                    value="Public" if profile.get("is_public") else "Private",
                    inline=True,
                )

                await interaction.followup.send(embed=embed, ephemeral=True)

            except Exception as e:
                logger.error(f"Profile error: {e}")
                await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)

        @tree.command(name="stats", description="Show trading statistics")
        @app_commands.describe(period="Time period: weekly, monthly, all")
        async def stats(
            interaction: discord.Interaction,
            period: str = "weekly",
        ):
            await interaction.response.defer()

            try:
                from core.community.leaderboard import Leaderboard
                lb = Leaderboard()

                rankings = lb.get_rankings(period=period, limit=5)
                total_traders = len(lb.get_rankings(period=period, limit=1000))

                embed = discord.Embed(
                    title=f"{period.title()} Statistics",
                    color=discord.Color.green(),
                    timestamp=datetime.now(timezone.utc),
                )

                # Top performer
                if rankings:
                    top = rankings[0]
                    embed.add_field(
                        name="Top Trader",
                        value=f"**{top['username']}** with ${top['total_pnl']:,.2f}",
                        inline=False,
                    )

                embed.add_field(
                    name="Active Traders",
                    value=str(total_traders),
                    inline=True,
                )

                await interaction.followup.send(embed=embed)

            except Exception as e:
                logger.error(f"Stats error: {e}")
                await interaction.followup.send(f"Error: {str(e)}")

        @tree.command(name="vote", description="Vote on community features")
        @app_commands.describe(option="What to vote for")
        async def vote(
            interaction: discord.Interaction,
            option: str,
        ):
            await interaction.response.defer(ephemeral=True)

            try:
                user_id = self._get_linked_user(interaction.user.id)
                if not user_id:
                    await interaction.followup.send(
                        "Link your account first with `/link`",
                        ephemeral=True,
                    )
                    return

                from core.community.voting import VotingManager
                voting = VotingManager()

                # Get active polls
                polls = voting.get_active_polls()
                if not polls:
                    await interaction.followup.send(
                        "No active polls right now.",
                        ephemeral=True,
                    )
                    return

                # Find poll with matching option
                voted = False
                for poll in polls:
                    if option in poll["options"]:
                        result = voting.cast_vote(poll["poll_id"], user_id, option)
                        if result["success"]:
                            await interaction.followup.send(
                                f"Voted for **{option}** in '{poll['title']}'!",
                                ephemeral=True,
                            )
                            voted = True
                            break
                        else:
                            await interaction.followup.send(
                                f"Could not vote: {result['message']}",
                                ephemeral=True,
                            )
                            return

                if not voted:
                    # Show available options
                    all_options = []
                    for poll in polls:
                        all_options.extend(poll["options"])

                    await interaction.followup.send(
                        f"'{option}' not found in active polls.\n"
                        f"Available options: {', '.join(set(all_options))}",
                        ephemeral=True,
                    )

            except Exception as e:
                logger.error(f"Vote error: {e}")
                await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)

        @tree.command(name="challenge", description="Show challenge standings")
        @app_commands.describe(status="Filter: active, completed, all")
        async def challenge(
            interaction: discord.Interaction,
            status: str = "active",
        ):
            await interaction.response.defer()

            try:
                from core.community.challenges import ChallengeManager
                challenges_mgr = ChallengeManager()

                if status == "active":
                    challenges = challenges_mgr.get_active_challenges()
                else:
                    # Get all challenges (would need a method for this)
                    challenges = challenges_mgr.get_active_challenges()

                if not challenges:
                    await interaction.followup.send("No active challenges.")
                    return

                for ch in challenges[:3]:  # Show up to 3
                    embed = discord.Embed(
                        title=ch["title"],
                        description=ch.get("description", ""),
                        color=discord.Color.orange(),
                    )

                    # Get leaderboard
                    lb = challenges_mgr.get_challenge_leaderboard(ch["challenge_id"], limit=5)

                    if lb:
                        lb_text = ""
                        for i, entry in enumerate(lb):
                            lb_text += f"{i+1}. {entry['username']} - {entry['score']:.2f}\n"
                        embed.add_field(name="Top 5", value=lb_text or "No participants yet")

                    embed.add_field(name="Ends", value=ch["end_date"][:10], inline=True)

                    await interaction.followup.send(embed=embed)

            except Exception as e:
                logger.error(f"Challenge error: {e}")
                await interaction.followup.send(f"Error: {str(e)}")

        @tree.command(name="link", description="Link your Discord to Jarvis account")
        @app_commands.describe(jarvis_user_id="Your Jarvis user ID")
        async def link(
            interaction: discord.Interaction,
            jarvis_user_id: str,
        ):
            await interaction.response.defer(ephemeral=True)

            # Store link (in production, verify ownership first)
            self._linked_users[interaction.user.id] = jarvis_user_id

            await interaction.followup.send(
                f"Linked Discord account to Jarvis user: {jarvis_user_id}",
                ephemeral=True,
            )

        @tree.command(name="badges", description="Show your badges")
        async def badges(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)

            try:
                user_id = self._get_linked_user(interaction.user.id)
                if not user_id:
                    await interaction.followup.send(
                        "Link your account first with `/link`",
                        ephemeral=True,
                    )
                    return

                from core.community.achievements import AchievementManager
                achievements = AchievementManager()

                badge_list = achievements.get_user_badges_detailed(user_id)

                if not badge_list:
                    await interaction.followup.send(
                        "No badges yet. Keep trading to earn them!",
                        ephemeral=True,
                    )
                    return

                embed = discord.Embed(
                    title="Your Badges",
                    color=discord.Color.purple(),
                )

                for badge in badge_list[:10]:
                    embed.add_field(
                        name=badge["name"],
                        value=badge["description"],
                        inline=True,
                    )

                embed.set_footer(text=f"Total: {len(badge_list)} badges")

                await interaction.followup.send(embed=embed, ephemeral=True)

            except Exception as e:
                logger.error(f"Badges error: {e}")
                await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)

    def _get_linked_user(self, discord_id: int) -> Optional[str]:
        """Get Jarvis user ID from Discord ID."""
        return self._linked_users.get(discord_id)

    @property
    def check_achievements(self):
        """Background task to check for new achievements to announce."""
        if not hasattr(self, '_check_achievements_task'):
            @tasks.loop(minutes=30)
            async def _check():
                # This would check for unnotified achievements and send alerts
                pass
            self._check_achievements_task = _check
        return self._check_achievements_task

    async def send_achievement_alert(
        self,
        channel_id: int,
        user_id: str,
        badge_name: str,
        badge_description: str,
    ):
        """Send achievement alert to a channel."""
        try:
            channel = self.bot.get_channel(channel_id)
            if channel:
                embed = discord.Embed(
                    title="New Achievement!",
                    description=f"**{user_id}** earned the **{badge_name}** badge!\n\n{badge_description}",
                    color=discord.Color.gold(),
                )
                await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to send achievement alert: {e}")

    async def send_leaderboard_alert(
        self,
        channel_id: int,
        user_id: str,
        rank: int,
    ):
        """Send alert when user enters top 10."""
        try:
            channel = self.bot.get_channel(channel_id)
            if channel:
                embed = discord.Embed(
                    title="Leaderboard Update!",
                    description=f"**{user_id}** has entered the **Top 10** at rank #{rank}!",
                    color=discord.Color.blue(),
                )
                await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to send leaderboard alert: {e}")

    async def start(self):
        """Start the Discord bot."""
        logger.info("Starting Discord bot...")
        await self.bot.start(self.token)

    async def close(self):
        """Close the Discord bot."""
        await self.bot.close()


# Convenience function to run bot
async def run_discord_bot():
    """Run the Discord bot."""
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        logger.error("DISCORD_BOT_TOKEN not set")
        return

    bot = JarvisDiscordBot(token=token)
    await bot.start()


if __name__ == "__main__":
    asyncio.run(run_discord_bot())
