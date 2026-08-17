""" import discord
import config
import naval_rules
import database
import utils
from discord.ext.modal_paginator import ModalPaginator, PaginatorModal


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

        # Show house selection view first; after selecting a house the merged modal opens
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

class FleetPaginator(ModalPaginator):
    def __init__(
        self,
        *,
        battle_id: int,
        house: str,
        available_fleet: dict,
        bot,
        origin_channel_id: int,
        origin_message_id: int,
        required_stat: str | None,
        author_id: int,
    ):
        super().__init__(
            author_id=author_id,
            can_go_back=True,
            disable_after=True,
        )

        self.battle_id = battle_id
        self.house = house
        self.available_fleet = available_fleet
        self.bot = bot
        self.origin_channel_id = origin_channel_id
        self.origin_message_id = origin_message_id
        self.required_stat = required_stat
        self.ship_pages = []
        #
        # Commander page
        #
        commander = PaginatorModal(
            title="Fleet Commander",
            required=True,
        )

        commander.add_input(
            label="Commander Name",
            required=True,
            max_length=100,
        )

        commander.add_input(
            label=(
                "Commander Stewardship"
                if required_stat == "stewardship"
                else (
                    "Commander Martial"
                    if required_stat == "martial"
                    else "Commander Stat"
                )
            ),
            required=True,
            max_length=5,
        )

        self.add_modal(commander)

        #
        # Ship pages
        #
        ships = list(available_fleet.items())

        PAGE_SIZE = 5

        for page_start in range(0, len(ships), PAGE_SIZE):

            modal = PaginatorModal(
                title=f"Fleet Ships ({page_start // PAGE_SIZE + 1})",
                required=False,
            )

            for ship_type, max_amount in ships[page_start:page_start + PAGE_SIZE]:

                ship_name = config.SHIPS.get(
                    ship_type,
                    {},
                ).get(
                    "name",
                    ship_type,
                )

                modal.add_input(
                    label=f"{ship_name} (max {max_amount})"[:45],
                    required=False,
                    placeholder="0",
                    max_length=6,
                )

            self.add_modal(modal)

    def _is_supply(self, ship_type: str):
        ship = config.SHIPS.get(ship_type, {})
        return (
            "supply" in ship.get("name", "").lower()
            or ship_type.lower().startswith("supply")
        )

    async def on_finish(self, interaction: discord.Interaction):

        #
        # Extract commander
        #

        pages = list(self)

        commander_modal, commander_fields = pages[0]

        commander_name = commander_fields[0].value.strip()

        try:
            commander_stat = int(commander_fields[1].value)
        except ValueError:
            await interaction.response.send_message(
                "Commander stat must be a number.",
                ephemeral=True,
            )
            return

        #
        # Extract ships
        #

        selected = {}

        ship_types = list(self.available_fleet.keys())

        index = 0

        for modal, fields in pages[1:]:

            for field in fields:

                ship_type = ship_types[index]
                index += 1

                raw = (field.value or "").strip()

                if raw == "":
                    continue

                try:
                    amount = int(raw)
                except ValueError:
                    await interaction.response.send_message(
                        f"Invalid amount for {ship_type}.",
                        ephemeral=True,
                    )
                    return

                max_amount = self.available_fleet[ship_type]

                if amount < 0 or amount > max_amount:
                    await interaction.response.send_message(
                        f"{ship_type} must be between 0 and {max_amount}.",
                        ephemeral=True,
                    )
                    return

                if amount:
                    selected[ship_type] = amount

                #
        # Validate fleet
        #

        if not selected:
            await interaction.response.send_message(
                "You must select at least one ship.",
                ephemeral=True,
            )
            return

        non_supply_count = sum(
            amount
            for ship_type, amount in selected.items()
            if not self._is_supply(ship_type)
        )

        supply_count = sum(
            amount
            for ship_type, amount in selected.items()
            if self._is_supply(ship_type)
        )

        if non_supply_count < 20:
            await interaction.response.send_message(
                f"A fleet must contain at least 20 non-supply ships "
                f"(currently {non_supply_count}).",
                ephemeral=True,
            )
            return

        supply_contrib = supply_count // 5

        fleet_total = non_supply_count + supply_contrib

        max_allowed = 20 + commander_stat

        if fleet_total > max_allowed:
            await interaction.response.send_message(
                f"Fleet exceeds commander capacity "
                f"({fleet_total}/{max_allowed}).",
                ephemeral=True,
            )
            return

        #
        # Supply validation
        #

        total_supply = 0

        for ship_type, amount in selected.items():

            ship = config.SHIPS.get(ship_type)

            if ship:

                total_supply += (
                    ship.get("supply_cost", 0)
                    * amount
                )

        if total_supply > 0:
            await interaction.response.send_message(
                f"Insufficient supply. "
                f"This fleet requires {total_supply} supply.",
                ephemeral=True,
            )
            return

        #
        # Reserve ships
        #

        success = database.reserve_battle_fleet_entries(
            self.battle_id,
            self.house,
            selected,
            commander_name,
        )

        if not success:
            await interaction.response.send_message(
                "Those ships are no longer available. "
                "Another fleet may have claimed them.",
                ephemeral=True,
            )
            return

        #
        # Refresh battle embed
        #

        await refresh_battle_message(
            self.bot,
            self.origin_channel_id,
            self.origin_message_id,
            self.battle_id,
            BattleFleetView(
                self.bot,
                self.battle_id,
            ),
        )

        fleet_lines = [
            f"- {config.SHIPS.get(ship_type, {}).get('name', ship_type)}: {amount}"
            for ship_type, amount in selected.items()
        ]

        embed = discord.Embed(
            title="Fleet Submitted",
            description=(
                f"House: **{self.house}**\n"
                f"Commander: **{commander_name}**"
            ),
            color=discord.Color.green(),
        )

        embed.add_field(
            name="Ships",
            value="\n".join(fleet_lines),
            inline=False,
        )

        await interaction.response.send_message(
            embed=embed
        )

class HouseSelectView(discord.ui.View):
    def __init__(self, battle_id: int, houses: list, user_id: int, origin_channel_id: int, origin_message_id: int, commander_name: str = None, commander_martial: int = 0):
        super().__init__(timeout=None)
        self.battle_id = battle_id
        self.houses = houses
        self.user_id = user_id
        self.origin_channel_id = origin_channel_id
        self.origin_message_id = origin_message_id
        self.commander_name = commander_name
        try:
            self.commander_martial = int(commander_martial) if commander_martial is not None else 0
        except (ValueError, TypeError):
            self.commander_martial = 0

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
        # Determine required stat from the selected house culture
        rules = naval_rules.get_culture_rules(selected_house) or {}
        fr = rules.get("fleet_rules", {}) if rules else {}
        required_stat = fr.get("stat") if fr else None

        paginator = FleetPaginator(
            battle_id=self.battle_id,
            house=selected_house,
            available_fleet=available_fleet,
            bot=interaction.client,
            origin_channel_id=self.origin_channel_id,
            origin_message_id=self.origin_message_id,
            required_stat=required_stat,
            author_id=interaction.user.id,
        )

        await paginator.send(interaction, ephemeral=True)

""" await interaction.response.send_modal(
            CommanderModal(
                self.battle_id,
                selected_house,
                available_fleet,
                interaction.client,
                self.origin_channel_id,
                self.origin_message_id,
                required_stat=required_stat
            )
        ) """




""" 
class CommanderModal(discord.ui.Modal, title="Fleet Commander"):
    submit_label = "Next"

    def __init__(self, battle_id, house, available_fleet, bot, origin_channel_id: int, origin_message_id: int, required_stat: str = None, previous_inputs: dict = None, error_message: str = None):
        super().__init__()
        self.battle_id = battle_id
        self.house = house
        self.available_fleet = available_fleet
        self.bot = bot
        self.origin_channel_id = origin_channel_id
        self.origin_message_id = origin_message_id
        self.required_stat = required_stat

        # show error if present
        if error_message:
            err = discord.ui.TextInput(
                label="Error",
                style=discord.TextStyle.paragraph,
                required=False,
                default=error_message,
                max_length=400
            )
            self.add_item(err)

        # prefill if provided
        cmd_default = ""
        stat_default = ""
        if previous_inputs:
            cmd_default = previous_inputs.get("commander_name", "")
            stat_default = previous_inputs.get("commander_stat", "")

        self.commander_name = discord.ui.TextInput(
            label="Commander Name",
            placeholder="Enter the fleet commander's name",
            required=True,
            max_length=100,
            default=cmd_default
        )
        self.add_item(self.commander_name)

        stat_label = "Commander Stewardship" if required_stat == "stewardship" else ("Commander Martial" if required_stat == "martial" else "Commander Stat")
        self.commander_stat = discord.ui.TextInput(
            label=stat_label,
            placeholder="Enter admiral stat (number)",
            required=True,
            max_length=5,
            default=stat_default
        )
        self.add_item(self.commander_stat)

    async def on_submit(self, interaction: discord.Interaction):
        # on next, open ShipsModal starting at index 0
        commander_name = str(self.commander_name.value).strip() if getattr(self.commander_name, 'value', None) else str(self.commander_name.default or "").strip()
        commander_stat = None
        try:
            commander_stat = int(str(self.commander_stat.value).strip()) if getattr(self.commander_stat, 'value', None) and str(self.commander_stat.value).strip() != "" else int(str(self.commander_stat.default).strip()) if self.commander_stat.default else 0
        except (ValueError, TypeError):
            commander_stat = 0

        await interaction.response.send_modal(ShipsModal(self.battle_id, self.house, self.available_fleet, self.bot, self.origin_channel_id, self.origin_message_id, required_stat=self.required_stat, commander_name=commander_name, commander_stat=commander_stat, start_index=0, collected={} ))


