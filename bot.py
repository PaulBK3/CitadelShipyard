import os

import discord
from discord.ext import commands
import config
import database

from views.ship_views import ShipRequestView, ApprovedShipView
from views.port_views import PortRequestView
from views.battle_views import BattleFleetView
from dotenv import load_dotenv


load_dotenv()
intents = discord.Intents.default()

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")


@bot.event
async def setup_hook():
    database.setup()

    guild = discord.Object(id=config.GUILD_ID)

    # Load cogs
    await bot.load_extension("cogs.ships")
    await bot.load_extension("cogs.staff")
    await bot.load_extension("cogs.player")

    # Register persistent views
    bot.add_view(ShipRequestView(bot))
    bot.add_view(ApprovedShipView(bot))
    bot.add_view(PortRequestView(bot))

    for battle in database.get_active_battles():
        bot.add_view(BattleFleetView(bot, battle["id"]))

    synced = await bot.tree.sync(guild=guild)
    print(f"Synced {len(synced)} commands to dev guild.")


# -------------------------------
# Run
# -------------------------------
if __name__ == '__main__':
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        if not TOKEN:
            print("Please set DISCORD_TOKEN in your environment or .env file.")
            exit(1)
    else:
        bot.run(TOKEN)