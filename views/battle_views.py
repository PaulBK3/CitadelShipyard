import discord
import config
import database
import utils
import battle_engine


def build_battle_embed(battle_id, thread_id=None):
    battle = database.get_battle_by_thread(thread_id) if thread_id else database.get_battle(battle_id)
    if not battle:
        return discord.Embed(
            title="Battle",
            description="Battle not found.",
            color=0xff0000
        )

    side_house = None
    side_houses = None

    if thread_id:
        if battle.get("side") == "attacker":
            side_houses = database.get_houses_for_side(battle_id, "attacker")
        elif battle.get("side") == "defender":
            side_houses = database.get_houses_for_side(battle_id, "defender")

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
        fleet_groups = [
            group
            for group in fleet_groups
            if group["house"] in side_houses
        ]

    if fleet_groups:
        for group in fleet_groups:
            house = group["house"]
            commander = group.get("commander") or "Unknown Commander"

            lines = [
                f"{config.SHIPS.get(ship_type, {}).get('name', ship_type)}: {amount}"
                for ship_type, amount in group["ships"].items()
            ]

            embed.add_field(
                name=f"{house} — {commander}",
                value="\n".join(lines),
                inline=False
            )
    else:
        empty_text = (
            f"No fleets registered yet for {side_house}."
            if side_house
            else "No fleets registered yet."
        )

        embed.add_field(
            name="Fleets",
            value=empty_text,
            inline=False
        )

    try:
        embed.set_footer(text=f"Battle ID: {battle_id}")
    except Exception:
        pass

    return embed


async def refresh_battle_message(
    bot,
    channel_id,
    message_id,
    battle_id,
    view
):
    channel = bot.get_channel(channel_id)

    if channel is None:
        return

    try:
        message = await channel.fetch_message(message_id)

        await message.edit(
            embed=build_battle_embed(battle_id, channel.id),
            view=view
        )
    except Exception:
        pass


