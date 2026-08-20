import random

import config
import database


FINAL_DAMAGE_MULTIPLIER = 2.5
MAX_ROUNDS = 20


def is_supply_ship(ship_type):
    ship_data = config.SHIPS.get(ship_type, {})

    return ship_data.get("supply_cost", 0) < 0


def roll_dice(sides):
    sides = int(sides)

    if sides <= 0:
        return 0

    return random.randint(1, sides)


def get_battle_culture_modifiers(battle):
    return battle.get("culture_modifiers") or []


def get_culture_combat_modifiers(
    culture,
    selected_conditions
):
    """
    Return only combat_modifiers belonging to the culture
    whose condition was selected by staff.
    """

    culture_data = config.SEA_CULTURES.get(culture)

    if not culture_data:
        return []

    selected_conditions = set(
        str(value).strip().lower()
        for value in selected_conditions
    )

    modifiers = []

    for modifier in culture_data.get(
        "combat_modifiers",
        []
    ):
        condition = str(
            modifier.get("condition", "")
        ).strip().lower()

        if condition in selected_conditions:
            modifiers.append(modifier)

    return modifiers


def get_house_combat_modifiers(
    house,
    selected_conditions
):
    house_data = database.get_house(house)

    if not house_data:
        return []

    culture = house_data.get("culture")

    return get_culture_combat_modifiers(
        culture,
        selected_conditions
    )


def get_modified_ship_stats(
    house,
    ship_type,
    selected_conditions
):
    """
    Calculate the combat snapshot for one ship type.

    Culture bonuses are applied to every ship individually.
    """

    base = config.SHIPS.get(ship_type)

    if not base:
        raise ValueError(
            f"Unknown ship type: {ship_type}"
        )

    health = int(base.get("health", 0))
    damage = int(base.get("damage", 0))

    for modifier in get_house_combat_modifiers(
        house,
        selected_conditions
    ):
        health += int(
            modifier.get("health_bonus", 0)
        )

        damage += int(
            modifier.get("damage_bonus", 0)
        )

    return {
        "health": max(0, health),
        "damage": max(0, damage)
    }


def initialize_battle(battle_id):
    """
    Freeze the submitted fleets into live combat state.

    Permanent fleet ownership is NOT modified.
    """

    battle = database.get_battle(battle_id)

    if not battle:
        raise ValueError("Battle not found.")

    if battle["status"] != "preparing":
        raise ValueError(
            "Battle is not in the preparing state."
        )

    if not battle["fleets_locked"]:
        raise ValueError(
            "Fleets must be locked before the battle starts."
        )

    fleet_groups = database.get_battle_fleet_groups(
        battle_id
    )

    if not fleet_groups:
        raise ValueError(
            "There are no fleets in this battle."
        )

    selected_conditions = (
        battle.get("culture_modifiers")
        or []
    )

    state = {}

    for fleet in fleet_groups:
        fleet_id = fleet["fleet_id"]
        house = fleet["house"]

        state[fleet_id] = {
            "fleet_id": fleet_id,
            "house": house,
            "commander": fleet.get("commander"),
            "commander_martial": int(
                fleet.get("commander_martial") or 0
            ),
            "ships": {}
        }

        for ship_type, amount in fleet["ships"].items():
            stats = get_modified_ship_stats(
                house,
                ship_type,
                selected_conditions
            )

            state[fleet_id]["ships"][ship_type] = {
                "amount": int(amount),
                "health": stats["health"],
                "damage": stats["damage"]
            }

    database.save_battle_fleet_state(
        battle_id,
        state
    )

    database.reset_battle_retreats(
        battle_id
    )

    database.set_battle_status(
        battle_id,
        "active",
        current_round=0
    )

    return state


def get_live_state(battle_id):
    """
    Combine persisted live ship state with fleet metadata.
    """

    raw_state = database.get_battle_fleet_state(
        battle_id
    )

    fleet_groups = {
        group["fleet_id"]: group
        for group in database.get_battle_fleet_groups(
            battle_id
        )
    }

    state = {}

    for fleet_id, fleet_state in raw_state.items():
        metadata = fleet_groups.get(
            fleet_id,
            {}
        )

        state[fleet_id] = {
            "fleet_id": fleet_id,
            "house": metadata.get(
                "house",
                "Unknown"
            ),
            "commander": metadata.get(
                "commander"
            ),
            "commander_martial": int(
                metadata.get(
                    "commander_martial",
                    0
                ) or 0
            ),
            "ships": fleet_state["ships"]
        }

    return state


def get_side_for_fleet(
    battle,
    house
):
    attacker_houses = set(
        database.get_houses_for_side(
            battle["id"],
            "attacker"
        )
    )

    defender_houses = set(
        database.get_houses_for_side(
            battle["id"],
            "defender"
        )
    )

    if house in attacker_houses:
        return "attacker"

    if house in defender_houses:
        return "defender"

    return None


