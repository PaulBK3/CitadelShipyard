import discord
from discord.ext import commands
from discord import app_commands
import config
import database
import utils
from views.ship_views import ShipRequestView
from views.port_views import PortRequestView
from naval_rules import can_build_ship, get_modified_ship_cost


async def ship_log_channel(guild):
    for channel in guild.text_channels:
        if channel.name == config.SHIP_LOG_CHANNEL:
            return channel
    return None


async def port_log_channel(guild):
    for channel in guild.text_channels:
        if channel.name == config.SHIP_LOG_CHANNEL:
            return channel
    return None


class ShipsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="buy_ship", description="Request ship construction")
    @app_commands.choices(ship_type=utils.SHIP_CHOICES)
    @app_commands.describe(
        ship_type="Type of ship",
        amount="How many ships to build",
        comment="Optional note for staff"
    )
    async def buy_ship(
        self,
        interaction: discord.Interaction,
        ship_type: app_commands.Choice[str],
        amount: app_commands.Range[int, 1, 100],
        comment: str | None = None
    ):

        house = utils.get_house(interaction.user)
        if not house:
            await interaction.response.send_message("No valid house role found.", ephemeral=True)
            return

        allowed, reason = can_build_ship(house, ship_type.value)
        if not allowed:
            await interaction.response.send_message(reason, ephemeral=True)
            return

        single_cost = get_modified_ship_cost(house, ship_type.value)
        total_cost = single_cost * amount

        log = await ship_log_channel(interaction.guild)
        if not log:
            await interaction.response.send_message("Ship request channel not found.", ephemeral=True)
            return

        request_id = database.create_ship_request(
            interaction.user.id,
            house,
            ship_type.value,
            amount,
            comment
        )

        embed = discord.Embed(
            title="New Ship Request",
            description="Waiting for staff approval."
        )
        embed.add_field(name="Player", value=interaction.user.mention, inline=True)
        embed.add_field(name="House", value=house, inline=True)
        embed.add_field(name="Ship", value=ship_type.name, inline=True)
        embed.add_field(name="Amount", value=str(amount), inline=True)
        embed.add_field(name="Total Cost", value=str(total_cost), inline=True)

        if comment:
            embed.add_field(name="Player Comment", value=comment, inline=False)

        embed.set_footer(text=f"Request ID: {request_id}")

        await log.send(embed=embed, view=ShipRequestView(self.bot))
        await interaction.response.send_message("Ship request submitted.", ephemeral=True)

    @app_commands.command(name="request_port_upgrade", description="Request a port level upgrade")
    @app_commands.describe(
        requested_level="Sum of new port capacity",
        highest_level="Highest port level available",
        comment="Optional note for staff"
    )
    async def request_port_upgrade(
        self,
        interaction: discord.Interaction,
        requested_level: app_commands.Range[int, 5, 1000],
        highest_level: app_commands.Range[int, 1, 10] | None = 1,
        comment: str | None = None
    ):
        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.response.send_message("You need the Ship Charta role.", ephemeral=True)
            return

        house = utils.get_house(interaction.user)
        if not house:
            await interaction.response.send_message("No valid house role found.", ephemeral=True)
            return

        log = await port_log_channel(interaction.guild)
        if not log:
            await interaction.response.send_message("Port request channel not found.", ephemeral=True)
            return

        request_id = database.create_port_request(
            interaction.user.id,
            house,
            requested_level,
            highest_level,
            comment
        )

        embed = discord.Embed(
            title="New Port Upgrade Request",
            description="Waiting for staff approval."
        )
        embed.add_field(name="Player", value=interaction.user.mention, inline=True)
        embed.add_field(name="House", value=house, inline=True)
        embed.add_field(name="Requested Level", value=str(requested_level), inline=True)
        embed.add_field(name="Highest Level", value=str(highest_level), inline=True)
        if comment:
            embed.add_field(name="Player Comment", value=comment, inline=False)

        embed.set_footer(text=f"Port Request ID: {request_id}")

        await log.send(embed=embed, view=PortRequestView(self.bot))
        await interaction.response.send_message("Port upgrade request submitted.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(ShipsCog(bot), guild=discord.Object(id=config.GUILD_ID))