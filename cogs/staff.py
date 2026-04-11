import discord
from discord.ext import commands
from discord import app_commands
import config
import database


def has_role(user, role_name):
    return any(role.name == role_name for role in user.roles)


def calculate_house_maintenance(house_name):
    fleet = database.get_fleet_for_house(house_name)
    total = 0

    for ship_type, amount in fleet.items():
        ship_data = config.SHIPS.get(ship_type)
        if ship_data:
            total += ship_data.get("maintenance", 0) * amount

    return total


class StaffCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    staff = app_commands.Group(name="staff", description="Ship staff commands")

    @staff.command(name="set_house_profile", description="Create or update a house profile")
    @app_commands.describe(
        house="House name",
        duchy="Duchy name",
        culture="Culture name",
        port_level="Current port level"
    )
    async def set_house_profile(
        self,
        interaction: discord.Interaction,
        house: str,
        duchy: str,
        culture: str,
        port_level: app_commands.Range[int, 0, 10]
    ):
        if not has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.response.send_message("Ship Staff only.", ephemeral=True)
            return

        database.upsert_house(house, duchy, culture, port_level)

        await interaction.response.send_message(
            f"Updated house profile:\n"
            f"**{house}**\n"
            f"Duchy: {duchy}\n"
            f"Culture: {culture}\n"
            f"Port Level: {port_level}",
            ephemeral=True
        )

    @staff.command(name="set_culture", description="Set a house culture")
    async def set_culture(self, interaction: discord.Interaction, house: str, culture: str):
        if not has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.response.send_message("Ship Staff only.", ephemeral=True)
            return

        database.set_house_culture(house, culture)
        await interaction.response.send_message(f"Set **{house}** culture to **{culture}**.", ephemeral=True)

    @staff.command(name="set_port_level", description="Set a house port level")
    async def set_port_level(self, interaction: discord.Interaction, house: str, port_level: app_commands.Range[int, 0, 10]):
        if not has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.response.send_message("Ship Staff only.", ephemeral=True)
            return

        database.set_house_port_level(house, port_level)
        await interaction.response.send_message(f"Set **{house}** port level to **{port_level}**.", ephemeral=True)

    @staff.command(name="fleet", description="View a house fleet")
    async def fleet(self, interaction: discord.Interaction, house: str):
        if not has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.response.send_message("Ship Staff only.", ephemeral=True)
            return

        fleet_data = database.get_fleet_for_house(house)

        if not fleet_data:
            await interaction.response.send_message(f"No fleet entries found for **{house}**.", ephemeral=True)
            return

        msg = f"**{house} Fleet**\n"
        for ship_type, amount in fleet_data.items():
            ship_name = config.SHIPS.get(ship_type, {}).get("name", ship_type)
            msg += f"- {ship_name}: {amount}\n"

        await interaction.response.send_message(msg, ephemeral=True)

    @staff.command(name="maintenance", description="Calculate a house fleet maintenance")
    async def maintenance(self, interaction: discord.Interaction, house: str):
        if not has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.response.send_message("Ship Staff only.", ephemeral=True)
            return

        total = calculate_house_maintenance(house)
        await interaction.response.send_message(
            f"**{house}** weekly fleet maintenance: **{total} gold**",
            ephemeral=True
        )

    @staff.command(name="maintenance_all", description="Calculate maintenance for all known houses")
    async def maintenance_all(self, interaction: discord.Interaction):
        if not has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.response.send_message("Ship Staff only.", ephemeral=True)
            return

        houses = database.get_all_houses()

        if not houses:
            await interaction.response.send_message("No houses found in database.", ephemeral=True)
            return

        msg = "**Weekly Fleet Maintenance**\n"
        for house_name in houses:
            total = calculate_house_maintenance(house_name)
            msg += f"- {house_name}: {total} gold\n"

        await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot):
    await bot.add_cog(StaffCog(bot), guild=discord.Object(id=config.GUILD_ID))