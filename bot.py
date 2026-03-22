import discord
from discord import app_commands
from discord.ext import commands, tasks
import config
import os
import database

from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

database.setup()

SHIP_CHOICES = [
    app_commands.Choice(name=data["name"], value=key)
    for key, data in config.SHIPS.items()
]

staff = app_commands.Group(name="staff", description="Trade team commands")
bot.tree.add_command(staff)

# -------------------
# Helpers
# -------------------

def has_role(member, role):

    return any(r.name == role for r in member.roles)


def get_region(member):

    regions = [r.name for r in member.roles if r.name in config.REGION_ROLES]

    if len(regions) == 1:
        return regions[0]
    #handle dragonstaone/crownlands dual role
    if len(regions)== 2:
        if "Dragonstone" in regions:
            return regions[0] if regions[1] == "Crownlands" else regions[1]
    return None


async def log_channel(guild):

    for channel in guild.text_channels:
        if channel.name == config.SHIP_LOG_CHANNEL:
            return channel
        
# -------------------
# Ready
# -------------------

@bot.event
async def setup_hook():

    guild = discord.Object(id=config.GUILD_ID)

    # clear global commands
    #bot.tree.clear_commands(guild=None)
    #await bot.tree.sync()

    # clear guild commands
    bot.tree.clear_commands(guild=guild)


    bot.tree.copy_global_to(guild=guild)
    synced = await bot.tree.sync(guild=guild)

    print(f"Synced {len(synced)} commands to dev guild.")
    
@bot.event
async def on_ready():

    print("Shipyard Bot Ready")


#-------------------
# Ship Requests View
#-------------------

class ShipRequestView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="ship_request_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_role(interaction.user, config.SHIP_STAFF_ROLE):
            await interaction.response.send_message("Ship Staff only.", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        fields = {field.name: field.value for field in embed.fields}

        player = fields["Player"]
        region = fields["Region"]
        ship = fields["Ship"]
        amount = int(fields["Amount"])

        new_embed = discord.Embed(
            title="Ship Request Approved",
            description=f"{amount}x {ship} approved for {region}.",
        )
        new_embed.add_field(name="Player", value=player, inline=True)
        new_embed.add_field(name="Approved By", value=interaction.user.mention, inline=True)

        await interaction.response.edit_message(embed=new_embed, view=None)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, custom_id="ship_request_deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_role(interaction.user, config.SHIP_STAFF_ROLE):
            await interaction.response.send_message("Ship Staff only.", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        fields = {field.name: field.value for field in embed.fields}

        player = fields["Player"]
        ship = fields["Ship"]
        amount = fields["Amount"]

        new_embed = discord.Embed(
            title="Ship Request Denied",
            description=f"{amount}x {ship} denied.",
        )
        new_embed.add_field(name="Player", value=player, inline=True)
        new_embed.add_field(name="Denied By", value=interaction.user.mention, inline=True)

        await interaction.response.edit_message(embed=new_embed, view=None)

#-------------------
# buy ship command
#-------------------

@bot.tree.command(name="buy_ship", description="Request ship construction")
@app_commands.choices(ship_type=SHIP_CHOICES)
@app_commands.describe(
    ship_type="Type of ship",
    amount="How many ships to build"
)
async def buy_ship(
    interaction: discord.Interaction,
    ship_type: str,
    amount: int
):
    if amount <= 0:
        await interaction.response.send_message("Amount must be greater than 0.", ephemeral=True)
        return

    region = get_region(interaction.user)
    if not region:
        await interaction.response.send_message("No valid region role found.", ephemeral=True)
        return

    ship_data = config.SHIPS[ship_type]
    ship_name = ship_data["name"]

    embed = discord.Embed(
        title="New Ship Construction Request",
        description="Waiting for staff approval.",
    )
    embed.add_field(name="Player", value=interaction.user.mention, inline=True)
    embed.add_field(name="Region", value=region, inline=True)
    embed.add_field(name="Ship", value=ship_name, inline=True)
    embed.add_field(name="Amount", value=str(amount), inline=True)

    cost_lines = []
    for resource, cost in ship_data["cost"].items():
        cost_lines.append(f"{resource}: {cost * amount}")
    embed.add_field(name="Total Cost", value="\n".join(cost_lines), inline=False)

    log = await log_channel(interaction.guild)
    if log:
        await log.send(embed=embed, view=ShipRequestView())

    await interaction.response.send_message(
        f"Ship request submitted for {amount}x {ship_name}.",
        ephemeral=True
    )

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