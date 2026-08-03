import discord
from discord.ext import commands
from discord import app_commands
import config
import database
import utils
from views.battle_views import BattleFleetView


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
        await interaction.response.defer(ephemeral=True)
        
        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.followup.send("Ship Staff only.", ephemeral=True)
            return

        database.upsert_house(house, duchy, culture, port_level)

        await interaction.followup.send(
            f"Updated house profile:\n"
            f"**{house}**\n"
            f"Duchy: {duchy}\n"
            f"Culture: {culture}\n"
            f"Port Level: {port_level}",
            ephemeral=True
        )

    @staff.command(name="set_culture", description="Set a house culture")
    async def set_culture(self, interaction: discord.Interaction, house: str, culture: str):
        await interaction.response.defer(ephemeral=True)
        
        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.followup.send("Ship Staff only.", ephemeral=True)
            return

        database.set_house_culture(house, culture)
        await interaction.followup.send(f"Set **{house}** culture to **{culture}**.", ephemeral=True)

    @staff.command(name="set_port_level", description="Set a house port level")
    async def set_port_level(self, interaction: discord.Interaction, house: str, port_level: app_commands.Range[int, 0, 10]):
        await interaction.response.defer(ephemeral=True)
        
        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.followup.send("Ship Staff only.", ephemeral=True)
            return

        database.set_house_port_level(house, port_level)
        await interaction.followup.send(f"Set **{house}** port level to **{port_level}**.", ephemeral=True)

    @staff.command(name="fleet", description="View a house fleet")
    async def fleet(self, interaction: discord.Interaction, house: str):
        await interaction.response.defer(ephemeral=True)
        
        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.followup.send("Ship Staff only.", ephemeral=True)
            return

        fleet_data = database.get_fleet_for_house(house)

        if not fleet_data:
            await interaction.followup.send(f"No fleet entries found for **{house}**.", ephemeral=True)
            return

        msg = f"**{house} Fleet**\n"
        for ship_type, amount in fleet_data.items():
            ship_name = config.SHIPS.get(ship_type, {}).get("name", ship_type)
            msg += f"- {ship_name}: {amount}\n"

        await interaction.followup.send(msg, ephemeral=True)

    @staff.command(name="maintenance", description="Calculate a house fleet maintenance")
    async def maintenance(self, interaction: discord.Interaction, house: str):
        await interaction.response.defer(ephemeral=True)
        
        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.followup.send("Ship Staff only.", ephemeral=True)
            return

        total = utils.calculate_house_maintenance(house)
        await interaction.followup.send(
            f"**{house}** weekly fleet maintenance: **{total} gold**",
            ephemeral=True
        )

    @staff.command(name="maintenance_all", description="Calculate maintenance for all known houses")
    async def maintenance_all(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.followup.send("Ship Staff only.", ephemeral=True)
            return

        houses = database.get_all_houses()

        if not houses:
            await interaction.followup.send("No houses found in database.", ephemeral=True)
            return

        msg = "**Weekly Fleet Maintenance**\n"
        for house_name in houses:
            total = utils.calculate_house_maintenance(house_name)
            msg += f"- {house_name}: {total} gold\n"

        await interaction.followup.send(msg, ephemeral=True)

    @staff.command(name="create_battle", description="Create a new naval battle")
    @app_commands.describe(
        name="Battle name",
        attacker="Attacking side",
        defender="Defending side"
    )
    async def create_battle(self, interaction: discord.Interaction, name: str, attacker: str, defender: str):
        await interaction.response.defer(ephemeral=True)
        
        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.followup.send("Ship Staff only.", ephemeral=True)
            return

        # Create battle
        battle_id = database.create_battle(name, attacker, defender, interaction.user.id)

        # Create thread in ship log channel
        guild = interaction.guild
        battle_channel = None
        for channel in guild.text_channels:
            if channel.name == config.SEA_BATTLE_CHANNEL:
                battle_channel = channel
                break

        if not battle_channel:
            await interaction.followup.send("Sea battle channel not found.", ephemeral=True)
            return

        # Create threads
        thread_attacker = await battle_channel.create_thread(
            name=f"Battle: {name} {attacker} side",
            type=discord.ChannelType.public_thread
        )

        thread_defender = await battle_channel.create_thread(
            name=f"Battle: {name} {defender} side",
            type=discord.ChannelType.public_thread
        )
        # Update battle with thread id
        database.update_battle_thread(battle_id, thread_attacker.id)
        database.update_battle_thread(battle_id, thread_defender.id)
        # Send initial message in thread
        embed = discord.Embed(
            title=f"Naval Battle: {name}",
            description=f"**Attacker:** {attacker}\n**Defender:** {defender}\n\nStatus: Preparing fleets",
            color=0xff0000
        )

        view = BattleFleetView(battle_id)
        await thread_attacker.send(embed=embed, view=view)
        await thread_defender.send(embed=embed, view=view)

        await interaction.followup.send(f"Battle '{name}' created! Threads: {thread_attacker.mention}, {thread_defender.mention}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(StaffCog(bot), guild=discord.Object(id=config.GUILD_ID))