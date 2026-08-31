import discord
import config
import database
from discord import app_commands

def has_role(user, role_name):
    return any(role.name == role_name for role in user.roles)


def get_house(member: discord.Member):
    for role in member.roles:
        for prefix in config.HOUSE_ROLE_FILTER:
            if role.name.startswith(prefix):
                return role.name
    return None


def calculate_house_maintenance(house_name, time):
    fleet = database.get_fleet_for_house(house_name)
    total = 0

    for ship_type, amount in fleet.items():
        ship_data = config.SHIPS.get(ship_type)
        if ship_data:
            total += (ship_data.get("maintenance", 0) * amount)/10*time

    return int(total)


CULTURE_CHOICES = [
    app_commands.Choice(name=culture_name, value=culture_name)
    for culture_name in sorted(config.SEA_CULTURES)
]

SHIP_CHOICES = [
    app_commands.Choice(name=data["name"], value=key)
    for key, data in config.SHIPS.items()
]

async def region_autocomplete(interaction: discord.Interaction,current: str):
    try:
        regions = database.get_all_regions(current or "", 25)

        current = current.lower()

        return [
            app_commands.Choice(
                name=region,
                value=region
            )
            for region in regions]     
    except Exception:
        return []

async def house_autocomplete(interaction: discord.Interaction, current: str):
    """Autocomplete provider: returns database-backed house names matching the current input."""
    try:
        matches = database.search_houses(current or "", 25)
        return [app_commands.Choice(name=h, value=h) for h in matches]
    except Exception:
        return []
