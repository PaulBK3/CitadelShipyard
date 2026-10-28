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

def split_discord_message(message, limit=2000):
    """Split a message on line boundaries while respecting Discord's size limit."""
    chunks = []
    current = ""

    for line in message.splitlines(keepends=True):
        # Duchy names are normally short, but split an unexpectedly long line
        # too, so one malformed entry cannot make the command fail.
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]

        if len(current) + len(line) > limit:
            if current:
                chunks.append(current)
            current = line
        else:
            current += line

    if current:
        chunks.append(current)

    return chunks or [message]