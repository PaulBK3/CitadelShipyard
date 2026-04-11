import discord
import config
import database


def has_role(user, role_name):
    return any(role.name == role_name for role in user.roles)


def get_house(member: discord.Member):
    for role in member.roles:
        for prefix in config.HOUSE_ROLE_FILTER:
            if role.name.startswith(prefix):
                return role.name
    return None


def calculate_house_maintenance(house_name):
    fleet = database.get_fleet_for_house(house_name)
    total = 0

    for ship_type, amount in fleet.items():
        ship_data = config.SHIPS.get(ship_type)
        if ship_data:
            total += ship_data.get("maintenance", 0) * amount

    return total