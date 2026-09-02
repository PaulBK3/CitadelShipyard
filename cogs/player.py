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
            f"Port Level: {house_data['port_level']}\n"
            f"Highest Port Level: {house_data['highest_port_level']}"
        )

        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="my_fleet", description="View your house fleet")
    @app_commands.describe(time="Time in years to pay maintenance for")
    async def my_fleet(self, interaction: discord.Interaction, time: int):
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

        total = utils.calculate_house_maintenance(house, time)
        msg += f"\nWeekly Maintenance for {time} years: **{total} gold**"

        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="create_fleet", description="Create a named patrol or trade fleet")
    @app_commands.choices(
        fleet_type=[app_commands.Choice(name="Patrol", value="patrol"), app_commands.Choice(name="Trade", value="trade")],
        ship_type=utils.SHIP_CHOICES,
    )
    async def create_fleet(self, interaction: discord.Interaction, name: str, fleet_type: app_commands.Choice[str], commander: str, commander_martial: app_commands.Range[int, 0, 100], ship_type: app_commands.Choice[str], amount: app_commands.Range[int, 1, 1000]):
        house = utils.get_house(interaction.user)
        if not house:
            await interaction.response.send_message("No valid house role found.", ephemeral=True)
            return
        result = database.create_saved_fleet(house, name, fleet_type.value, commander, commander_martial, interaction.user.id, ship_type.value, amount)
        await interaction.response.send_message(result["message"], ephemeral=True)

    @app_commands.command(name="add_fleet_ship", description="Add ships to one of your named fleets")
    @app_commands.choices(ship_type=utils.SHIP_CHOICES)
    async def add_fleet_ship(self, interaction: discord.Interaction, fleet_name: str, ship_type: app_commands.Choice[str], amount: app_commands.Range[int, 1, 1000]):
        house = utils.get_house(interaction.user)
        if not house:
            await interaction.response.send_message("No valid house role found.", ephemeral=True)
            return
        result = database.add_ship_to_saved_fleet(house, fleet_name, ship_type.value, amount)
        await interaction.response.send_message(result["message"], ephemeral=True)

    @app_commands.command(name="my_fleets", description="View your named patrol and trade fleets")
    async def my_fleets(self, interaction: discord.Interaction):
        house = utils.get_house(interaction.user)
        if not house:
            await interaction.response.send_message("No valid house role found.", ephemeral=True)
            return
        fleets = database.get_saved_fleets([house])
        if not fleets:
            await interaction.response.send_message("You have no saved fleets.", ephemeral=True)
            return
        lines = []
        for fleet in fleets:
            ships = ", ".join(f"{amount} {config.SHIPS.get(ship_type, {}).get('name', ship_type)}" for ship_type, amount in fleet["ships"].items())
            lines.append(f"**{fleet['name']}** ({fleet['fleet_type']}) — {fleet['commander']}\n{ships}")
        await interaction.response.send_message("\n\n".join(lines), ephemeral=True)

async def setup(bot):
    await bot.add_cog(PlayerCog(bot), guild=discord.Object(id=config.GUILD_ID))
