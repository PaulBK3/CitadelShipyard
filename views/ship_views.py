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


async def save_edit_channel(guild):
    for channel in guild.text_channels:
        if channel.name == config.SAVE_EDIT_CHANNEL:
            return channel
    return None


class DenyShipReasonModal(discord.ui.Modal, title="Deny Ship Request"):
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

        request = database.get_ship_request(self.request_id)
        if not request:
            await interaction.response.send_message("Request not found.", ephemeral=True)
            return

        if request["status"] != "pending":
            await interaction.response.send_message("This request was already handled.", ephemeral=True)
            return

        database.update_ship_request_status(
            self.request_id,
            "denied",
            interaction.user.name,
            str(self.reason)
        )

        new_embed = discord.Embed(
            title="Ship Request Denied",
            description=f"{request['house']} ship request denied."
        )
        new_embed.add_field(name="Player", value=f"<@{request['user_id']}>", inline=True)
        new_embed.add_field(name="House", value=request["house"], inline=True)
        new_embed.add_field(name="Ship", value=request["ship_type"], inline=True)
        new_embed.add_field(name="Amount", value=str(request["amount"]), inline=True)
        new_embed.add_field(name="Reason", value=str(self.reason), inline=False)

        if request["comment"]:
            new_embed.add_field(name="Player Comment", value=request["comment"], inline=False)

        new_embed.set_footer(text=f"Request ID: {self.request_id}")

        await interaction.response.edit_message(embed=new_embed, view=None)

        await notify_user(
            self.bot,
            request["user_id"],
            f"Your ship request for **{request['amount']}x {request['ship_type']}** "
            f"for **{request['house']}** was denied.\nReason: {self.reason}"
        )


class ApprovedShipView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Add to Ledger", style=discord.ButtonStyle.blurple, custom_id="ship_add_to_ledger")
    async def add_to_ledger(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
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

        if request["status"] != "approved":
            await interaction.response.send_message("Only approved requests can be added to the ledger.", ephemeral=True)
            return

        if request["added_to_ledger"]:
            await interaction.response.send_message("This request is already in the ledger.", ephemeral=True)
            return

        database.add_fleet_entry(
            request["house"],
            request["ship_type"],
            request["amount"]
        )
        database.mark_ship_request_added_to_ledger(request_id)

        new_embed = embed.copy()
        new_embed.add_field(name="Ledger", value=f"Added by {interaction.user.mention}", inline=False)

        await interaction.response.edit_message(embed=new_embed, view=None)

        await notify_user(
            self.bot,
            request["user_id"],
            f"Your approved ship request for **{request['amount']}x {request['ship_type']}** "
            f"has now been added to the fleet ledger."
        )


class ShipRequestView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="ship_request_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
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

        ship_data = config.SHIPS.get(request["ship_type"], {})
        total_cost = ship_data.get("cost", 0) * request["amount"]

        save_channel = await save_edit_channel(interaction.guild)
        if save_channel:
            await save_channel.send(
                f"<@{request['user_id']}>:\n- Remove {total_cost} gold"
            )

        new_embed = discord.Embed(
            title="Ship Request Approved",
            description=f"{request['house']} ship request approved."
        )
        new_embed.add_field(name="Player", value=f"<@{request['user_id']}>", inline=True)
        new_embed.add_field(name="House", value=request["house"], inline=True)
        new_embed.add_field(name="Ship", value=request["ship_type"], inline=True)
        new_embed.add_field(name="Amount", value=str(request["amount"]), inline=True)
        new_embed.add_field(name="Total Cost", value=str(total_cost), inline=True)
        new_embed.add_field(name="Approved By", value=interaction.user.mention, inline=True)

        if request["comment"]:
            new_embed.add_field(name="Player Comment", value=request["comment"], inline=False)

        new_embed.set_footer(text=f"Request ID: {request_id}")

        await interaction.response.edit_message(embed=new_embed, view=ApprovedShipView(self.bot))

        await notify_user(
            self.bot,
            request["user_id"],
            f"Your ship request for **{request['amount']}x {request['ship_type']}** "
            f"for **{request['house']}** was approved."
        )

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, custom_id="ship_request_deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.response.send_message("Ship Staff only.", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        footer = embed.footer.text

        if not footer.startswith("Request ID: "):
            await interaction.response.send_message("Invalid request.", ephemeral=True)
            return

        request_id = int(footer.replace("Request ID: ", ""))
        await interaction.response.send_modal(DenyShipReasonModal(self.bot, request_id))