def get_side_fleets(
    battle,
    state,
    side
):
    return [
        fleet
        for fleet in state.values()
        if get_side_for_fleet(
            battle,
            fleet["house"]
        ) == side
    ]


def get_combat_ship_count(fleets):
    total = 0

    for fleet in fleets:
        for ship_type, ship in fleet["ships"].items():
            if is_supply_ship(ship_type):
                continue

            total += max(
                0,
                int(ship["amount"])
            )

    return total


def get_total_ship_count(fleets):
    total = 0

    for fleet in fleets:
        for ship in fleet["ships"].values():
            total += max(
                0,
                int(ship["amount"])
            )

    return total


def roll_fleet_damage(
    fleets,
    half_damage=False
):
    """
    Formula:

        (
            1dMartial
            + every combat ship's individual damage die
        )
        / total ships
        * 2.5

    Supply ships do not contribute damage dice.

    The final damage is floored when actually applied,
    matching the spreadsheet's damage application behavior.
    """

    total_ships = get_total_ship_count(
        fleets
    )

    if total_ships <= 0:
        return {
            "damage": 0.0,
            "admiral_dice": 0,
            "ship_dice": 0,
            "combat_ships": 0,
            "total_ships": 0
        }

    combat_fleets = [
        fleet
        for fleet in fleets
        if get_combat_ship_count([fleet]) > 0
    ]

    if not combat_fleets:
        return {
            "damage": 0.0,
            "admiral_dice": 0,
            "ship_dice": 0,
            "combat_ships": 0,
            "total_ships": total_ships
        }

    # One admiral roll per fleet.
    admiral_dice = 0

    # One commander/admiral per fleet.
    for fleet in combat_fleets:
        martial = max(
            0,
            int(
                fleet.get(
                    "commander_martial",
                    0
                )
            )
        )

        admiral_dice += roll_dice(
            martial
        )

    # Every combat ship rolls its own damage die.
    ship_dice = 0
    combat_ship_count = 0

    for fleet in combat_fleets:
        for ship_type, ship in fleet["ships"].items():
            amount = max(
                0,
                int(ship["amount"])
            )

            if amount <= 0:
                continue

            if is_supply_ship(ship_type):
                continue

            damage_stat = max(
                0,
                int(ship["damage"])
            )

            combat_ship_count += amount

            for _ in range(amount):
                ship_dice += roll_dice(
                    damage_stat
                )

    raw = (
        admiral_dice + ship_dice
    ) / total_ships

    damage = (
        raw * FINAL_DAMAGE_MULTIPLIER
    )

    if half_damage:
        damage *= 0.5

    return {
        "damage": damage,
        "admiral_dice": admiral_dice,
        "ship_dice": ship_dice,
        "combat_ships": combat_ship_count,
        "total_ships": total_ships
    }


def weighted_ship_choice(
    eligible
):
    """
    Choose a ship type weighted by its current quantity.
    """

    total = sum(
        entry["amount"]
        for entry in eligible
    )

    if total <= 0:
        return None

    roll = random.uniform(
        0,
        total
    )

    for entry in eligible:
        roll -= entry["amount"]

        if roll <= 0:
            return entry

    return eligible[-1]


def apply_damage(
    fleets,
    damage
):
    """
    Apply whole HP damage using the spreadsheet's
    weighted random sinking behavior.

    Supply ships are immune.

    A ship is destroyed only when the remaining damage
    is at least that ship's full HP.
    """

    remaining = max(
        0,
        int(damage)
    )

    destroyed = 0
    destroyed_by_type = {}

    eligible = []

    for fleet in fleets:
        for ship_type, ship in fleet["ships"].items():
            amount = max(
                0,
                int(ship["amount"])
            )

            health = max(
                0,
                int(ship["health"])
            )

            if amount <= 0:
                continue

            if is_supply_ship(ship_type):
                continue

            if health <= 0:
                continue

            eligible.append({
                "fleet_id": fleet["fleet_id"],
                "ship_type": ship_type,
                "amount": amount,
                "health": health
            })

    while remaining > 0 and eligible:
        chosen = weighted_ship_choice(
            eligible
        )

        if not chosen:
            break

        if remaining < chosen["health"]:
            break

        fleet = next(
            (
                fleet
                for fleet in fleets
                if fleet["fleet_id"]
                == chosen["fleet_id"]
            ),
            None
        )

        if fleet is None:
            break

        ship = fleet["ships"].get(
            chosen["ship_type"]
        )

        if not ship or ship["amount"] <= 0:
            eligible = [
                entry
                for entry in eligible
                if not (
                    entry["fleet_id"]
                    == chosen["fleet_id"]
                    and entry["ship_type"]
                    == chosen["ship_type"]
                )
            ]
            continue

        ship["amount"] -= 1

        remaining -= chosen["health"]

        destroyed += 1

        destroyed_by_type[
            chosen["ship_type"]
        ] = (
            destroyed_by_type.get(
                chosen["ship_type"],
                0
            ) + 1
        )

        chosen["amount"] -= 1

        if chosen["amount"] <= 0:
            eligible = [
                entry
                for entry in eligible
                if not (
                    entry["fleet_id"]
                    == chosen["fleet_id"]
                    and entry["ship_type"]
                    == chosen["ship_type"]
                )
            ]

    return {
        "destroyed": destroyed,
        "destroyed_by_type": destroyed_by_type,
        "remaining_damage": remaining
    }


