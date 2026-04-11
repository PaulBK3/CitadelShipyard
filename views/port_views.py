import discord
import config
import database
import utils

async def notify_user(bot, user_id, message):
    try:
        user = await bot.fetch_user(user_id)
        await user.send(message)
    except Exception:
        pass


class DenyPortReasonModal(discord.ui.Modal, title="Deny Port Upgrade"):
    reason = discord.ui.TextInput(
        label="Reason",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )

    def __init__(self, bot, request_id: int):
        super().__init__()
        self.bot = bot
        self.request_id = request_id

    async def on_submit(self, interaction: discord.Interaction):
        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.response.send_message("Ship Staff only.", ephemeral=True)
            return

        request = database.get_port_request(self.request_id)
        if not request:
            await interaction.response.send_message("Request not found.", ephemeral=True)
            return

        if request["status"] != "pending":
            await interaction.response.send_message("This request was already handled.", ephemeral=True)
            return

        database.update_port_request_status(self.request_id, "denied", interaction.user.name, str(self.reason))

        new_embed = discord.Embed(
            title="Port Upgrade Denied",
            description=f"{request['house']} port upgrade request denied."
        )
        new_embed.add_field(name="Player", value=f"<@{request['user_id']}>", inline=True)
        new_embed.add_field(name="House", value=request["house"], inline=True)
        new_embed.add_field(name="Requested Level", value=str(request["requested_level"]), inline=True)
        new_embed.add_field(name="Reason", value=str(self.reason), inline=False)

        if request["comment"]:
            new_embed.add_field(name="Player Comment", value=request["comment"], inline=False)

        new_embed.set_footer(text=f"Port Request ID: {self.request_id}")

        await interaction.response.edit_message(embed=new_embed, view=None)

        await notify_user(
            self.bot,
            request["user_id"],
            f"Your port upgrade request for **{request['house']}** was denied.\nReason: {self.reason}"
        )


class PortRequestView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="port_request_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.response.send_message("Ship Staff only.", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        footer = embed.footer.text

        if not footer.startswith("Port Request ID: "):
            await interaction.response.send_message("Invalid request.", ephemeral=True)
            return

        request_id = int(footer.replace("Port Request ID: ", ""))
        request = database.get_port_request(request_id)

        if not request:
            await interaction.response.send_message("Request not found.", ephemeral=True)
            return

        if request["status"] != "pending":
            await interaction.response.send_message("This request was already handled.", ephemeral=True)
            return

        database.update_port_request_status(request_id, "approved", interaction.user.name)
        database.set_house_port_level(request["house"], request["requested_level"])

        new_embed = discord.Embed(
            title="Port Upgrade Approved",
            description=f"{request['house']} port level set to {request['requested_level']}."
        )
        new_embed.add_field(name="Player", value=f"<@{request['user_id']}>", inline=True)
        new_embed.add_field(name="House", value=request["house"], inline=True)
        new_embed.add_field(name="Approved By", value=interaction.user.mention, inline=True)

        if request["comment"]:
            new_embed.add_field(name="Player Comment", value=request["comment"], inline=False)

        new_embed.set_footer(text=f"Port Request ID: {request_id}")

        await interaction.response.edit_message(embed=new_embed, view=None)

        await notify_user(
            self.bot,
            request["user_id"],
            f"Your port upgrade request for **{request['house']}** was approved.\n"
            f"New Port Level: {request['requested_level']}"
        )

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, custom_id="port_request_deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.response.send_message("Ship Staff only.", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        footer = embed.footer.text

        if not footer.startswith("Port Request ID: "):
            await interaction.response.send_message("Invalid request.", ephemeral=True)
            return

        request_id = int(footer.replace("Port Request ID: ", ""))
        await interaction.response.send_modal(DenyPortReasonModal(self.bot, request_id))