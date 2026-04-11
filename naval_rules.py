import config
import database


def get_culture_rules(house_name: str):
    house = database.get_house(house_name)
    if not house:
        return None

    culture = house.get("culture")
    return config.SEA_CULTURES.get(culture)


def can_build_ship(house_name: str, ship_type: str):
    rules = get_culture_rules(house_name)

    if not rules:
        return True, None

    if rules.get("blocked_ships") == "ALL":
        return False, "This culture cannot build ships directly."

    allowed = rules.get("allowed_ships", [])
    blocked = rules.get("blocked_ships", [])

    if ship_type in blocked:
        return False, f"This ship type is blocked for this culture."

    if allowed and ship_type not in allowed:
        return False, f"This ship type is not available for this culture."

    return True, None


def get_modified_ship_cost(house_name: str, ship_type: str):
    base_cost = config.SHIPS[ship_type]["cost"]
    rules = get_culture_rules(house_name)

    if not rules:
        return base_cost

    total = base_cost

    for mod in rules.get("cost_modifiers", []):
        applies = False

        if mod["ship_types"] == "ALL":
            applies = True
        elif ship_type in mod["ship_types"]:
            applies = True

        if applies:
            total = round(total * mod["multiplier"])

    return total


def get_modified_ship_maintenance(house_name: str, ship_type: str):
    base_maintenance = config.SHIPS[ship_type]["maintenance"]
    rules = get_culture_rules(house_name)

    if not rules:
        return {
            "gold": base_maintenance,
            "prestige": 0
        }

    total = base_maintenance
    prestige = 0

    for mod in rules.get("maintenance_modifiers", []):
        applies = False

        if mod["ship_types"] == "ALL":
            applies = True
        elif ship_type in mod["ship_types"]:
            applies = True

        if not applies:
            continue

        # Special pirate split
        if "gold_ratio" in mod:
            gold = round(base_maintenance * mod["gold_ratio"], 2)
            prestige = round(base_maintenance * mod["prestige_ratio"], 2)
            return {
                "gold": gold,
                "prestige": prestige
            }

        total = round(total * mod["multiplier"], 2)

    return {
        "gold": total,
        "prestige": prestige
    }