import discord
from discord.ext import commands
from discord import app_commands
import config
import database
from views.ship_views import ShipRequestView
from views.port_views import PortRequestView


def has_role(user, role_name):
    return any(role.name == role_name for role in user.roles)


def get_house(member: discord.Member):
    for role in member.roles:
        for prefix in config.HOUSE_ROLE_FILTER:
            if role.name.startswith(prefix):
                return role.name
    return None


async def ship_log_channel(guild):
    for channel in guild.text_channels:
        if channel.name == config.SHIP_LOG_CHANNEL:
            return channel
    return None


async def port_log_channel(guild):
    for channel in guild.text_channels:
        if channel.name == config.PORT_LOG_CHANNEL:
            return channel
    return None


def ship_allowed_for_house(house_name, ship_type):
    house = database.get_house(house_name)
    if not house:
        return True

    culture = house.get("culture")
    ship_data = config.SHIPS.get(ship_type, {})
    allowed = ship_data.get("cultures")

    if not allowed:
        return True

    return culture in allowed


SHIP_CHOICES = [
    app_commands.Choice(name=data["name"], value=key)
    for key, data in config.SHIPS.items()
]


class ShipsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="buy_ship", description="Request ship construction")
    @app_commands.choices(ship_type=SHIP_CHOICES)
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
        if not has_role(interaction.user, config.SHIP_CHARTA_ROLE):
            await interaction.response.send_message("You need the Ship Charta role.", ephemeral=True)
            return

        house = get_house(interaction.user)
        if not house:
            await interaction.response.send_message("No valid house role found.", ephemeral=True)
            return

        if not ship_allowed_for_house(house, ship_type.value):
            house_data = database.get_house(house)
            culture = house_data["culture"] if house_data else "Unknown"

            await interaction.response.send_message(
                f"{config.SHIPS[ship_type.value]['name']} is not available for your culture ({culture}).",
                ephemeral=True
            )
            return

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

        if comment:
            embed.add_field(name="Player Comment", value=comment, inline=False)

        embed.set_footer(text=f"Request ID: {request_id}")

        await log.send(embed=embed, view=ShipRequestView(self.bot))
        await interaction.response.send_message("Ship request submitted.", ephemeral=True)

    @app_commands.command(name="request_port_upgrade", description="Request a port level upgrade")
    @app_commands.describe(
        requested_level="Requested new port level",
        comment="Optional note for staff"
    )
    async def request_port_upgrade(
        self,
        interaction: discord.Interaction,
        requested_level: app_commands.Range[int, 1, 10],
        comment: str | None = None
    ):
        if not has_role(interaction.user, config.SHIP_CHARTA_ROLE):
            await interaction.response.send_message("You need the Ship Charta role.", ephemeral=True)
            return

        house = get_house(interaction.user)
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
            comment
        )

        embed = discord.Embed(
            title="New Port Upgrade Request",
            description="Waiting for staff approval."
        )
        embed.add_field(name="Player", value=interaction.user.mention, inline=True)
        embed.add_field(name="House", value=house, inline=True)
        embed.add_field(name="Requested Level", value=str(requested_level), inline=True)

        if comment:
            embed.add_field(name="Player Comment", value=comment, inline=False)

        embed.set_footer(text=f"Port Request ID: {request_id}")

        await log.send(embed=embed, view=PortRequestView(self.bot))
        await interaction.response.send_message("Port upgrade request submitted.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(ShipsCog(bot), guild=discord.Object(id=config.GUILD_ID))