class ShipsModal(discord.ui.Modal, title="Enter Ship Amounts"):
    PAGE_SIZE = 4  # max ship input fields per modal (reserve 1 slot if error used)

    def __init__(self, battle_id, house, available_fleet, bot, origin_channel_id: int, origin_message_id: int, required_stat: str = None, commander_name: str = None, commander_stat: int = 0, start_index: int = 0, collected: dict = None, error_message: str = None):
        super().__init__()
        self.battle_id = battle_id
        self.house = house
        self.available_fleet = available_fleet
        self.bot = bot
        self.origin_channel_id = origin_channel_id
        self.origin_message_id = origin_message_id
        self.required_stat = required_stat
        self.commander_name = commander_name
        self.commander_stat = commander_stat or 0
        self.start_index = start_index
        self.collected = collected or {}

        # optional error field (uses one slot)
        if error_message:
            err = discord.ui.TextInput(
                label="Error",
                style=discord.TextStyle.paragraph,
                required=False,
                default=error_message,
                max_length=400
            )
            self.add_item(err)

        # build page of ship inputs
        ship_types = list(self.available_fleet.keys())
        end = min(len(ship_types), start_index + self.PAGE_SIZE)
        self.page_ship_types = ship_types[start_index:end]

        for ship_type in self.page_ship_types:
            max_amount = self.available_fleet.get(ship_type, 0)
            ship_name = config.SHIPS.get(ship_type, {}).get("name", ship_type)
            label = f"{ship_name} (max {max_amount})"
            if len(label) > 45:
                label = label[:42] + "..."
            default_val = self.collected.get(ship_type, "")
            self.add_item(discord.ui.TextInput(
                label=label,
                placeholder="0",
                required=False,
                max_length=6,
                default=str(default_val) if default_val is not None else ""
            ))

    async def on_submit(self, interaction: discord.Interaction):
        # collect current page inputs
        fields = [item for item in self.children if isinstance(item, discord.ui.TextInput)]
        # if error field present, skip it
        if fields and fields[0].label == "Error":
            fields = fields[1:]

        for ship_type, field in zip(self.page_ship_types, fields):
            raw = str(getattr(field, 'value', None) or field.default or "").strip()
            try:
                amt = int(raw) if raw != "" else 0
            except ValueError:
                # reopen same page with error
                self.collected[ship_type] = raw
                await interaction.response.send_modal(ShipsModal(self.battle_id, self.house, self.available_fleet, self.bot, self.origin_channel_id, self.origin_message_id, required_stat=self.required_stat, commander_name=self.commander_name, commander_stat=self.commander_stat, start_index=self.start_index, collected=self.collected, error_message=f"Invalid number for {ship_type}."))
                return

            max_amount = self.available_fleet.get(ship_type, 0)
            if amt < 0 or amt > max_amount:
                self.collected[ship_type] = raw
                await interaction.response.send_modal(ShipsModal(self.battle_id, self.house, self.available_fleet, self.bot, self.origin_channel_id, self.origin_message_id, required_stat=self.required_stat, commander_name=self.commander_name, commander_stat=self.commander_stat, start_index=self.start_index, collected=self.collected, error_message=f"Amount for {ship_type} must be between 0 and {max_amount}."))
                return

            if amt > 0:
                self.collected[ship_type] = amt
            else:
                # ensure cleared
                self.collected.pop(ship_type, None)

        # determine if more pages remain
        ship_types = list(self.available_fleet.keys())
        next_index = self.start_index + self.PAGE_SIZE
        if next_index < len(ship_types):
            # open next page
            await interaction.response.send_modal(ShipsModal(self.battle_id, self.house, self.available_fleet, self.bot, self.origin_channel_id, self.origin_message_id, required_stat=self.required_stat, commander_name=self.commander_name, commander_stat=self.commander_stat, start_index=next_index, collected=self.collected))
            return

        # final validation on collected
        selected = {k: v for k, v in self.collected.items() if isinstance(v, int) and v > 0}
        if not selected:
            await interaction.response.send_modal(ShipsModal(self.battle_id, self.house, self.available_fleet, self.bot, self.origin_channel_id, self.origin_message_id, required_stat=self.required_stat, commander_name=self.commander_name, commander_stat=self.commander_stat, start_index=0, collected=self.collected, error_message="No ships selected."))
            return

        def is_supply_type(ship_type: str) -> bool:
            ship_info = config.SHIPS.get(ship_type, {})
            name = ship_info.get("name", "")
            return "supply" in name.lower() or ship_type.lower().startswith("supply")

        non_supply_count = sum(v for k, v in selected.items() if not is_supply_type(k))
        supply_count = sum(v for k, v in selected.items() if is_supply_type(k))

        if non_supply_count < 20:
            await interaction.response.send_modal(ShipsModal(self.battle_id, self.house, self.available_fleet, self.bot, self.origin_channel_id, self.origin_message_id, required_stat=self.required_stat, commander_name=self.commander_name, commander_stat=self.commander_stat, start_index=0, collected=self.collected, error_message=f"A fleet must include at least 20 non-supply ships (you selected {non_supply_count})."))
            return

        supply_contrib = supply_count // 5
        total_for_cap = non_supply_count + supply_contrib
        max_allowed = 20 + (self.commander_stat or 0)
        if total_for_cap > max_allowed:
            await interaction.response.send_modal(ShipsModal(self.battle_id, self.house, self.available_fleet, self.bot, self.origin_channel_id, self.origin_message_id, required_stat=self.required_stat, commander_name=self.commander_name, commander_stat=self.commander_stat, start_index=0, collected=self.collected, error_message=f"Fleet exceeds maximum allowed ships: {total_for_cap} > {max_allowed}."))
            return

        # supply check (if supply_cost logic still used)
        total_supply = 0
        for ship_type, amount in selected.items():
            ship_data = config.SHIPS.get(ship_type)
            if ship_data:
                total_supply += ship_data.get("supply_cost", 0) * amount

        if total_supply > 0:
            await interaction.response.send_modal(ShipsModal(self.battle_id, self.house, self.available_fleet, self.bot, self.origin_channel_id, self.origin_message_id, required_stat=self.required_stat, commander_name=self.commander_name, commander_stat=self.commander_stat, start_index=0, collected=self.collected, error_message=f"Insufficient supply! Your fleet requires {total_supply} supply points."))
            return

        commander_name = self.commander_name or "Unknown Commander"
        success = database.reserve_battle_fleet_entries(self.battle_id, self.house, selected, commander_name)
        if not success:
            await interaction.response.send_modal(ShipsModal(self.battle_id, self.house, self.available_fleet, self.bot, self.origin_channel_id, self.origin_message_id, required_stat=self.required_stat, commander_name=self.commander_name, commander_stat=self.commander_stat, start_index=0, collected=self.collected, error_message="Insufficient ships available to submit this fleet. Another fleet may have claimed them."))
            return

        fleet_str = "\n".join([f"- {config.SHIPS.get(ship_type, {}).get('name', ship_type)}: {amount}" for ship_type, amount in selected.items()])
        await interaction.response.send_message(f"Fleet submitted for **{self.house}** under commander **{commander_name}**:\n{fleet_str}", ephemeral=True)
        await refresh_battle_message(self.bot, self.origin_channel_id, self.origin_message_id, self.battle_id, BattleFleetView(self.bot, self.battle_id))
 """



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





 """