def side_has_combat_ships(
    state,
    battle,
    side
):
    fleets = get_side_fleets(
        battle,
        state,
        side
    )

    return get_combat_ship_count(
        fleets
    ) > 0


def run_round(battle_id):
    """
    Execute one normal round.

    Staff explicitly calls this.

    Both sides calculate their attacks from the
    same pre-round state, then both sets of damage
    are applied.
    """

    battle = database.get_battle(
        battle_id
    )

    if not battle:
        raise ValueError(
            "Battle not found."
        )

    if battle["status"] != "active":
        raise ValueError(
            "Battle is not active."
        )

    if (
        battle["attacker_retreat"]
        or battle["defender_retreat"]
    ):
        raise ValueError(
            "A fleet has already declared retreat. "
            "Resolve the retreat before starting another round."
        )

    round_number = (
        int(battle["current_round"])
        + 1
    )

    if round_number > MAX_ROUNDS:
        raise ValueError(
            f"The maximum of {MAX_ROUNDS} rounds has been reached."
        )

    state = get_live_state(
        battle_id
    )

    attacker_fleets = get_side_fleets(
        battle,
        state,
        "attacker"
    )

    defender_fleets = get_side_fleets(
        battle,
        state,
        "defender"
    )

    if not attacker_fleets:
        raise ValueError(
            "The attacker has no fleets."
        )

    if not defender_fleets:
        raise ValueError(
            "The defender has no fleets."
        )

    attacker_roll = roll_fleet_damage(
        attacker_fleets
    )

    defender_roll = roll_fleet_damage(
        defender_fleets
    )

    attacker_result = apply_damage(
        defender_fleets,
        attacker_roll["damage"]
    )

    defender_result = apply_damage(
        attacker_fleets,
        defender_roll["damage"]
    )

    database.save_battle_fleet_state(
        battle_id,
        state
    )

    database.save_battle_round(
        battle_id=battle_id,
        round_number=round_number,
        attacker_damage=attacker_roll["damage"],
        defender_damage=defender_roll["damage"],
        attacker_dice=attacker_roll["admiral_dice"],
        defender_dice=defender_roll["admiral_dice"],
        attacker_ship_dice=attacker_roll["ship_dice"],
        defender_ship_dice=defender_roll["ship_dice"],
        attacker_destroyed=attacker_result["destroyed"],
        defender_destroyed=defender_result["destroyed"]
    )

    database.set_battle_status(
        battle_id,
        "active",
        current_round=round_number
    )

    return {
        "round": round_number,
        "attacker": {
            "damage": attacker_roll["damage"],
            "admiral_dice": attacker_roll["admiral_dice"],
            "ship_dice": attacker_roll["ship_dice"],
            "destroyed": attacker_result["destroyed"],
            "destroyed_by_type": attacker_result[
                "destroyed_by_type"
            ]
        },
        "defender": {
            "damage": defender_roll["damage"],
            "admiral_dice": defender_roll["admiral_dice"],
            "ship_dice": defender_roll["ship_dice"],
            "destroyed": defender_result["destroyed"],
            "destroyed_by_type": defender_result[
                "destroyed_by_type"
            ]
        }
    }


