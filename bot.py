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


def get_house(member):

    houses = [r.name for r in member.roles if r.name.startswith("House ")]
    return houses[0] if houses else None


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
    bot.add_view(ShipRequestView())  # re-register persistent buttons
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
        if not has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.response.send_message("Ship Staff only.", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        footer = embed.footer.text

        if not footer.startswith("Request ID: "):
            await interaction.response.send_message("Invalid request.", ephemeral=True)
            return

        request_id = int(footer.replace("Request ID: ", ""))
        request = database.get_ship_request(request_id)

        if not request:
            await interaction.response.send_message("Request not found.", ephemeral=True)
            return

        if request["status"] != "pending":
            await interaction.response.send_message("This request was already handled.", ephemeral=True)
            return

        database.update_ship_request_status(request_id, "approved", interaction.user.name)

        new_embed = discord.Embed(
            title="Ship Request Approved",
            description=f"{request['amount']}x {config.SHIPS[request['ship_type']]['name']} approved."
        )
        new_embed.add_field(name="Player", value=f"<@{request['user_id']}>", inline=True)
        new_embed.add_field(name="House", value=request["house"], inline=True)
        new_embed.add_field(name="Approved By", value=interaction.user.mention, inline=True)
        new_embed.set_footer(text=f"Request ID: {request_id}")

        await interaction.response.edit_message(embed=new_embed, view=None)

    @discord.ui.button(
        label="Deny",
        style=discord.ButtonStyle.red,
        custom_id="ship_request_deny"
    )
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.response.send_message("Ship Staff only.", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        footer = embed.footer.text

        if not footer.startswith("Request ID: "):
            await interaction.response.send_message("Invalid request.", ephemeral=True)
            return

        request_id = int(footer.replace("Request ID: ", ""))
        request = database.get_ship_request(request_id)

        if not request:
            await interaction.response.send_message("Request not found.", ephemeral=True)
            return

        if request["status"] != "pending":
            await interaction.response.send_message("This request was already handled.", ephemeral=True)
            return

        database.update_ship_request_status(request_id, "denied", interaction.user.name)

        new_embed = discord.Embed(
            title="Ship Request Denied",
            description=f"{request['amount']}x {config.SHIPS[request['ship_type']]['name']} denied."
        )
        new_embed.add_field(name="Player", value=f"<@{request['user_id']}>", inline=True)
        new_embed.add_field(name="House", value=request["house"], inline=True)
        new_embed.add_field(name="Denied By", value=interaction.user.mention, inline=True)
        new_embed.set_footer(text=f"Request ID: {request_id}")

        await interaction.response.edit_message(embed=new_embed, view=None)

#-------------------
# buy ship command
#-------------------

@bot.tree.command(name="buy_ship", description="Request ship construction")
@app_commands.choices(ship_type=SHIP_CHOICES)
@app_commands.describe(
    ship_type="Ship type",
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

    house = get_house(interaction.user)
    if not house:
        await interaction.response.send_message("No valid house role found.", ephemeral=True)
        return

    log = await log_channel(interaction.guild)
    if not log:
        await interaction.response.send_message("Ship request channel not found.", ephemeral=True)
        return

    request_id = database.create_ship_request(
        interaction.user.id,
        house,
        ship_type,
        amount
    )

    ship_name = config.SHIPS[ship_type]["name"]

    embed = discord.Embed(
        title="New Ship Construction Request",
        description="Waiting for staff approval."
    )
    embed.add_field(name="Player", value=interaction.user.mention, inline=True)
    embed.add_field(name="House", value=house, inline=True)
    embed.add_field(name="Ship", value=ship_name, inline=True)
    embed.add_field(name="Amount", value=str(amount), inline=True)

    cost_lines = []
    for key, data in config.SHIPS.items():
        if key == ship_type:
            total_cost = data["cost"] * amount
            cost_lines.append(f"{data['name']}: {data['cost']} Gold each, {total_cost} Gold total")
    embed.add_field(name="Total Cost", value="\n".join(cost_lines), inline=False)

    embed.set_footer(text=f"Request ID: {request_id}")

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