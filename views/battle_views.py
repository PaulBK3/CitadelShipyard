import discord
import config
import database
import utils


def build_battle_embed(battle_id, thread_id=None):
    battle = database.get_battle_by_thread(thread_id) if thread_id else database.get_battle(battle_id)
    if not battle:
        return discord.Embed(title="Battle", description="Battle not found.", color=0xff0000)

    side_house = None
    side_houses = None
    if thread_id:
        if battle.get("side") == "attacker":
            side_houses = database.get_houses_for_side(battle_id, 'attacker')
        elif battle.get("side") == "defender":
            side_houses = database.get_houses_for_side(battle_id, 'defender')
        # For display purposes, set a representative name when only one house exists
        if side_houses:
            side_house = ", ".join(side_houses)

    embed = discord.Embed(
        title=f"Naval Battle: {battle['name']}",
        description=(
            f"**Attacker:** {battle['attacker_house']}\n"
            f"**Defender:** {battle['defender_house']}\n"
            f"Status: {battle['status']}\n"
            f"Fleets locked: {'Yes' if battle.get('fleets_locked') else 'No'}"
            + (f"\nShowing: {side_house} side" if side_house else "")
        ),
        color=0xff0000
    )

    fleet_groups = database.get_battle_fleet_groups(battle_id)
    if side_houses:
        fleet_groups = [group for group in fleet_groups if group["house"] in side_houses]

    if fleet_groups:
        for group in fleet_groups:
            house = group["house"]
            commander = group.get("commander") or "Unknown Commander"
            lines = [f"{config.SHIPS.get(ship_type, {}).get('name', ship_type)}: {amount}" for ship_type, amount in group["ships"].items()]
            embed.add_field(
                name=f"{house} — {commander}",
                value="\n".join(lines),
                inline=False
            )
    else:
        empty_text = f"No fleets registered yet for {side_house}." if side_house else "No fleets registered yet."
        embed.add_field(name="Fleets", value=empty_text, inline=False)

    # show battle id in footer for easy reference
    try:
        embed.set_footer(text=f"Battle ID: {battle_id}")
    except Exception:
        pass

    return embed


async def refresh_battle_message(bot, channel_id, message_id, battle_id, view):
    channel = bot.get_channel(channel_id)
    if channel is None:
        return
    try:
        message = await channel.fetch_message(message_id)
        await message.edit(embed=build_battle_embed(battle_id, channel.id), view=view)
    except Exception:
        pass


