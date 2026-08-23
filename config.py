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
    "Kingdom of "
]
REGIONS = [
    "The North"
]
SHIPS = {
    "Longship": {
        "name": "Longship",
        "cost": 25,
        "maintenance": 5,
        "supply_cost": 192,
        "health": 1,
        "damage": 3
    },
    "War_Longship": {
        "name": "War Longship",
        "cost": 25,
        "maintenance": 5,
        "supply_cost": 192,
        "health": 2,
        "damage": 4
    },
    "Galley": {
        "name": "Galley",
        "cost": 100,
        "maintenance": 10,
        "supply_cost": 320,
        "health": 3,
        "damage": 5
    },
    "Myrish_Galley": {
        "name": "Myrish Galley",
        "cost": 75,
        "maintenance": 7,
        "supply_cost": 240,
        "health": 2,
        "damage": 5
    },
    "War_Galley": {
        "name": "War Galley",
        "cost": 175,
        "maintenance": 15,
        "supply_cost": 480,
        "health": 5,
        "damage": 7
    },
    "Myrish_War_Galley": {
        "name": "Myrish War Galley",
        "cost": 125,
        "maintenance": 12,
        "supply_cost": 320,
        "health": 4,
        "damage": 6
    },
    "Dromond": {
        "name": "Dromond",
        "cost": 500,
        "maintenance": 50,
        "supply_cost": 1920,
        "health": 10,
        "damage": 15
    },
    "Supply_Ship": {
        "name": "Supply Ship",
        "cost": 25,
        "maintenance": 0,
        "supply_cost": -1920,
        "health": 0,
        "damage": 0
    },
}

PORT_LEVEL_CAPS = {
    1: 5,
    2: 10,
    3: 15,
    4: 20,
    5: 30,
    6: 40,
    7: 50,
    8: 60,
    9: 70
}

