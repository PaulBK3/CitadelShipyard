import discord
from discord.ext import commands
import config
import database

from views.ship_views import ShipRequestView, ApprovedShipView
from views.port_views import PortRequestView

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = False

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

    synced = await bot.tree.sync(guild=guild)
    print(f"Synced {len(synced)} commands to dev guild.")


bot.run(config.TOKEN)