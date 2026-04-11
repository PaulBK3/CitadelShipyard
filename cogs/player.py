import discord
from discord.ext import commands
from discord import app_commands
import config
import database
import utils


class PlayerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="my_port", description="View your house naval profile")
    async def my_port(self, interaction: discord.Interaction):
        house = utils.get_house(interaction.user)
        if not house:
            await interaction.response.send_message("No valid house role found.", ephemeral=True)
            return

        house_data = database.get_house(house)
        if not house_data:
            await interaction.response.send_message(f"No profile found for **{house}**.", ephemeral=True)
            return

        msg = (
            f"**{house} Naval Profile**\n"
            f"Duchy: {house_data['duchy']}\n"
            f"Culture: {house_data['culture']}\n"
            f"Port Level: {house_data['port_level']}"
        )

        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="my_fleet", description="View your house fleet")
    async def my_fleet(self, interaction: discord.Interaction):
        house = utils.get_house(interaction.user)
        if not house:
            await interaction.response.send_message("No valid house role found.", ephemeral=True)
            return

        fleet_data = database.get_fleet_for_house(house)
        if not fleet_data:
            await interaction.response.send_message(f"No fleet entries found for **{house}**.", ephemeral=True)
            return

        msg = f"**{house} Fleet**\n"
        for ship_type, amount in fleet_data.items():
            ship_name = config.SHIPS.get(ship_type, {}).get("name", ship_type)
            msg += f"- {ship_name}: {amount}\n"

        total = utils.calculate_house_maintenance(house)
        msg += f"\nWeekly Maintenance: **{total} gold**"

        await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot):
    await bot.add_cog(PlayerCog(bot), guild=discord.Object(id=config.GUILD_ID))