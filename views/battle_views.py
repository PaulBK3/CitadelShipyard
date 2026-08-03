import discord
import config
import database
import utils


class BattleFleetView(discord.ui.View):
    def __init__(self, battle_id: int):
        super().__init__(timeout=None)
        self.battle_id = battle_id
        # Set the custom_id to include the battle_id so it persists
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.label == "Create Fleet":
                item.custom_id = f"create_fleet_{battle_id}"

    @discord.ui.button(label="Create Fleet", style=discord.ButtonStyle.primary)
    async def create_fleet(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Extract battle_id from custom_id (format: create_fleet_{battle_id})
        try:
            battle_id = int(button.custom_id.split('_')[-1])
        except (ValueError, IndexError):
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send("Error: Invalid battle ID.", ephemeral=True)
            return
        
        # Get all houses with ships available
        houses = database.get_all_houses()
        if not houses:
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send("No houses available.", ephemeral=True)
            return
        
        # Create house selection view
        view = HouseSelectView(battle_id, houses)
        await interaction.response.send_message("Select a house:", view=view, ephemeral=True)


class HouseSelectView(discord.ui.View):
    def __init__(self, battle_id: int, houses: list):
        super().__init__()
        self.battle_id = battle_id
        
        # Create select dropdown with house options
        select = discord.ui.Select(
            placeholder="Choose a house",
            options=[discord.SelectOption(label=house, value=house) for house in houses],
            custom_id=f"house_select_{battle_id}"
        )
        select.callback = self.select_house
        self.add_item(select)
    
    async def select_house(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Get selected house
        house = interaction.data['values'][0]
        
        # Get available fleet
        available_fleet = database.get_fleet_for_house(house)
        if not available_fleet:
            await interaction.followup.send("No ships available in this fleet.", ephemeral=True)
            return
        
        # Show ship selection view
        embed = discord.Embed(
            title=f"Select Ships for {house}",
            description="Choose ships to add to the battle fleet."
        )
        view = ShipSelectView(self.battle_id, house, available_fleet)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class FleetModal(discord.ui.Modal, title="Create Battle Fleet"):
    def __init__(self, battle_id):
        super().__init__()
        self.battle_id = battle_id

    house_select = discord.ui.TextInput(
        label="House Name",
        placeholder="Enter your house name",
        required=True,
        max_length=100
    )

    ship_inputs = []

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        house = self.house_select.value.strip()

        # Get battle info
        battle = database.get_battle(self.battle_id)
        if not battle:
            await interaction.followup.send("Battle not found.", ephemeral=True)
            return

        # Get available fleet
        available_fleet = database.get_fleet_for_house(house)
        if not available_fleet:
            await interaction.followup.send("No ships available in this fleet.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Select Ships for {house}",
            description="Choose ships to add to the battle fleet."
        )

        view = ShipSelectView(self.battle_id, house, available_fleet)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class ShipSelectView(discord.ui.View):
    def __init__(self, battle_id, house, available_fleet):
        super().__init__()
        self.battle_id = battle_id
        self.house = house
        self.available_fleet = available_fleet
        self.selected_ships = {}

        # Add select for each ship type
        for ship_type, max_amount in available_fleet.items():
            ship_name = config.SHIPS.get(ship_type, {}).get("name", ship_type)
            select = discord.ui.Select(
                placeholder=f"Select {ship_name} (max {max_amount})",
                options=[discord.SelectOption(label=str(i), value=str(i)) for i in range(max_amount + 1)],
                custom_id=f"select_{ship_type}"
            )
            select.callback = self.update_selection
            self.add_item(select)

    async def update_selection(self, interaction: discord.Interaction):
        # Update selected amounts
        for item in self.children:
            if isinstance(item, discord.ui.Select):
                ship_type = item.custom_id[7:]  # remove "select_"
                amount = int(item.values[0]) if item.values else 0
                self.selected_ships[ship_type] = amount
        await interaction.response.defer()

    @discord.ui.button(label="Submit Fleet", style=discord.ButtonStyle.green)
    async def submit_fleet(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        # Collect selected amounts
        fleet = {ship_type: amount for ship_type, amount in self.selected_ships.items() if amount > 0}
        if not fleet:
            await interaction.followup.send("No ships selected.", ephemeral=True)
            return

        total_supply = 0
        for ship_type, amount in fleet.items():
            ship_data = config.SHIPS.get(ship_type)
            if ship_data:
                total_supply += ship_data["supply_cost"] * amount

        if total_supply > 0:
            await interaction.followup.send(
                f"Insufficient supply! Your fleet requires {total_supply} supply points. Add more supply ships.",
                ephemeral=True
            )
            return

        # Check if already submitted
        existing_fleet = database.get_battle_fleet(self.battle_id, self.house)
        if existing_fleet:
            await interaction.followup.send("Fleet already submitted for this house.", ephemeral=True)
            return

        # Add to battle fleet
        for ship_type, amount in fleet.items():
            database.add_battle_fleet_entry(self.battle_id, self.house, ship_type, amount)

        # Send confirmation
        fleet_str = "\n".join([f"- {config.SHIPS.get(ship_type, {}).get('name', ship_type)}: {amount}" for ship_type, amount in fleet.items()])
        await interaction.followup.send(
            f"Fleet submitted for **{self.house}**:\n{fleet_str}",
            ephemeral=True
        )