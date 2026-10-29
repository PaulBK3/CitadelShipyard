GUILD_ID = 1222288591707967568
#GUILD_ID = 763895183321858060
SHIP_TEAM_ROLE = "Travel Team"
SAVE_EDIT_CHANNEL = "✍︱save-edit-list"
SHIP_LOG_CHANNEL = "🛳️︱ship-log"
SEA_BATTLE_CHANNEL = "⚓︱sea-battles"

# Used to detect a player's house role
HOUSE_ROLE_FILTER = [
    "House ",
    "Free City of ",
    "Kingdom of ",
    "High "
]

SHIPS = {
    "Longship": {
        "name": "Longship",
        "cost": 25,
        "maintenance": 5,
        "supply_cost": 192,
        "health": 4,
        "damage": 3,
        "port_level": 1
    },
    "War_Longship": {
        "name": "War Longship",
        "cost": 25,
        "maintenance": 5,
        "supply_cost": 192,
        "health": 8,
        "damage": 4,
        "port_level": 1
    },
    "Galley": {
        "name": "Galley",
        "cost": 100,
        "maintenance": 10,
        "supply_cost": 320,
        "health": 12,
        "damage": 5,
        "port_level": 3
    },
    "Myrish_Galley": {
        "name": "Myrish Galley",
        "cost": 75,
        "maintenance": 7,
        "supply_cost": 240,
        "health": 8,
        "damage": 5,
        "port_level": 3
    },
    "War_Galley": {
        "name": "War Galley",
        "cost": 175,
        "maintenance": 15,
        "supply_cost": 480,
        "health": 20,
        "damage": 7,
        "port_level": 5
    },
    "Myrish_War_Galley": {
        "name": "Myrish War Galley",
        "cost": 125,
        "maintenance": 12,
        "supply_cost": 320,
        "health": 16,
        "damage": 6,
        "port_level": 5
    },
    "Dromond": {
        "name": "Dromond",
        "cost": 500,
        "maintenance": 50,
        "supply_cost": 1920,
        "health": 40,
        "damage": 15,
        "port_level": 8
    },
    "Supply_Ship": {
        "name": "Supply Ship",
        "cost": 25,
        "maintenance": 0,
        "supply_cost": -1920,
        "health": 0,
        "damage": 0,
        "port_level": 1
    },
}

# Ship lists shared by most cultures
WESTEROSI_SHIPS = ["Longship", "Galley", "War_Galley", "Dromond", "Supply_Ship"]
ESSOSI_SHIPS = ["Myrish_Galley", "Myrish_War_Galley"]

# Combat modifiers without a "condition" are always applied.
# Combat modifiers with "ship_types" only apply to those ship types.
# Conditional combat modifiers must be selected by staff for the battle.
WESTERLANDS_CULTURE = {
    "allowed_ships": WESTEROSI_SHIPS,
    "blocked_ships": ESSOSI_SHIPS + ["War_Longship"],
    "cost_modifiers": [],
    "maintenance_modifiers": [
        {
            "ship_types": "ALL",
            "multiplier": 1.5,
            "reason": "Due to their overabundance and corruption they pay 50% more naval upkeep."
        }
    ],
    "fleet_rules": {
        "base": 20,
        "stat": "martial"
    },
    "special_rules": []
}

