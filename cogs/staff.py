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
    @app_commands.autocomplete(house=utils.house_autocomplete)
    @app_commands.choices(culture=utils.CULTURE_CHOICES)
    @app_commands.choices(region=utils.REGION_CHOICES)
    @app_commands.describe(
        house="House name",
        duchy="Duchy name",
        culture="Culture name",
        port_level="Current port level",
        region="Region name"
    )
    async def set_house_profile(
        self,
        interaction: discord.Interaction,
        house: str,
        duchy: str,
        culture: app_commands.Choice[str] | None = None,
        port_level: app_commands.Range[int, 0, 10] | None = None,
        region: app_commands.Choice[str] | None = None
    ):
        await interaction.response.defer(ephemeral=True)
        
        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.followup.send("Ship Staff only.", ephemeral=True)
            return

        database.upsert_house(house, duchy, culture.value if culture else None, port_level, region.value if region else None)

        await interaction.followup.send(
            f"Updated house profile:\n"
            f"**{house}**\n"
            f"Duchy: {duchy}\n"
            f"Culture: {culture.value}\n"
            f"Port Level: {port_level}\n"
            f"Region: {region.value}",
            ephemeral=True
        )

    @staff.command(name="set_culture", description="Set a house culture")
    @app_commands.choices(culture=utils.CULTURE_CHOICES)
    @app_commands.autocomplete(house=utils.house_autocomplete)
    async def set_culture(self, interaction: discord.Interaction, house: str, culture: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)
        
        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.followup.send("Ship Staff only.", ephemeral=True)
            return

        database.set_house_culture(house, culture.value)
        await interaction.followup.send(f"Set **{house}** culture to **{culture.value}**.", ephemeral=True)

    @staff.command(name="set_region", description="Set a house region")
    @app_commands.choices(region=utils.REGION_CHOICES)
    @app_commands.autocomplete(house=utils.house_autocomplete)
    async def set_region(self, interaction: discord.Interaction, house: str, region: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)
        
        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.followup.send("Ship Staff only.", ephemeral=True)
            return

        database.set_house_region(house, region.value)
        await interaction.followup.send(f"Set **{house}** region to **{region.value}**.", ephemeral=True)

    @staff.command(name="set_port_level", description="Set a house port level")
    @app_commands.autocomplete(house=utils.house_autocomplete)
    async def set_port_level(self, interaction: discord.Interaction, house: str, port_level: app_commands.Range[int, 0, 10]):
        await interaction.response.defer(ephemeral=True)
        
        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.followup.send("Ship Staff only.", ephemeral=True)
            return

        database.set_house_port_level(house, port_level)
        await interaction.followup.send(f"Set **{house}** port level to **{port_level}**.", ephemeral=True)

    @staff.command(name="add_ships", description="Add ships directly to a house fleet")
    @app_commands.choices(ship_type=utils.SHIP_CHOICES)
    @app_commands.describe(
        house="House name",
        ship_type="Type of ship",
        amount="How many ships to add"
    )
    @app_commands.autocomplete(house=utils.house_autocomplete)
    async def add_ships(
        self,
        interaction: discord.Interaction,
        house: str,
        ship_type: app_commands.Choice[str],
        amount: app_commands.Range[int, 1, 1000]
    ):
        await interaction.response.defer(ephemeral=True)

        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.followup.send("Ship Staff only.", ephemeral=True)
            return

        database.ensure_house_exists(house)
        database.add_fleet_entry(house, ship_type.value, amount)

        ship_name = config.SHIPS.get(ship_type.value, {}).get("name", ship_type.value)
        await interaction.followup.send(
            f"Added **{amount}x {ship_name}** to **{house}**.",
            ephemeral=True
        )

    @staff.command(name="fleet", description="View a house fleet")
    @app_commands.autocomplete(house=utils.house_autocomplete)
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
    @app_commands.autocomplete(house=utils.house_autocomplete)
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
    @app_commands.autocomplete(attacker=utils.house_autocomplete, defender=utils.house_autocomplete)
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
        # Update battle with side-specific thread ids
        database.update_battle_threads(battle_id, thread_attacker.id, thread_defender.id)

        view = BattleFleetView(self.bot, battle_id)
        embed_attacker = discord.Embed(
            title=f"Naval Battle: {name} — {attacker} Side",
            description=(
                f"**Attacker:** {attacker}\n"
                f"**Defender:** {defender}\n"
                f"Status: Preparing fleets\n"
                f"Showing: {attacker} side"
            ),
            color=0xff0000
        )
        embed_attacker.set_footer(text=f"Battle ID: {battle_id}")
        embed_defender = discord.Embed(
            title=f"Naval Battle: {name} — {defender} Side",
            description=(
                f"**Attacker:** {attacker}\n"
                f"**Defender:** {defender}\n"
                f"Status: Preparing fleets\n"
                f"Showing: {defender} side"
            ),
            color=0xff0000
        )
        embed_defender.set_footer(text=f"Battle ID: {battle_id}")

        await thread_attacker.send(embed=embed_attacker, view=view)
        await thread_defender.send(embed=embed_defender, view=view)

        await interaction.followup.send(f"Battle '{name}' created! Threads: {thread_attacker.mention}, {thread_defender.mention}", ephemeral=True)

    @staff.command(name="assign_house", description="Assign a house to an attacker or defender side")
    @app_commands.autocomplete(house=utils.house_autocomplete)
    @app_commands.describe(
        battle_id="Battle ID",
        side="Which side: attacker or defender",
        house="House name to assign"
    )
    async def assign_house(self, interaction: discord.Interaction, battle_id: int, side: str, house: str):
        await interaction.response.defer(ephemeral=True)
        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.followup.send("Ship Staff only.", ephemeral=True)
            return

        side_norm = side.lower()
        if side_norm not in ("attacker", "defender"):
            await interaction.followup.send("Side must be 'attacker' or 'defender'.", ephemeral=True)
            return

        database.assign_house_to_side(battle_id, side_norm, house)
        await interaction.followup.send(f"Assigned **{house}** to **{side_norm}** for battle {battle_id}.", ephemeral=True)

    @staff.command(name="remove_house", description="Remove a house from a battle side")
    @app_commands.autocomplete(house=utils.house_autocomplete)
    @app_commands.describe(
        battle_id="Battle ID",
        side="Which side: attacker or defender",
        house="House name to remove"
    )
    async def remove_house(self, interaction: discord.Interaction, battle_id: int, side: str, house: str):
        await interaction.response.defer(ephemeral=True)
        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.followup.send("Ship Staff only.", ephemeral=True)
            return

        side_norm = side.lower()
        if side_norm not in ("attacker", "defender"):
            await interaction.followup.send("Side must be 'attacker' or 'defender'.", ephemeral=True)
            return

        database.remove_house_from_side(battle_id, side_norm, house)
        await interaction.followup.send(f"Removed **{house}** from **{side_norm}** for battle {battle_id}.", ephemeral=True)

    @staff.command(name="sync_houses", description="Sync house roles from the guild into the database")
    async def sync_houses(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.followup.send("Ship Staff only.", ephemeral=True)
            return

        guild = interaction.guild
        if not guild:
            await interaction.followup.send("Command must be run in a guild.", ephemeral=True)
            return

        # Find roles that match HOUSE_ROLE_FILTER prefixes
        matched = []
        for role in guild.roles:
            for prefix in config.HOUSE_ROLE_FILTER:
                if role.name.startswith(prefix):
                    matched.append((role.id, role.name))
                    break

        if not matched:
            await interaction.followup.send("No house roles found to sync.", ephemeral=True)
            return

        database.sync_houses_from_list(matched)
        await interaction.followup.send(f"Synced {len(matched)} house roles into the database.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(StaffCog(bot), guild=discord.Object(id=config.GUILD_ID))