SEA_CULTURES = {
    # =========================
    # WESTEROS
    # =========================
    "Ironborn": {
        "allowed_ships": ["Longship", "War_Longship", "Galley", "War_Galley", "Dromond", "Supply_Ship"],
        "blocked_ships": ["Myrish_Galley", "Myrish_War_Galley"],
        "cost_modifiers": [],
        "maintenance_modifiers": [
            {
                "ship_types": ["War_Galley", "Dromond", "Galley"],
                "multiplier": 2.0,
                "reason": "Ironborn pay double maintenance for ships larger than Longships."
            }
        ],
        "fleet_rules": {
            "base": 20,
            "stat": "martial"
        },
        "special_rules": [
            "Can raise the Iron Fleet (100 Longships) if they hold 1500 raid gold.",
            "Doing so strips all timber from the Iron Islands and blocks shipbuilding for 30 years unless wood is imported."
        ]
    },

    "Shieldman": {
        "allowed_ships": ["Longship", "War_Longship", "Galley", "War_Galley", "Dromond", "Supply_Ship"],
        "blocked_ships": ["Myrish_Galley", "Myrish_War_Galley"],
        "cost_modifiers": [],
        "maintenance_modifiers": [],
        "fleet_rules": {
            "base": 20,
            "stat": "martial"
        },
        "combat_modifiers": [
            {
                "condition": "defending_mander",
                "damage_bonus": 1
            }
        ],
        "special_rules": [
            "Loses cultural bonuses if the Shield Islands are politically unified above the other island lords.",
            "Can command fleets of unplayed Shield Island houses if relations are good."
        ]
    },

    "Vineman": {
        "allowed_ships": ["Longship", "Galley", "War_Galley", "Dromond", "Supply_Ship"],
        "blocked_ships": ["Myrish_Galley", "Myrish_War_Galley", "War_Longship"],
        "cost_modifiers": [],
        "maintenance_modifiers": [],
        "fleet_rules": {
            "base": 20,
            "stat": "stewardship"
        },
        "special_modifiers": [
            {
                "condition": "trading_fleet",
                "security_bonus": 1
            }
        ],
        "special_rules": [
            "Fleet of the Arbor cannot be raised offensively while the Redwyne player is in debt."
        ]
    },

    "Dornish": {
        "allowed_ships": ["Longship", "Galley", "Myrish_Galley", "Supply_Ship"],
        "blocked_ships": ["Dromond", "Great_Dromond", "War_Galley", "Myrish_War_Galley"],
        "cost_modifiers": [
            {
                "ship_types": "ALL",
                "multiplier": 2.0,
                "reason": "Stone Dornish pay double ship construction costs."
            }
        ],
        "maintenance_modifiers": [],
        "fleet_rules": {
            "base": 20,
            "stat": "martial"
        },
        "special_rules": [
            "Cannot build ships larger than Galleys."
        ]
    },

    "Westerosi Valyrian": {
        "allowed_ships": ["Longship", "Galley", "War_Galley", "Dromond", "Supply_Ship"],
        "blocked_ships": ["Myrish_Galley", "Myrish_War_Galley", "War_Longship"],
        "cost_modifiers": [],
        "maintenance_modifiers": [
            {
                "ship_types": ["Galley", "War_Galley"],
                "multiplier": 0.5,
                "condition": "spicetown_rebuilt",
                "reason": "Galleys cost half maintenance if Spicetown is rebuilt."
            }
        ],
        "fleet_rules": {
            "base": 20,
            "stat": "martial",
            "conditional_override": {
                "condition": "targaryen_on_throne",
                "base": 25
            }
        },
        "special_rules": [
            "If no Targaryen sits the throne and no Westerosi Valyrian is Master of Ships, fleet cap may be reduced by staff."
        ]
    },

    "Harborman": {
        "allowed_ships": ["Longship", "Galley", "War_Galley", "Dromond", "Supply_Ship"],
        "blocked_ships": ["Myrish_Galley", "Myrish_War_Galley", "War_Longship"],
        "cost_modifiers": [],
        "maintenance_modifiers": [
            {
                "ship_types": ["Dromond", "War_Galley"],
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
                "security_bonus": 1
            }
        ],
        "special_rules": []
    },

    "Bearmen": {
        "allowed_ships": ["Longship", "War_Longship", "Supply_Ship"],
        "blocked_ships": ["War_Galley", "Dromond", "Myrish_Galley", "Myrish_War_Galley", "Galley"],
        "cost_modifiers": [],
        "maintenance_modifiers": [],
        "fleet_rules": {
            "base": 20,
            "stat": "martial"
        },
        "combat_modifiers": [
            {
                "condition": "all_fleets",
                "health_bonus": 1
            },
            {
                "condition": "defending_north_coast",
                "damage_bonus": 1
            }
        ],
        "special_rules": [
            "Cannot build ships larger than War Longships."
        ]
    },

    "Sapphire Islander": {
        "allowed_ships": ["Longship", "Galley", "War_Galley", "Dromond", "Supply_Ship"],
        "blocked_ships": ["Myrish_Galley", "Myrish_War_Galley", "War_Longship"],
        "cost_modifiers": [],
        "maintenance_modifiers": [
            {
                "ship_types": ["ALL"],
                "multiplier": 1.10,
                "reason": "Stormlands warship maintenance costs 10% more."
            }
        ],
        "fleet_rules": {
            "base": 20,
            "stat": "stewardship"
        },
        "combat_modifiers": [
            {
                "condition": "defending_stormlands_coast",
                "health_bonus": 1
            }
        ],
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
                "multiplier": 0.25,
                "prestige_multiplier": 0.75,
                "reason": "Pirates pay only 25 percent of ship maintenance in gold."
            }
        ],
        "fleet_rules": {
            "base": 20,
            "stat": "martial"
        },
        "special_rules": [
            "Cannot build ships directly.",
            "Must buy, capture, or receive sponsored ships."
        ]
    },

    "Magister": {
        "allowed_ships": ["Longship", "Galley", "War_Galley", "Dromond", "Supply_Ship", "Myrish_Galley", "Myrish_War_Galley"],
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