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

    async def house_selected(self, interaction: discord.Interaction):
        selected_house = interaction.data.get("values", [None])[0]
        if not selected_house:
            await interaction.response.send_message("No house selected.", ephemeral=True)
            return

        available_fleet = database.get_available_fleet_for_house(selected_house)
        if not available_fleet:
            await interaction.response.send_message("No ships available for that house.", ephemeral=True)
            return

        await interaction.response.edit_message(
            content=f"Select ships for **{selected_house}**:",
            view=ShipSelectView(
                self.battle_id,
                selected_house,
                available_fleet,
                self.user_id,
                self.origin_channel_id,
                self.origin_message_id
            )
        )


class ShipSelectView(discord.ui.View):
    def __init__(self, battle_id: int, house: str, available_fleet: dict, user_id: int, origin_channel_id: int, origin_message_id: int):
        super().__init__(timeout=None)
        self.battle_id = battle_id
        self.house = house
        self.available_fleet = available_fleet
        self.user_id = user_id
        self.origin_channel_id = origin_channel_id
        self.origin_message_id = origin_message_id
        self.selected_ships = {}

        for ship_type, max_amount in available_fleet.items():
            ship_name = config.SHIPS.get(ship_type, {}).get("name", ship_type)
            if max_amount <= 24:
                options = [discord.SelectOption(label=str(i), value=str(i)) for i in range(max_amount + 1)]
            else:
                options = [discord.SelectOption(label=str(i), value=str(i)) for i in range(24)]
                options.append(discord.SelectOption(label="24+ (enter exact amount)", value="24plus"))
            select = discord.ui.Select(
                placeholder=f"{ship_name} (max {max_amount})",
                options=options,
                custom_id=f"ship_select_{ship_type}",
                min_values=1,
                max_values=1
            )
            select.callback = self.update_selection
            self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Only the original user can select ships.", ephemeral=True)
            return False
        return True

    async def update_selection(self, interaction: discord.Interaction):
        for item in self.children:
            if isinstance(item, discord.ui.Select):
                ship_type = item.custom_id.replace("ship_select_", "")
                amount = int(item.values[0]) if item.values else 0
                self.selected_ships[ship_type] = amount
        await interaction.response.defer()

    @discord.ui.button(label="Submit Fleet", style=discord.ButtonStyle.green)
    async def submit_fleet(self, interaction: discord.Interaction, button: discord.ui.Button):
        fleet = {ship_type: amount for ship_type, amount in self.selected_ships.items() if amount > 0}
        if not fleet:
            await interaction.response.send_message("No ships selected.", ephemeral=True)
            return

        total_supply = 0
        for ship_type, amount in fleet.items():
            ship_data = config.SHIPS.get(ship_type)
            if ship_data:
                total_supply += ship_data.get("supply_cost", 0) * amount

        if total_supply > 0:
            await interaction.response.send_message(
                f"Insufficient supply! Your fleet requires {total_supply} supply points. Add more supply ships.",
                ephemeral=True
            )
            return

        large_ship_types = [ship_type for ship_type, amount in self.selected_ships.items() if amount == "24plus"]
        if large_ship_types:
            modal = ShipQuantityModal(
                self.battle_id,
                self.house,
                self.selected_ships,
                self.available_fleet,
                interaction.client,
                self.origin_channel_id,
                self.origin_message_id,
                large_ship_types
            )
            await interaction.response.send_modal(modal)
            return

        modal = CommanderModal(
            self.battle_id,
            self.house,
            fleet,
            interaction.client,
            self.origin_channel_id,
            self.origin_message_id
        )
        await interaction.response.send_modal(modal)


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
    def __init__(self, battle_id, house, selected_ships, available_fleet, bot, origin_channel_id: int, origin_message_id: int, large_ship_types: list):
        super().__init__(title="Enter Large Ship Amounts")
        self.battle_id = battle_id
        self.house = house
        self.selected_ships = selected_ships
        self.available_fleet = available_fleet
        self.bot = bot
        self.origin_channel_id = origin_channel_id
        self.origin_message_id = origin_message_id
        self.large_ship_types = large_ship_types

        for ship_type in large_ship_types:
            max_amount = available_fleet.get(ship_type, 0)
            ship_name = config.SHIPS.get(ship_type, {}).get("name", ship_type)
            self.add_item(discord.ui.TextInput(
                label=f"{ship_name} amount (max {max_amount})",
                placeholder=str(max_amount),
                required=True,
                max_length=5
            ))

    async def on_submit(self, interaction: discord.Interaction):
        fields = [item for item in self.children if isinstance(item, discord.ui.TextInput)]
        for ship_type, field in zip(self.large_ship_types, fields):
            try:
                amount = int(str(field.value).strip())
            except ValueError:
                await interaction.response.send_message(f"Invalid amount for {ship_type}. Please enter a number.", ephemeral=True)
                return

            max_amount = self.available_fleet.get(ship_type, 0)
            if amount < 0 or amount > max_amount:
                await interaction.response.send_message(
                    f"Amount for {ship_type} must be between 0 and {max_amount}.",
                    ephemeral=True
                )
                return

            self.selected_ships[ship_type] = amount

        fleet = {ship_type: amount for ship_type, amount in self.selected_ships.items() if isinstance(amount, int) and amount > 0}
        if not fleet:
            await interaction.response.send_message("No ships selected.", ephemeral=True)
            return

        total_supply = 0
        for ship_type, amount in fleet.items():
            ship_data = config.SHIPS.get(ship_type)
            if ship_data:
                total_supply += ship_data.get("supply_cost", 0) * amount

        if total_supply > 0:
            await interaction.response.send_message(
                f"Insufficient supply! Your fleet requires {total_supply} supply points. Add more supply ships.",
                ephemeral=True
            )
            return

        modal = CommanderModal(
            self.battle_id,
            self.house,
            fleet,
            self.bot,
            self.origin_channel_id,
            self.origin_message_id
        )
        await interaction.response.send_modal(modal)


class CommanderModal(discord.ui.Modal, title="Fleet Commander"):
    commander = discord.ui.TextInput(
        label="Commander Name",
        placeholder="Enter the fleet commander's name",
        required=True,
        max_length=100
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