def resolve_retreat_round(
    battle_id,
    retreating_side
):
    """
    Resolve the free half-damage attack after one side retreats.

    The retreating side does not attack.

    The opposing side attacks once at half damage.
    """

    battle = database.get_battle(
        battle_id
    )

    if not battle:
        raise ValueError(
            "Battle not found."
        )

    if battle["status"] != "active":
        raise ValueError(
            "Battle is not active."
        )

    if retreating_side not in {
        "attacker",
        "defender"
    }:
        raise ValueError(
            "Invalid retreating side."
        )

    state = get_live_state(
        battle_id
    )

    attacking_side = (
        "defender"
        if retreating_side == "attacker"
        else "attacker"
    )

    attacking_fleets = get_side_fleets(
        battle,
        state,
        attacking_side
    )

    target_fleets = get_side_fleets(
        battle,
        state,
        retreating_side
    )

    attack = roll_fleet_damage(
        attacking_fleets,
        half_damage=True
    )

    result = apply_damage(
        target_fleets,
        attack["damage"]
    )

    database.save_battle_fleet_state(
        battle_id,
        state
    )

    round_number = (
        int(battle["current_round"])
        + 1
    )

    if round_number <= MAX_ROUNDS:
        database.save_battle_round(
            battle_id=battle_id,
            round_number=round_number,
            attacker_damage=(
                attack["damage"]
                if attacking_side == "attacker"
                else 0
            ),
            defender_damage=(
                attack["damage"]
                if attacking_side == "defender"
                else 0
            ),
            attacker_dice=(
                attack["admiral_dice"]
                if attacking_side == "attacker"
                else 0
            ),
            defender_dice=(
                attack["admiral_dice"]
                if attacking_side == "defender"
                else 0
            ),
            attacker_ship_dice=(
                attack["ship_dice"]
                if attacking_side == "attacker"
                else 0
            ),
            defender_ship_dice=(
                attack["ship_dice"]
                if attacking_side == "defender"
                else 0
            ),
            attacker_destroyed=(
                result["destroyed"]
                if retreating_side == "attacker"
                else 0
            ),
            defender_destroyed=(
                result["destroyed"]
                if retreating_side == "defender"
                else 0
            ),
            attacker_retreat=(
                retreating_side == "attacker"
            ),
            defender_retreat=(
                retreating_side == "defender"
            ),
            notes=(
                f"{retreating_side} retreating; "
                f"{attacking_side} received a free "
                f"half-damage attack."
            )
        )

        database.set_battle_status(
            battle_id,
            "active",
            current_round=round_number
        )

    return {
        "round": round_number,
        "attacking_side": attacking_side,
        "retreating_side": retreating_side,
        "damage": attack["damage"],
        "admiral_dice": attack["admiral_dice"],
        "ship_dice": attack["ship_dice"],
        "destroyed": result["destroyed"],
        "destroyed_by_type": result[
            "destroyed_by_type"
        ]
    }


def close_battle(
    battle_id,
    winner_side=None
):
    """
    Close the battle and finally modify fleet_ledger.

    This is the ONLY battle function that changes permanent
    fleet ownership.

    Surviving combat ships are returned naturally because
    the original fleet reservation is removed when the
    battle is closed.

    Supply ships belonging to a fleet with no combat ships
    remaining are destroyed.
    """

    battle = database.get_battle(
        battle_id
    )

    if not battle:
        raise ValueError(
            "Battle not found."
        )

    if battle["status"] == "closed":
        raise ValueError(
            "Battle is already closed."
        )

    state = get_live_state(
        battle_id
    )

    final_counts = {}

    for fleet_id, fleet in state.items():
        combat_count = 0

        for ship_type, ship in fleet["ships"].items():
            if is_supply_ship(ship_type):
                continue

            combat_count += max(
                0,
                int(ship["amount"])
            )

        final_counts[fleet_id] = {}

        for ship_type, ship in fleet["ships"].items():
            amount = max(
                0,
                int(ship["amount"])
            )

            if (
                is_supply_ship(ship_type)
                and combat_count <= 0
            ):
                amount = 0

            final_counts[fleet_id][
                ship_type
            ] = amount

    # Calculate original committed fleet.
    original = database.get_battle_fleet_groups(
        battle_id
    )

    original_by_fleet = {
        group["fleet_id"]: group
        for group in original
    }

    try:
        database.conn.execute("BEGIN")

        for fleet_id, remaining in final_counts.items():
            original_group = original_by_fleet.get(
                fleet_id
            )

            if not original_group:
                continue

            house = original_group["house"]

            original_ships = original_group[
                "ships"
            ]

            for ship_type, original_amount in (
                original_ships.items()
            ):
                remaining_amount = remaining.get(
                    ship_type,
                    0
                )

                destroyed = (
                    original_amount
                    - remaining_amount
                )

                if destroyed <= 0:
                    continue

                cursor = database.cursor

                cursor.execute("""
                    INSERT INTO fleet_ledger(
                        house,
                        ship_type,
                        amount,
                        added_by
                    )
                    VALUES(?, ?, ?, ?)
                """, (
                    house,
                    ship_type,
                    -destroyed,
                    "battle_close"
                ))

        database.cursor.execute("""
            UPDATE battles
            SET status=?,
                fleets_locked=1
            WHERE id=?
        """, (
            "closed",
            battle_id
        ))

        database.conn.commit()

    except Exception:
        database.conn.rollback()
        raise

    return {
        "battle_id": battle_id,
        "winner_side": winner_side,
        "fleets": final_counts
    }