class BattleFleetView(discord.ui.View):
    def __init__(self, bot, battle_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.battle_id = battle_id

        # Set the custom_id to include the battle_id so it persists
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if item.label == "Create Fleet":
                    item.custom_id = f"create_fleet_{battle_id}"
                elif item.label == "Lock Fleets":
                    item.custom_id = f"lock_fleets_{battle_id}"
                elif item.label == "Remove Fleet":
                    item.custom_id = f"remove_fleet_{battle_id}"

        if bot is not None and hasattr(bot, "add_view"):
            bot.add_view(self)

    @discord.ui.button(label="Create Fleet", style=discord.ButtonStyle.primary)
    async def create_fleet(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Extract battle_id from custom_id (format: create_fleet_{battle_id})
        try:
            battle_id = int(button.custom_id.split('_')[-1])
        except (ValueError, IndexError):
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send("Error: Invalid battle ID.", ephemeral=True)
            return

        if database.is_battle_fleets_locked(battle_id):
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send("Fleets are locked for this battle. No further fleet creation is allowed.", ephemeral=True)
            return

        battle = database.get_battle_by_thread(interaction.channel.id) or database.get_battle(battle_id)
        side_houses = None
        if battle and battle.get("side") == "attacker":
            side_houses = database.get_houses_for_side(battle_id, 'attacker')
        elif battle and battle.get("side") == "defender":
            side_houses = database.get_houses_for_side(battle_id, 'defender')

        if side_houses:
            houses = [h for h in side_houses if database.get_available_fleet_for_house(h)]
        else:
            houses = [house for house in database.get_all_houses() if database.get_available_fleet_for_house(house)]

        if not houses:
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send("No available houses with ships.", ephemeral=True)
            return

        view = HouseSelectView(battle_id, houses, interaction.user.id, interaction.channel.id, interaction.message.id)
        await interaction.response.send_message("Choose a house for your fleet:", view=view, ephemeral=True)

    @discord.ui.button(label="Lock Fleets", style=discord.ButtonStyle.secondary)
    async def lock_fleets(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.response.send_message("You do not have permission to lock fleets.", ephemeral=True)
            return

        try:
            battle_id = int(button.custom_id.split('_')[-1])
        except (ValueError, IndexError):
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send("Error: Invalid battle ID.", ephemeral=True)
            return

        locked = database.is_battle_fleets_locked(battle_id)
        battle = database.get_battle_by_thread(interaction.channel.id) or database.get_battle(battle_id)
        side_house = None
        if battle and battle.get("side") == "attacker":
            side_house = battle["attacker_house"]
        elif battle and battle.get("side") == "defender":
            side_house = battle["defender_house"]

        fleet_groups = database.get_battle_fleet_groups(battle_id)
        if side_house:
            fleet_groups = [group for group in fleet_groups if group["house"] == side_house]

            database.unlock_battle_fleets(battle_id)
            status_message = "Fleets are now unlocked for this battle. Fleet creation is allowed again."
        else:
            database.lock_battle_fleets(battle_id)
            status_message = "Fleets are now locked for this battle. No further fleet creation is allowed."

        await refresh_battle_message(self.bot, interaction.channel.id, interaction.message.id, battle_id, BattleFleetView(self.bot, battle_id))
        await interaction.response.send_message(status_message, ephemeral=True)

    @discord.ui.button(label="Remove Fleet", style=discord.ButtonStyle.danger)
    async def remove_fleet(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not utils.has_role(interaction.user, config.SHIP_TEAM_ROLE):
            await interaction.response.send_message("You do not have permission to remove fleets.", ephemeral=True)
            return

        try:
            battle_id = int(button.custom_id.split('_')[-1])
        except (ValueError, IndexError):
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send("Error: Invalid battle ID.", ephemeral=True)
            return

        battle = database.get_battle_by_thread(interaction.channel.id) or database.get_battle(battle_id)
        side_house = None
        if battle and battle.get("side") == "attacker":
            side_house = battle["attacker_house"]
        elif battle and battle.get("side") == "defender":
            side_house = battle["defender_house"]

        fleet_groups = database.get_battle_fleet_groups(battle_id)
        if side_house:
            fleet_groups = [group for group in fleet_groups if group["house"] == side_house]

        if not fleet_groups:
            await interaction.response.send_message("There are no fleets to remove for this battle.", ephemeral=True)
            return

        view = RemoveFleetView(
            battle_id,
            fleet_groups,
            interaction.user.id,
            interaction.client,
            interaction.channel.id,
            interaction.message.id
        )
        await interaction.response.send_message("Select a fleet to remove or delete all fleets:", view=view, ephemeral=True)


class HouseSelectView(discord.ui.View):
    def __init__(self, battle_id: int, houses: list, user_id: int, origin_channel_id: int, origin_message_id: int):
        super().__init__(timeout=None)
        self.battle_id = battle_id
        self.houses = houses
        self.user_id = user_id
        self.origin_channel_id = origin_channel_id
        self.origin_message_id = origin_message_id

        options = [discord.SelectOption(label=house, value=house) for house in houses]
        house_select = discord.ui.Select(
            placeholder="Choose a house",
            options=options,
            custom_id=f"house_select_{battle_id}",
            min_values=1,
            max_values=1
        )
        house_select.callback = self.house_selected
        self.add_item(house_select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Only the original user can choose a house.", ephemeral=True)
            return False
        return True

    async def house_selected(
        self,
        interaction: discord.Interaction
    ):
        selected_house = interaction.data.get(
            "values", [None]
        )[0]

        if not selected_house:
            await interaction.response.send_message(
                "No house selected.",
                ephemeral=True
            )
            return

        available_fleet = database.get_available_fleet_for_house(
            selected_house
        )

        if not available_fleet:
            await interaction.response.send_message(
                "No ships available for that house.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(
            CommanderModal(
                battle_id=self.battle_id,
                house=selected_house,
                available_fleet=available_fleet,
                bot=interaction.client,
                user_id=self.user_id,
                origin_channel_id=self.origin_channel_id,
                origin_message_id=self.origin_message_id
            )
        )


class ShipSelectView(discord.ui.View):
    def __init__(
        self,
        battle_id: int,
        house: str,
        available_fleet: dict,
        commander: str,
        bot,
        user_id: int,
        origin_channel_id: int,
        origin_message_id: int
    ):
        super().__init__(timeout=None)

        self.battle_id = battle_id
        self.house = house
        self.available_fleet = available_fleet
        self.commander = commander
        self.bot = bot
        self.user_id = user_id
        self.origin_channel_id = origin_channel_id
        self.origin_message_id = origin_message_id

        # This is the ONLY place selected quantities are stored.
        # Everything starts at 0.
        self.selected_ships = {
            ship_type: 0
            for ship_type in available_fleet
        }

        for ship_type, max_amount in available_fleet.items():
            ship_name = config.SHIPS.get(
                ship_type, {}
            ).get("name", ship_type)

            button = discord.ui.Button(
                label=f"{ship_name} (0)",
                style=discord.ButtonStyle.secondary,
                custom_id=f"ship_amount_{battle_id}_{ship_type}"
            )

            async def callback(
                interaction: discord.Interaction,
                ship_type=ship_type
            ):
                await self.ship_selected(interaction, ship_type)

            button.callback = callback
            self.add_item(button)

        self.add_item(
            discord.ui.Button(
                label="Submit Fleet",
                style=discord.ButtonStyle.success,
                custom_id=f"submit_fleet_{battle_id}"
            )
        )

        # Assign callback to submit button
        self.children[-1].callback = self.submit_fleet

    async def interaction_check(
        self,
        interaction: discord.Interaction
    ) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Only the original user can configure this fleet.",
                ephemeral=True
            )
            return False

        return True

    async def ship_selected(
        self,
        interaction: discord.Interaction,
        ship_type: str
    ):
        ship_name = config.SHIPS.get(
            ship_type, {}
        ).get("name", ship_type)

        max_amount = self.available_fleet[ship_type]
        current_amount = self.selected_ships.get(ship_type, 0)

        await interaction.response.send_modal(
            ShipQuantityModal(
                ship_type=ship_type,
                ship_name=ship_name,
                max_amount=max_amount,
                current_amount=current_amount,
                ship_view=self
            )
        )
    def get_ship_selection_text(self):
        lines = [
            f"**House:** {self.house}",
            f"**Commander:** {self.commander}",
            "",
            "**Current Fleet:**"
        ]

        has_ships = False

        for ship_type, amount in self.selected_ships.items():
            if amount > 0:
                has_ships = True

                ship_name = config.SHIPS.get(
                    ship_type, {}
                ).get("name", ship_type)

                lines.append(
                    f"• {ship_name}: {amount}"
                )

        if not has_ships:
            lines.append("*No ships selected.*")

        lines.extend([
            "",
            "Click a ship below to enter its quantity."
        ])

        return "\n".join(lines)


    def update_ship_buttons(self):
        for item in self.children:
            if not isinstance(item, discord.ui.Button):
                continue

            if not item.custom_id:
                continue

            if not item.custom_id.startswith("ship_amount_"):
                continue

            ship_type = item.custom_id.split(
                "_", 3
            )[-1]

            amount = self.selected_ships.get(
                ship_type, 0
            )

            ship_name = config.SHIPS.get(
                ship_type, {}
            ).get("name", ship_type)

            item.label = f"{ship_name} ({amount})"
    async def submit_fleet(
        self,
        interaction: discord.Interaction
    ):
        # Only include ships the user actually selected.
        fleet = {
            ship_type: amount
            for ship_type, amount in self.selected_ships.items()
            if amount > 0
        }

        if not fleet:
            await interaction.response.send_message(
                "No ships selected.",
                ephemeral=True
            )
            return

        # Check supply
        total_supply = 0

        for ship_type, amount in fleet.items():
            ship_data = config.SHIPS.get(ship_type)

            if ship_data:
                total_supply += (
                    ship_data.get("supply_cost", 0) * amount
                )

        if total_supply > 0:
            await interaction.response.send_message(
                f"Insufficient supply! Your fleet requires "
                f"{total_supply} supply points. "
                f"Add more supply ships.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        # THIS is the first point where ships are actually reserved.
        success = database.reserve_battle_fleet_entries(
            self.battle_id,
            self.house,
            fleet,
            self.commander
        )

        if not success:
            await interaction.followup.send(
                "Insufficient ships available to submit this fleet. "
                "Another fleet may have claimed them.",
                ephemeral=True
            )
            return

        fleet_str = "\n".join(
            f"- {config.SHIPS.get(ship_type, {}).get('name', ship_type)}: {amount}"
            for ship_type, amount in fleet.items()
        )

        await interaction.followup.send(
            f"Fleet submitted for **{self.house}** "
            f"under commander **{self.commander}**:\n"
            f"{fleet_str}",
            ephemeral=True
        )

        await refresh_battle_message(
            self.bot,
            self.origin_channel_id,
            self.origin_message_id,
            self.battle_id,
            BattleFleetView(self.bot, self.battle_id)
        )


class RemoveFleetView(discord.ui.View):
    def __init__(self, battle_id: int, fleet_groups: list, user_id: int, bot, origin_channel_id: int, origin_message_id: int):
        super().__init__(timeout=None)
        self.battle_id = battle_id
        self.user_id = user_id
        self.bot = bot
        self.origin_channel_id = origin_channel_id
        self.origin_message_id = origin_message_id
        self.selected_fleet_id = None

        options = [
            discord.SelectOption(
                label=f"{group['house']} — {group.get('commander', 'Unknown Commander')} ({sum(group['ships'].values())} ships)",
                value=group['fleet_id']
            )
            for group in fleet_groups
        ]
        self.fleet_select = discord.ui.Select(
            placeholder="Select a fleet to remove",
            options=options,
            custom_id=f"remove_fleet_select_{battle_id}",
            min_values=1,
            max_values=1
        )
        self.fleet_select.callback = self.select_fleet
        self.add_item(self.fleet_select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Only the original user can remove fleets.", ephemeral=True)
            return False
        return True

    async def select_fleet(self, interaction: discord.Interaction):
        self.selected_fleet_id = interaction.data.get("values", [None])[0]
        await interaction.response.defer()

    @discord.ui.button(label="Delete Selected Fleet", style=discord.ButtonStyle.danger)
    async def delete_selected(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_fleet_id:
            await interaction.response.send_message("Please select a fleet before deleting.", ephemeral=True)
            return

        database.delete_battle_fleet(self.battle_id, self.selected_fleet_id)
        await refresh_battle_message(self.bot, self.origin_channel_id, self.origin_message_id, self.battle_id, BattleFleetView(self.bot, self.battle_id))
        await interaction.response.send_message(f"Fleet has been removed and ships released.", ephemeral=True)

    @discord.ui.button(label="Delete All Fleets", style=discord.ButtonStyle.danger)
    async def delete_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        database.delete_all_battle_fleets(self.battle_id)
        await refresh_battle_message(self.bot, self.origin_channel_id, self.origin_message_id, self.battle_id, BattleFleetView(self.bot, self.battle_id))
        await interaction.response.send_message("All fleets for this battle have been removed and ships released.", ephemeral=True)


class ShipQuantityModal(discord.ui.Modal):
    def __init__(
        self,
        ship_type: str,
        ship_name: str,
        max_amount: int,
        current_amount: int,
        ship_view: ShipSelectView
    ):
        super().__init__(title=f"{ship_name} Quantity")

        self.ship_type = ship_type
        self.max_amount = max_amount
        self.ship_view = ship_view

        self.amount = discord.ui.TextInput(
            label=f"{ship_name} amount",
            placeholder=f"Enter 0-{max_amount}",
            default=str(current_amount),
            required=True,
            max_length=10
        )

        self.add_item(self.amount)

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):
        try:
            amount = int(str(self.amount.value).strip())
        except ValueError:
            await interaction.response.send_message(
                "Please enter a whole number.",
                ephemeral=True
            )
            return

        if amount < 0:
            await interaction.response.send_message(
                "The amount cannot be negative.",
                ephemeral=True
            )
            return

        if amount > self.max_amount:
            await interaction.response.send_message(
                f"You only have **{self.max_amount}** "
                f"of this ship available.",
                ephemeral=True
            )
            return

        # Only change the selected quantity.
        self.ship_view.selected_ships[self.ship_type] = amount

        # Rebuild the buttons so they show the selected amounts.
        self.ship_view.update_ship_buttons()

        await interaction.response.edit_message(
            content=self.ship_view.get_ship_selection_text(),
            view=self.ship_view
        )

class CommanderView(discord.ui.View):
    def __init__(
        self,
        battle_id: int,
        house: str,
        available_fleet: dict,
        user_id: int,
        origin_channel_id: int,
        origin_message_id: int
    ):
        super().__init__(timeout=None)

        self.battle_id = battle_id
        self.house = house
        self.available_fleet = available_fleet
        self.user_id = user_id
        self.origin_channel_id = origin_channel_id
        self.origin_message_id = origin_message_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Only the original user can configure this fleet.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(
        label="Enter Commander",
        style=discord.ButtonStyle.primary
    )
    async def enter_commander(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_modal(
            CommanderNameModal(
                self.battle_id,
                self.house,
                self.available_fleet,
                self.user_id,
                self.origin_channel_id,
                self.origin_message_id
            )
        )

class ShipAmountModal(discord.ui.Modal):
    def __init__(
        self,
        ship_type: str,
        ship_name: str,
        max_amount: int,
        current_amount: int,
        ship_view: ShipSelectView
    ):
        super().__init__(title=f"{ship_name} Amount")

        self.ship_type = ship_type
        self.max_amount = max_amount
        self.ship_view = ship_view

        self.amount = discord.ui.TextInput(
            label=f"{ship_name} (max {max_amount})",
            placeholder=str(current_amount),
            default=str(current_amount),
            required=True,
            max_length=10
        )

        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(str(self.amount.value).strip())
        except ValueError:
            await interaction.response.send_message(
                "Please enter a whole number.",
                ephemeral=True
            )
            return

        if amount < 0:
            await interaction.response.send_message(
                "The amount cannot be negative.",
                ephemeral=True
            )
            return

        if amount > self.max_amount:
            await interaction.response.send_message(
                f"You only have **{self.max_amount}** "
                f"of this ship available.",
                ephemeral=True
            )
            return

        self.ship_view.selected_ships[self.ship_type] = amount

        # Show current selections again
        lines = []

        for ship_type, selected_amount in self.ship_view.selected_ships.items():
            if selected_amount > 0:
                ship_name = config.SHIPS.get(
                    ship_type, {}
                ).get("name", ship_type)

                lines.append(
                    f"**{ship_name}:** {selected_amount}"
                )

        if not lines:
            lines.append("*No ships selected yet.*")

        await interaction.response.edit_message(
            content=(
                f"**House:** {self.ship_view.house}\n"
                f"**Commander:** {self.ship_view.commander}\n\n"
                + "\n".join(lines)
                + "\n\nClick a ship to change its quantity."
            ),
            view=self.ship_view
        )

class CommanderModal(discord.ui.Modal, title="Fleet Commander"):
    commander = discord.ui.TextInput(
        label="Commander Name",
        placeholder="Enter the fleet commander's name",
        required=True,
        max_length=100
    )

    def __init__(
        self,
        battle_id: int,
        house: str,
        available_fleet: dict,
        bot,
        user_id: int,
        origin_channel_id: int,
        origin_message_id: int
    ):
        super().__init__()

        self.battle_id = battle_id
        self.house = house
        self.available_fleet = available_fleet
        self.bot = bot
        self.user_id = user_id
        self.origin_channel_id = origin_channel_id
        self.origin_message_id = origin_message_id

    async def on_submit(self, interaction: discord.Interaction):
        commander_name = str(self.commander.value).strip()

        # IMPORTANT:
        # Do NOT reserve/add any ships here.
        # This only moves the user to the ship selection view.

        await interaction.response.edit_message(
            content=(
                f"**House:** {self.house}\n"
                f"**Commander:** {commander_name}\n\n"
                "Select a ship type below to enter the quantity."
            ),
            view=ShipSelectView(
                battle_id=self.battle_id,
                house=self.house,
                available_fleet=self.available_fleet,
                commander=commander_name,
                bot=self.bot,
                user_id=self.user_id,
                origin_channel_id=self.origin_channel_id,
                origin_message_id=self.origin_message_id
            )
        )

    def __init__(self, battle_id, house, fleet, bot, origin_channel_id: int, origin_message_id: int):
        super().__init__()
        self.battle_id = battle_id
        self.house = house
        self.fleet = fleet
        self.bot = bot
        self.origin_channel_id = origin_channel_id
        self.origin_message_id = origin_message_id

    async def on_submit(self, interaction: discord.Interaction):
        commander_name = str(self.commander).strip()
        await interaction.response.defer(ephemeral=True)

        success = database.reserve_battle_fleet_entries(self.battle_id, self.house, self.fleet, commander_name)
        if not success:
            await interaction.followup.send("Insufficient ships available to submit this fleet. Another fleet may have claimed them.", ephemeral=True)
            return

        fleet_str = "\n".join([f"- {config.SHIPS.get(ship_type, {}).get('name', ship_type)}: {amount}" for ship_type, amount in self.fleet.items()])
        await interaction.followup.send(f"Fleet submitted for **{self.house}** under commander **{commander_name}**:\n{fleet_str}", ephemeral=True)
        await refresh_battle_message(self.bot, self.origin_channel_id, self.origin_message_id, self.battle_id, BattleFleetView(self.bot, self.battle_id))