SEA_CULTURES = {
    # =========================
    # WESTEROS
    # =========================
    "Ironborn": {
        "allowed_ships": WESTEROSI_SHIPS + ["War_Longship"],
        "blocked_ships": ESSOSI_SHIPS,
        "cost_modifiers": [],
        "maintenance_modifiers": [],
        "fleet_rules": {
            "base": 20,
            "stat": "martial"
        },
        "combat_modifiers": [
            {
                "ship_types": ["War_Longship"],
                "damage_bonus": 1,
                "reason": "Ironborn War Longships deal +1 damage."
            }
        ],
        "special_rules": []
    },

    "Shieldman": {
        "allowed_ships": WESTEROSI_SHIPS + ["War_Longship"],
        "blocked_ships": ESSOSI_SHIPS,
        "cost_modifiers": [],
        "maintenance_modifiers": [],
        "fleet_rules": {
            "base": 20,
            "stat": "martial"
        },
        "combat_modifiers": [
            {
                "condition": "defending_mander",
                "health_bonus": 4,
                "reason": "Fleets led by a Shieldman Admiral gain +4 health when defending the Mander."
            }
        ],
        "special_rules": []
    },

    "Vineman": {
        "allowed_ships": WESTEROSI_SHIPS,
        "blocked_ships": ESSOSI_SHIPS + ["War_Longship"],
        "cost_modifiers": [],
        "maintenance_modifiers": [],
        "fleet_rules": {
            "base": 20,
            "stat": "stewardship"
        },
        "special_modifiers": [
            {
                "condition": "trading_fleet",
                "security_bonus": 5
            }
        ],
        "special_rules": [
            "May only use 25% of their fleet when going on the offensive."
        ]
    },

    "Drylander": {
        "allowed_ships": ["Longship", "Galley", "Myrish_Galley", "Supply_Ship"],
        "blocked_ships": ["War_Longship", "War_Galley", "Myrish_War_Galley", "Dromond"],
        "cost_modifiers": [
            {
                "ship_types": "ALL",
                "multiplier": 2.0,
                "reason": "Drylander / Red Mountain Dornish pay double ship production costs."
            }
        ],
        "maintenance_modifiers": [],
        "fleet_rules": {
            "base": 20,
            "stat": "martial"
        },
        "special_rules": [
            "Cannot build ships greater than Galleys."
        ]
    },

    "Dornish": {
        "allowed_ships": WESTEROSI_SHIPS + ESSOSI_SHIPS,
        "blocked_ships": ["War_Longship"],
        "cost_modifiers": [],
        "maintenance_modifiers": [],
        "fleet_rules": {
            "base": 20,
            "stat": "martial"
        },
        "special_rules": [
            "Can build Essosi ship types."
        ]
    },

    "Westerosi Valyrian": {
        "allowed_ships": WESTEROSI_SHIPS,
        "blocked_ships": ESSOSI_SHIPS + ["War_Longship"],
        "cost_modifiers": [],
        "maintenance_modifiers": [
            {
                "ship_types": ["Galley"],
                "multiplier": 0.5,
                "condition": "velaryon_spicetown",
                "reason": "Galleys cost half maintenance if House Velaryon holds a functioning Spicetown."
            }
        ],
        "fleet_rules": {
            "base": 20,
            "stat": "martial",
            "conditional_overrides": [
                {
                    "condition": "targaryen_on_throne",
                    "base": 25
                },
                {
                    "condition": "no_targaryen_and_no_valyrian_master_of_ships",
                    "base": 18
                }
            ]
        },
        "special_rules": [
            "Fleet size is 25+Martial while a Targaryen sits on the throne.",
            "Fleet size is 18+Martial if no Targaryen sits on the throne and no Westerosi Valyrian is Master of Ships."
        ]
    },

    "Harborman": {
        "allowed_ships": WESTEROSI_SHIPS,
        "blocked_ships": ESSOSI_SHIPS + ["War_Longship"],
        "cost_modifiers": [],
        "maintenance_modifiers": [
            {
                "ship_types": ["War_Galley", "Dromond"],
                "multiplier": 1.10,
                "reason": "Ships larger than Galleys cost 10% more to maintain."
            }
        ],
        "fleet_rules": {
            "base": 20,
            "stat": "stewardship"
        },
        "special_modifiers": [
            {
                "condition": "all_fleets",
                "security_bonus": 5
            }
        ],
        "special_rules": []
    },

    "Bearmen": {
        "allowed_ships": ["Longship", "War_Longship", "Supply_Ship"],
        "blocked_ships": ["Galley", "War_Galley", "Dromond"] + ESSOSI_SHIPS,
        "cost_modifiers": [],
        "maintenance_modifiers": [],
        "fleet_rules": {
            "base": 20,
            "stat": "martial"
        },
        "combat_modifiers": [
            {
                "health_bonus": 4,
                "reason": "Bearmen ships gain +4 health."
            },
            {
                "condition": "defending_north_coast",
                "damage_bonus": 1,
                "reason": "Bearmen ships gain +1 damage when protecting the North coasts."
            }
        ],
        "special_rules": [
            "Cannot build ships larger than War Longships."
        ]
    },

    "Sapphire Islander": {
        "allowed_ships": WESTEROSI_SHIPS,
        "blocked_ships": ESSOSI_SHIPS + ["War_Longship"],
        "cost_modifiers": [],
        "maintenance_modifiers": [
            {
                "ship_types": "ALL",
                "multiplier": 0.8,
                "reason": "Sapphire Islander naval upkeep is reduced by 20%."
            }
        ],
        "fleet_rules": {
            "base": 20,
            "stat": "stewardship"
        },
        "combat_modifiers": [
            {
                "condition": "defending_stormlands_coast",
                "health_bonus": 4,
                "reason": "Sapphire Islander ships gain +4 health when defending the Stormlands coast."
            }
        ],
        "special_rules": []
    },

    "Krakenman": {
        "allowed_ships": WESTEROSI_SHIPS + ["War_Longship"],
        "blocked_ships": ESSOSI_SHIPS,
        "cost_modifiers": [],
        "maintenance_modifiers": [],
        "fleet_rules": {
            "base": 20,
            "stat": "martial"
        },
        "special_rules": [
            "Can build War Longships due to their Ironborn heritage."
        ]
    },

    "Fair Islander": {
        "allowed_ships": WESTEROSI_SHIPS,
        "blocked_ships": ESSOSI_SHIPS + ["War_Longship"],
        "cost_modifiers": [],
        "maintenance_modifiers": [],
        "fleet_rules": {
            "base": 20,
            "stat": "martial"
        },
        "combat_modifiers": [
            {
                "condition": "defending_fair_isle",
                "health_bonus": 4,
                "reason": "Fleets led by a Fair Islander Admiral gain +4 health when defending Fair Isle."
            }
        ],
        "special_rules": []
    },

    "Iron Bane": WESTERLANDS_CULTURE,
    "Westerlander": WESTERLANDS_CULTURE,
    "Silverlander": WESTERLANDS_CULTURE,

    "Esterman": {
        "allowed_ships": WESTEROSI_SHIPS,
        "blocked_ships": ESSOSI_SHIPS + ["War_Longship"],
        "cost_modifiers": [],
        "maintenance_modifiers": [
            {
                "ship_types": "ALL",
                "multiplier": 0.8,
                "condition": "stationed_on_tarth",
                "reason": "Naval upkeep is reduced by 20% while fleets are stationed upon Tarth."
            }
        ],
        "fleet_rules": {
            "base": 20,
            "stat": "martial"
        },
        "special_modifiers": [
            {
                "condition": "all_fleets",
                "security_bonus": 3
            }
        ],
        "special_rules": []
    },

    "Baymen": {
        "allowed_ships": WESTEROSI_SHIPS,
        "blocked_ships": ESSOSI_SHIPS + ["War_Longship"],
        "cost_modifiers": [],
        "maintenance_modifiers": [],
        "fleet_rules": {
            "base": 20,
            "stat": "martial"
        },
        "combat_modifiers": [
            {
                "condition": "defending_blackwater_bay",
                "health_bonus": 4,
                "reason": "Fleets led by a Baymen Admiral gain +4 health when defending the Blackwater Bay."
            }
        ],
        "special_rules": []
    },

    "Sisterman": {
        "allowed_ships": WESTEROSI_SHIPS + ["War_Longship"],
        "blocked_ships": ESSOSI_SHIPS,
        "cost_modifiers": [
            {
                "ship_types": ["Galley", "War_Galley", "Dromond"],
                "multiplier": 2.0,
                "reason": "Ships bigger than War Longships cost double to produce."
            }
        ],
        "maintenance_modifiers": [
            {
                "ship_types": "ALL",
                "gold_ratio": 0.25,
                "prestige_ratio": 0.75,
                "reason": "Sistermen pay 25% of maintenance in gold and the rest in prestige."
            }
        ],
        "fleet_rules": {
            "base": 20,
            "stat": "martial"
        },
        "special_rules": []
    },

    # =========================
    # ESSOS
    # =========================
    "Pirate": {
        "allowed_ships": [],
        "blocked_ships": "ALL",
        "cost_modifiers": [],
        "maintenance_modifiers": [
            {
                "ship_types": "ALL",
                "gold_ratio": 0.25,
                "prestige_ratio": 0.75,
                "reason": "Pirates pay 25% of maintenance in gold and the rest in prestige."
            }
        ],
        "fleet_rules": {
            "base": 20,
            "stat": "martial"
        },
        "special_rules": [
            "Cannot build ships directly.",
            "Must buy, capture, or negotiate sponsored ships from Essosi players."
        ]
    },

    "Magister": {
        "allowed_ships": WESTEROSI_SHIPS + ESSOSI_SHIPS,
        "blocked_ships": ["War_Longship"],
        "cost_modifiers": [],
        "maintenance_modifiers": [],
        "fleet_rules": {
            "base": 20,
            "stat": "stewardship"
        },
        "special_rules": [
            "May pay maintenance from treasury.",
            "Can build Essosi ship types."
        ]
    }
}