class BattleFleetView(discord.ui.View):
    def __init__(self, bot, battle_id: int):
        super().__init__(timeout=None)

        self.bot = bot
        self.battle_id = battle_id

        for item in self.children:
            if not isinstance(
                item,
                discord.ui.Button
            ):
                continue

            if item.label == "Create Fleet":
                item.custom_id = (
                    f"create_fleet_{battle_id}"
                )

            elif item.label == "Lock Fleets":
                item.custom_id = (
                    f"lock_fleets_{battle_id}"
                )

            elif item.label == "Remove Fleet":
                item.custom_id = (
                    f"remove_fleet_{battle_id}"
                )

            elif item.label == "Start Battle":
                item.custom_id = (
                    f"start_battle_{battle_id}"
                )

            elif item.label == "Start Next Round":
                item.custom_id = (
                    f"next_round_{battle_id}"
                )

            elif item.label == "Close Battle":
                item.custom_id = (
                    f"close_battle_{battle_id}"
                )

        if (
            bot is not None
            and hasattr(bot, "add_view")
        ):
            bot.add_view(self)
        if bot is not None and hasattr(bot, "add_view"):
            bot.add_view(self)

    @discord.ui.button(
        label="Create Fleet",
        style=discord.ButtonStyle.primary
    )
    async def create_fleet(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        try:
            battle_id = int(button.custom_id.split("_")[-1])
        except (ValueError, IndexError):
            await interaction.response.send_message(
                "Error: Invalid battle ID.",
                ephemeral=True
            )
            return

        # UI-level check for a better immediate error.
        # The database performs the authoritative check again at submission.
        if database.is_battle_fleets_locked(battle_id):
            await interaction.response.send_message(
                "Fleets are locked for this battle. No further fleet creation is allowed.",
                ephemeral=True
            )
            return

        battle = (
            database.get_battle_by_thread(interaction.channel.id)
            or database.get_battle(battle_id)
        )

        if not battle:
            await interaction.response.send_message(
                "Battle not found.",
                ephemeral=True
            )
            return

        side_houses = None

        if battle.get("side") == "attacker":
            side_houses = database.get_houses_for_side(
                battle_id,
                "attacker"
            )
        elif battle.get("side") == "defender":
            side_houses = database.get_houses_for_side(
                battle_id,
                "defender"
            )

        if side_houses:
            houses = [
                house
                for house in side_houses
                if database.get_available_fleet_for_house(house)
            ]
        else:
            houses = [
                house
                for house in database.get_all_houses()
                if database.get_available_fleet_for_house(house)
            ]

        if not houses:
            await interaction.response.send_message(
                "No available houses with ships.",
                ephemeral=True
            )
            return

        view = HouseSelectView(
            battle_id=battle_id,
            houses=houses,
            user_id=interaction.user.id,
            origin_channel_id=interaction.channel.id,
            origin_message_id=interaction.message.id
        )

        await interaction.response.send_message(
            "Choose a house for your fleet:",
            view=view,
            ephemeral=True
        )

    @discord.ui.button(
        label="Lock Fleets",
        style=discord.ButtonStyle.secondary
    )
    async def lock_fleets(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not utils.has_role(
            interaction.user,
            config.SHIP_TEAM_ROLE
        ):
            await interaction.response.send_message(
                "You do not have permission to lock fleets.",
                ephemeral=True
            )
            return

        try:
            battle_id = int(button.custom_id.split("_")[-1])
        except (ValueError, IndexError):
            await interaction.response.send_message(
                "Error: Invalid battle ID.",
                ephemeral=True
            )
            return

        locked = database.is_battle_fleets_locked(battle_id)

        if locked:
            database.unlock_battle_fleets(battle_id)
            status_message = (
                "Fleets are now unlocked for this battle. "
                "Fleet creation is allowed again."
            )
        else:
            database.lock_battle_fleets(battle_id)
            status_message = (
                "Fleets are now locked for this battle. "
                "No further fleet creation is allowed."
            )

        await refresh_battle_message(
            self.bot,
            interaction.channel.id,
            interaction.message.id,
            battle_id,
            BattleFleetView(self.bot, battle_id)
        )

        await interaction.response.send_message(
            status_message,
            ephemeral=True
        )

    @discord.ui.button(
        label="Remove Fleet",
        style=discord.ButtonStyle.danger
    )
    async def remove_fleet(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not utils.has_role(
            interaction.user,
            config.SHIP_TEAM_ROLE
        ):
            await interaction.response.send_message(
                "You do not have permission to remove fleets.",
                ephemeral=True
            )
            return

        try:
            battle_id = int(button.custom_id.split("_")[-1])
        except (ValueError, IndexError):
            await interaction.response.send_message(
                "Error: Invalid battle ID.",
                ephemeral=True
            )
            return

        battle = (
            database.get_battle_by_thread(interaction.channel.id)
            or database.get_battle(battle_id)
        )

        side_houses = None

        if battle and battle.get("side") == "attacker":
            side_houses = database.get_houses_for_side(
                battle_id,
                "attacker"
            )
        elif battle and battle.get("side") == "defender":
            side_houses = database.get_houses_for_side(
                battle_id,
                "defender"
            )

        fleet_groups = database.get_battle_fleet_groups(battle_id)

        if side_houses:
            fleet_groups = [
                group
                for group in fleet_groups
                if group["house"] in side_houses
            ]

        if not fleet_groups:
            await interaction.response.send_message(
                "There are no fleets to remove for this battle.",
                ephemeral=True
            )
            return

        view = RemoveFleetView(
            battle_id=battle_id,
            fleet_groups=fleet_groups,
            user_id=interaction.user.id,
            bot=interaction.client,
            origin_channel_id=interaction.channel.id,
            origin_message_id=interaction.message.id
        )

        await interaction.response.send_message(
            "Select a fleet to remove or delete all fleets:",
            view=view,
            ephemeral=True
        )
    @discord.ui.button(
        label="Start Battle",
        style=discord.ButtonStyle.success
    )
    async def start_battle(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not utils.has_role(
            interaction.user,
            config.SHIP_TEAM_ROLE
        ):
            await interaction.response.send_message(
                "You do not have permission to start battles.",
                ephemeral=True
            )
            return

        try:
            state = battle_engine.initialize_battle(
                self.battle_id
            )

        except ValueError as exc:
            await interaction.response.send_message(
                str(exc),
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "Battle started. **Round 1 is ready to begin.**",
            ephemeral=False
        )

        await refresh_battle_message(
            self.bot,
            interaction.channel.id,
            interaction.message.id,
            self.battle_id,
            BattleCombatView(
                self.bot,
                self.battle_id
            )
        )

    @discord.ui.button(
        label="Close Battle",
        style=discord.ButtonStyle.danger
    )
    async def close_battle(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not utils.has_role(
            interaction.user,
            config.SHIP_TEAM_ROLE
        ):
            await interaction.response.send_message(
                "You do not have permission to close battles.",
                ephemeral=True
            )
            return

        result = battle_engine.close_battle(
            self.battle_id
        )

        await interaction.response.send_message(
            "Battle closed. Permanent fleet numbers have been updated.",
            ephemeral=True
        )

        await refresh_battle_message(
            self.bot,
            interaction.channel.id,
            interaction.message.id,
            self.battle_id,
            BattleFleetView(
                self.bot,
                self.battle_id
            )
        )

class HouseSelectView(discord.ui.View):
    def __init__(
        self,
        battle_id: int,
        houses: list,
        user_id: int,
        origin_channel_id: int,
        origin_message_id: int
    ):
        super().__init__(timeout=None)

        self.battle_id = battle_id
        self.houses = houses
        self.user_id = user_id
        self.origin_channel_id = origin_channel_id
        self.origin_message_id = origin_message_id

        options = [
            discord.SelectOption(
                label=house,
                value=house
            )
            for house in houses
        ]

        house_select = discord.ui.Select(
            placeholder="Choose a house",
            options=options,
            custom_id=f"house_select_{battle_id}",
            min_values=1,
            max_values=1
        )

        house_select.callback = self.house_selected
        self.add_item(house_select)

    async def interaction_check(
        self,
        interaction: discord.Interaction
    ) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Only the original user can choose a house.",
                ephemeral=True
            )
            return False

        return True

    async def house_selected(
        self,
        interaction: discord.Interaction
    ):
        selected_house = interaction.data.get(
            "values",
            [None]
        )[0]

        if not selected_house:
            await interaction.response.send_message(
                "No house selected.",
                ephemeral=True
            )
            return

        # Recheck availability because the list may be stale.
        available_fleet = database.get_available_fleet_for_house(
            selected_house
        )

        if not available_fleet:
            await interaction.response.send_message(
                "No ships are currently available for that house.",
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
        commander_martial: int,
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
        self.commander_martial = commander_martial
        self.bot = bot
        self.user_id = user_id
        self.origin_channel_id = origin_channel_id
        self.origin_message_id = origin_message_id

        # Only store user selections here.
        # Nothing is reserved until final submission.
        self.selected_ships = {
            ship_type: 0
            for ship_type in available_fleet
        }

        for ship_type, max_amount in available_fleet.items():
            ship_name = config.SHIPS.get(
                ship_type,
                {}
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
                await self.ship_selected(
                    interaction,
                    ship_type
                )

            button.callback = callback
            self.add_item(button)

        submit_button = discord.ui.Button(
            label="Submit Fleet",
            style=discord.ButtonStyle.success,
            custom_id=f"submit_fleet_{battle_id}"
        )

        submit_button.callback = self.submit_fleet
        self.add_item(submit_button)

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
            ship_type,
            {}
        ).get("name", ship_type)

        max_amount = self.available_fleet[ship_type]
        current_amount = self.selected_ships.get(
            ship_type,
            0
        )

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
            f"**Admiral:** {self.commander}",
            f"**Martial:** {self.commander_martial}",
            "",
            "**Current Fleet:**"
        ]

        has_ships = False

        for ship_type, amount in self.selected_ships.items():
            if amount > 0:
                has_ships = True

                ship_name = config.SHIPS.get(
                    ship_type,
                    {}
                ).get("name", ship_type)

                lines.append(
                    f"• {ship_name}: {amount}"
                )

        if not has_ships:
            lines.append("*No ships selected.*")

        lines.extend([
            "",
            "Click a ship below to enter the quantity."
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
                "_",
                3
            )[-1]

            amount = self.selected_ships.get(
                ship_type,
                0
            )

            ship_name = config.SHIPS.get(
                ship_type,
                {}
            ).get("name", ship_type)

            item.label = f"{ship_name} ({amount})"

    async def submit_fleet(
        self,
        interaction: discord.Interaction
    ):
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

        # Supply validation intentionally left unchanged.
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
                f"{total_supply/1920} more supply ships."
                f"Add more supply ships.",
                ephemeral=True
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        # The database now owns the authoritative submission logic.
        result = database.submit_battle_fleet(
            battle_id=self.battle_id,
            house=self.house,
            commander=self.commander,
            commander_martial=self.commander_martial,
            fleet_dict=fleet
        )

        if not result["success"]:
            await interaction.followup.send(
                result["message"],
                ephemeral=True
            )
            return

        fleet_str = "\n".join(
            f"- {config.SHIPS.get(ship_type, {}).get('name', ship_type)}: {amount}"
            for ship_type, amount in fleet.items()
        )

        await interaction.followup.send(
            f"Fleet submitted for **{self.house}** "
            f"under **{self.commander}** "
            f"(Martial {self.commander_martial}):\n"
            f"{fleet_str}",
            ephemeral=True
        )

        await refresh_battle_message(
            self.bot,
            self.origin_channel_id,
            self.origin_message_id,
            self.battle_id,
            BattleFleetView(
                self.bot,
                self.battle_id
            )
        )

class RemoveFleetView(discord.ui.View):
    def __init__(
        self,
        battle_id: int,
        fleet_groups: list,
        user_id: int,
        bot,
        origin_channel_id: int,
        origin_message_id: int
    ):
        super().__init__(timeout=None)

        self.battle_id = battle_id
        self.user_id = user_id
        self.bot = bot
        self.origin_channel_id = origin_channel_id
        self.origin_message_id = origin_message_id
        self.selected_fleet_id = None

        options = [
            discord.SelectOption(
                label=(
                    f"{group['house']} — "
                    f"{group.get('commander', 'Unknown Commander')} "
                    f"({sum(group['ships'].values())} ships)"
                ),
                value=group["fleet_id"]
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

    async def interaction_check(
        self,
        interaction: discord.Interaction
    ) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Only the original user can remove fleets.",
                ephemeral=True
            )
            return False

        return True

    async def select_fleet(
        self,
        interaction: discord.Interaction
    ):
        self.selected_fleet_id = interaction.data.get(
            "values",
            [None]
        )[0]

        await interaction.response.defer()

    @discord.ui.button(
    label="Delete Selected Fleet",
    style=discord.ButtonStyle.danger
    )
    async def delete_selected(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not self.selected_fleet_id:
            await interaction.response.send_message(
                "Please select a fleet before deleting.",
                ephemeral=True
            )
            return

        fleet_id = self.selected_fleet_id

        # Delete it first.
        database.delete_battle_fleet(
            self.battle_id,
            fleet_id
        )

        # IMPORTANT:
        # Re-query the database and rebuild the ephemeral removal
        # view. Do not rely on the old select options.
        fleet_groups = database.get_battle_fleet_groups(
            self.battle_id
        )

        # Determine which side/house this removal view belongs to.
        battle = database.get_battle(
            self.battle_id
        )

        side_houses = None

        if battle:
            # If the battle has side mappings, preserve them.
            side_houses = []

            for side in ("attacker", "defender"):
                houses = database.get_houses_for_side(
                    self.battle_id,
                    side
                )

                side_houses.extend(houses)

            if not side_houses:
                side_houses = None

        if side_houses:
            fleet_groups = [
                group
                for group in fleet_groups
                if group["house"] in side_houses
            ]

        # If there are no fleets left, replace the ephemeral
        # Remove Fleet view with a finished message.
        if not fleet_groups:
            await interaction.response.edit_message(
                content=(
                    "The fleet has been removed and its ships released.\n\n"
                    "There are no fleets remaining to remove."
                ),
                view=None
            )

        else:
            # Build a completely fresh removal view.
            new_view = RemoveFleetView(
                battle_id=self.battle_id,
                fleet_groups=fleet_groups,
                user_id=self.user_id,
                bot=self.bot,
                origin_channel_id=self.origin_channel_id,
                origin_message_id=self.origin_message_id
            )

            await interaction.response.edit_message(
                content=(
                    "Fleet removed and ships released.\n\n"
                    "Select another fleet to remove:"
                ),
                view=new_view
            )

        # Also refresh the actual public battle message.
        await refresh_battle_message(
            self.bot,
            self.origin_channel_id,
            self.origin_message_id,
            self.battle_id,
            BattleFleetView(
                self.bot,
                self.battle_id
            )
        )

    @discord.ui.button(
        label="Delete All Fleets",
        style=discord.ButtonStyle.danger
    )
    async def delete_all(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        deleted_count = database.delete_all_battle_fleets(
            self.battle_id
        )

        if deleted_count == 0:
            await interaction.response.send_message(
                "There are no fleets to remove.",
                ephemeral=True
            )
            return

        await refresh_battle_message(
            self.bot,
            self.origin_channel_id,
            self.origin_message_id,
            self.battle_id,
            BattleFleetView(
                self.bot,
                self.battle_id
            )
        )

        await interaction.response.send_message(
            f"Removed {deleted_count} fleet entries. "
            f"Ships have been released.",
            ephemeral=True
        )


class ShipQuantityModal(discord.ui.Modal):
    def __init__(
        self,
        ship_type: str,
        ship_name: str,
        max_amount: int,
        current_amount: int,
        ship_view: ShipSelectView
    ):
        super().__init__(
            title=f"{ship_name} Quantity"
        )

        self.ship_type = ship_type
        self.max_amount = max_amount
        self.ship_view = ship_view

        self.amount = discord.ui.TextInput(
            label=f"{ship_name} amount",
            placeholder=f"Enter 0-{max_amount}",
            default=str(current_amount) if current_amount > 0 else None,
            required=True,
            max_length=10
        )

        self.add_item(self.amount)

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):
        try:
            amount = int(
                str(self.amount.value).strip()
            )
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

        self.ship_view.selected_ships[
            self.ship_type
        ] = amount

        self.ship_view.update_ship_buttons()

        await interaction.response.edit_message(
            content=self.ship_view.get_ship_selection_text(),
            view=self.ship_view
        )


class CommanderModal(
    discord.ui.Modal,
    title="Fleet Admiral"
):
    commander = discord.ui.TextInput(
        label="Admiral Name",
        placeholder="Enter the admiral's name",
        required=True,
        max_length=100
    )

    martial = discord.ui.TextInput(
        label="Martial",
        placeholder="Enter the admiral's Martial stat",
        required=True,
        max_length=3
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

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):
        commander_name = str(
            self.commander.value
        ).strip()

        if not commander_name:
            await interaction.response.send_message(
                "Admiral name cannot be empty.",
                ephemeral=True
            )
            return

        try:
            commander_martial = int(
                str(self.martial.value).strip()
            )
        except ValueError:
            await interaction.response.send_message(
                "Martial must be a whole number.",
                ephemeral=True
            )
            return

        if commander_martial < 0:
            await interaction.response.send_message(
                "Martial cannot be negative.",
                ephemeral=True
            )
            return

        await interaction.response.edit_message(
            content=(
                f"**House:** {self.house}\n"
                f"**Admiral:** {commander_name}\n"
                f"**Martial:** {commander_martial}\n\n"
                "Select a ship type below to enter the quantity."
            ),
            view=ShipSelectView(
                battle_id=self.battle_id,
                house=self.house,
                available_fleet=self.available_fleet,
                commander=commander_name,
                commander_martial=commander_martial,
                bot=self.bot,
                user_id=self.user_id,
                origin_channel_id=self.origin_channel_id,
                origin_message_id=self.origin_message_id
            )
        )

async def publish_round_result(
    bot,
    battle_id,
    result
):
    battle = database.get_battle(battle_id)

    if not battle:
        return

    # Attacker gets the attacker's private view.
    attacker_embed = build_round_result_for_side(
        result,
        "attacker"
    )

    # Defender gets the defender's private view.
    defender_embed = build_round_result_for_side(
        result,
        "defender"
    )

    await send_battle_update(
        bot,
        battle["attacker_thread_id"],
        attacker_embed
    )

    await send_battle_update(
        bot,
        battle["defender_thread_id"],
        defender_embed
    )

    # Each side also gets its own current fleet state.
    await publish_current_fleet_state(
        bot,
        battle_id,
        "attacker",
        result
    )

    await publish_current_fleet_state(
        bot,
        battle_id,
        "defender",
        result
    )


async def publish_retreat_result(
    bot,
    battle_id,
    result
):
    battle = database.get_battle(
        battle_id
    )

    if not battle:
        return

    retreating_side = result[
        "retreating_side"
    ]

    attacking_side = result[
        "attacking_side"
    ]

    # The attacking side sees its own
    # half-damage attack.
    attacking_embed = build_retreat_result_for_side(
        result,
        attacking_side
    )

    # The retreating side sees the attack
    # against them, but NOT the enemy's rolls.
    retreating_embed = build_retreat_result_for_side(
        result,
        retreating_side
    )

    await send_battle_update(
        bot,
        battle[
            f"{attacking_side}_thread_id"
        ],
        attacking_embed
    )

    await send_battle_update(
        bot,
        battle[
            f"{retreating_side}_thread_id"
        ],
        retreating_embed
    )

    await publish_current_fleet_state(
        bot,
        battle_id,
        attacking_side,
        result=None
    )

    await publish_current_fleet_state(
        bot,
        battle_id,
        retreating_side,
        result=result
    )


async def publish_current_fleet_state(
    bot,
    battle_id,
    side,
    result=None
):
    battle = database.get_battle(
        battle_id
    )

    if not battle:
        return

    state = battle_engine.get_live_state(
        battle_id
    )

    fleets = battle_engine.get_side_fleets(
        battle,
        state,
        side
    )

    embed = discord.Embed(
        title="⚓ Your Current Fleet",
        color=0x34495E
    )

    if not fleets:
        embed.description = (
            "You have no fleets remaining."
        )

    else:
        for fleet in fleets:

            lines = []

            for ship_type, ship in (
                fleet["ships"].items()
            ):
                amount = max(
                    0,
                    int(ship["amount"])
                )

                if amount <= 0:
                    continue

                ship_name = config.SHIPS.get(
                    ship_type,
                    {}
                ).get(
                    "name",
                    ship_type
                )

                lines.append(
                    f"• {ship_name}: **{amount}**"
                )

            if not lines:
                lines.append(
                    "• No ships remaining"
                )

            commander = (
                fleet.get("commander")
                or "Unknown"
            )

            embed.add_field(
                name=(
                    f"{fleet['house']} "
                    f"— {commander}"
                ),
                value="\n".join(lines),
                inline=False
            )

    # Show losses suffered by your side this round.
    if result:

        enemy_side = (
        "defender"
        if side == "attacker"
        else "attacker"
        )

        enemy_result = result[enemy_side]

        embed.add_field(
            name="Your Losses This Round",
            value=format_ship_losses(
                enemy_result["destroyed_by_type"]
            ),
            inline=False
        )

        thread_id = (
            battle["attacker_thread_id"]
            if side == "attacker"
            else battle["defender_thread_id"]
        )

        await send_battle_update(
            bot,
            thread_id,
            embed
        )

async def send_battle_update(
    bot,
    thread_id,
    embed
):
    if not thread_id:
        return

    channel = bot.get_channel(
        int(thread_id)
    )

    if channel is None:
        try:
            channel = await bot.fetch_channel(
                int(thread_id)
            )
        except Exception:
            return

    await channel.send(
        embed=embed
    )

def build_round_result_for_side(
    result,
    side
):
    own = result[side]

    embed = discord.Embed(
        title=f"⚔️ Round {result['round']}",
        color=0x8B0000
    )

    embed.add_field(
        name="Your Attack",
        value=(
            f"Admiral roll: "
            f"**{own['admiral_dice']}**\n"
            f"Ship dice: "
            f"**{own['ship_dice']}**\n"
            f"Damage dealt: "
            f"**{own['damage']:.2f}**"
        ),
        inline=False
    )

    embed.add_field(
        name="Enemy Losses",
        value=format_ship_losses(
            own["destroyed_by_type"]
        ),
        inline=False
    )

    return embed

def format_ship_losses(
    destroyed_by_type
):
    if not destroyed_by_type:
        return "• No ships lost"

    lines = []

    for ship_type, amount in destroyed_by_type.items():

        ship_name = config.SHIPS.get(
            ship_type,
            {}
        ).get(
            "name",
            ship_type
        )

        lines.append(
            f"• **{amount} × {ship_name}**"
        )

    return "\n".join(lines)

def build_retreat_result_for_side(
    result,
    side
):
    retreating_side = result[
        "retreating_side"
    ]

    attacking_side = result[
        "attacking_side"
    ]

    embed = discord.Embed(
        title="🏳️ Retreat",
        color=0xCC8800
    )

    if side == attacking_side:

        embed.description = (
            "The enemy has retreated. "
            "Your fleet received one free attack "
            "at half damage."
        )

        embed.add_field(
            name="Your Free Attack",
            value=(
                f"Admiral roll: "
                f"**{result['admiral_dice']}**\n"
                f"Ship dice: "
                f"**{result['ship_dice']}**\n"
                f"Half damage: "
                f"**{result['damage']:.2f}**"
            ),
            inline=False
        )

        embed.add_field(
            name="Enemy Losses",
            value=format_ship_losses(
                result["destroyed_by_type"]
            ),
            inline=False
        )

    else:

        embed.description = (
            "Your fleet has retreated. "
            "The enemy received one free attack "
            "at half damage."
        )

        embed.add_field(
            name="Your Losses",
            value=format_ship_losses(
                result["destroyed_by_type"]
            ),
            inline=False
        )

        embed.add_field(
            name="Enemy Attack",
            value=(
                "The enemy's attack was resolved, "
                "but its rolls and damage are hidden."
            ),
            inline=False
        )

    return embed

class BattleCombatView(discord.ui.View):

    def __init__(self, bot, battle_id: int):
        super().__init__(timeout=None)

        self.bot = bot
        self.battle_id = battle_id

        for item in self.children:
            if not isinstance(
                item,
                discord.ui.Button
            ):
                continue

            if item.label == "Start Next Round":
                item.custom_id = (
                    f"next_round_{battle_id}"
                )

            elif item.label == "Close Battle":
                item.custom_id = (
                    f"close_battle_{battle_id}"
                )

            elif item.label == "Retreat Attacker":
                item.custom_id = (
                    f"retreat_attacker_{battle_id}"
                )

            elif item.label == "Retreat Defender":
                item.custom_id = (
                    f"retreat_defender_{battle_id}"
                )

        if (
            bot is not None
            and hasattr(bot, "add_view")
        ):
            bot.add_view(self)

    @discord.ui.button(
        label="Start Next Round",
        style=discord.ButtonStyle.success
    )
    async def next_round(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not utils.has_role(
            interaction.user,
            config.SHIP_TEAM_ROLE
        ):
            await interaction.response.send_message(
                "You do not have permission to start rounds.",
                ephemeral=True
            )
            return

        try:
            result = battle_engine.run_round(
                self.battle_id
            )

        except ValueError as exc:
            await interaction.response.send_message(
                str(exc),
                ephemeral=True
            )
            return

        await publish_round_result(
            self.bot,
            self.battle_id,
            result
        )

        await refresh_battle_message(
            self.bot,
            interaction.channel.id,
            interaction.message.id,
            self.battle_id,
            BattleCombatView(
                self.bot,
                self.battle_id
            )
        )

    @discord.ui.button(
        label="Retreat Attacker",
        style=discord.ButtonStyle.danger
    )
    async def retreat_attacker(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await self._retreat(
            interaction,
            "attacker"
        )

    @discord.ui.button(
        label="Retreat Defender",
        style=discord.ButtonStyle.danger
    )
    async def retreat_defender(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await self._retreat(
            interaction,
            "defender"
        )

    @discord.ui.button(
        label="Close Battle",
        style=discord.ButtonStyle.danger
    )
    async def close_battle(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not utils.has_role(
            interaction.user,
            config.SHIP_TEAM_ROLE
        ):
            await interaction.response.send_message(
                "You do not have permission to close battles.",
                ephemeral=True
            )
            return

        result = battle_engine.close_battle(
            self.battle_id
        )

        await interaction.response.send_message(
            "Battle closed. Permanent fleet numbers have been updated.",
            ephemeral=True
        )

        await refresh_battle_message(
            self.bot,
            interaction.channel.id,
            interaction.message.id,
            self.battle_id,
            BattleFleetView(
                self.bot,
                self.battle_id
            )
        )

    async def _retreat(
        self,
        interaction,
        side
    ):
        if not utils.has_role(
            interaction.user,
            config.SHIP_TEAM_ROLE
        ):
            await interaction.response.send_message(
                "You do not have permission to declare retreats.",
                ephemeral=True
            )
            return

        battle = database.get_battle(
            self.battle_id
        )

        if not battle:
            await interaction.response.send_message(
                "Battle not found.",
                ephemeral=True
            )
            return

        if battle["status"] != "active":
            await interaction.response.send_message(
                "The battle is not active.",
                ephemeral=True
            )
            return

        database.set_battle_retreat(
            self.battle_id,
            side,
            True
        )

        updated = database.get_battle(
            self.battle_id
        )

        # Both sides retreat → staff simply closes battle.
        if (
            updated["attacker_retreat"]
            and updated["defender_retreat"]
        ):
            await interaction.response.send_message(
                "Both sides have chosen to retreat. "
                "Staff can now close the battle.",
                ephemeral=False
            )

            return

        # One side retreats → immediately resolve the
        # opponent's free half-damage attack.
        result = battle_engine.resolve_retreat_round(
            self.battle_id,
            side
        )

        await publish_retreat_result(
            self.bot,
            self.battle_id,
            result
        )

        await refresh_battle_message(
            self.bot,
            interaction.channel.id,
            interaction.message.id,
            self.battle_id,
            BattleCombatView(
                self.bot,
                self.battle_id
            )
        )