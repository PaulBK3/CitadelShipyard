import sqlite3
import uuid
import config
import json

conn = sqlite3.connect("ships.db")
cursor = conn.cursor()


def setup():
    # ----------------------------
    # Ship Requests
    # ----------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ship_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        house TEXT NOT NULL,
        ship_type TEXT NOT NULL,
        amount INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        staff_name TEXT,
        deny_reason TEXT,
        comment TEXT,
        added_to_ledger INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Add missing column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE ship_requests ADD COLUMN added_to_ledger INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        # Column already exists
        pass

    # ----------------------------
    # House Profiles
    # ----------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS houses (
        house_name TEXT PRIMARY KEY,
        duchy TEXT,
        culture TEXT,
        port_level INTEGER NOT NULL DEFAULT 0,
        region TEXT
    )
    """)

    # Add missing region column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE houses ADD COLUMN region TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    # Add role_id column to houses for storing Discord role IDs
    try:
        cursor.execute("ALTER TABLE houses ADD COLUMN role_id INTEGER")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # ----------------------------
    # Fleet Ledger
    # ----------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fleet_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        house TEXT NOT NULL,
        ship_type TEXT NOT NULL,
        amount INTEGER NOT NULL,
        source_request_id INTEGER,
        added_by TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ----------------------------
    # Port Upgrade Requests
    # ----------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS port_upgrade_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        house TEXT NOT NULL,
        requested_level INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        staff_name TEXT,
        deny_reason TEXT,
        comment TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ----------------------------
    # Battles
    # ----------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS battles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        attacker_house TEXT NOT NULL,
        defender_house TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'preparing',
        attacker_thread_id INTEGER,
        defender_thread_id INTEGER,
        thread_id INTEGER,
        created_by INTEGER NOT NULL,
        fleets_locked INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Side -> houses mapping for a battle (allows multiple houses per side)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS battle_side_houses (
        battle_id INTEGER NOT NULL,
        side TEXT NOT NULL,
        house TEXT NOT NULL,
        PRIMARY KEY (battle_id, side, house),
        FOREIGN KEY (battle_id) REFERENCES battles(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS battle_fleets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        battle_id INTEGER NOT NULL,
        house TEXT NOT NULL,
        ship_type TEXT NOT NULL,
        amount INTEGER NOT NULL,
        commander TEXT,
        commander_martial INTEGER,
        fleet_id TEXT,
        FOREIGN KEY (battle_id) REFERENCES battles(id)
    )
    """)
    # ---------------------------------------------------------
    # Battle combat state
    # ---------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS battle_fleet_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            battle_id INTEGER NOT NULL,
            fleet_id TEXT NOT NULL,
            ship_type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            health INTEGER NOT NULL,
            damage INTEGER NOT NULL,
            FOREIGN KEY (battle_id) REFERENCES battles(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS battle_rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            battle_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            attacker_damage REAL NOT NULL DEFAULT 0,
            defender_damage REAL NOT NULL DEFAULT 0,
            attacker_dice INTEGER NOT NULL DEFAULT 0,
            defender_dice INTEGER NOT NULL DEFAULT 0,
            attacker_ship_dice INTEGER NOT NULL DEFAULT 0,
            defender_ship_dice INTEGER NOT NULL DEFAULT 0,
            attacker_destroyed INTEGER NOT NULL DEFAULT 0,
            defender_destroyed INTEGER NOT NULL DEFAULT 0,
            attacker_retreat INTEGER NOT NULL DEFAULT 0,
            defender_retreat INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(battle_id, round_number),
            FOREIGN KEY (battle_id) REFERENCES battles(id)
        )
    """)

    # Current round and retreat state.
    try:
        cursor.execute("""
            ALTER TABLE battles
            ADD COLUMN current_round INTEGER NOT NULL DEFAULT 0
        """)
        conn.commit()
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("""
            ALTER TABLE battles
            ADD COLUMN attacker_retreat INTEGER NOT NULL DEFAULT 0
        """)
        conn.commit()
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("""
            ALTER TABLE battles
            ADD COLUMN defender_retreat INTEGER NOT NULL DEFAULT 0
        """)
        conn.commit()
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("""
            ALTER TABLE battles
            ADD COLUMN culture_modifiers TEXT
        """)
        conn.commit()
    except sqlite3.OperationalError:
        pass
    # Add missing attacker_thread_id and defender_thread_id columns if they don't exist
    try:
        cursor.execute("ALTER TABLE battles ADD COLUMN attacker_thread_id INTEGER")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE battles ADD COLUMN defender_thread_id INTEGER")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # Add missing commander_martial column if it doesn't exist
    try:
        cursor.execute("""
            ALTER TABLE battle_fleets
            ADD COLUMN commander_martial INTEGER
        """)
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # Add missing fleets_locked column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE battles ADD COLUMN fleets_locked INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass


# =========================================================
# AVAILABILITY / RESERVATION HELPERS
# =========================================================

def get_committed_ships_for_house(house_name):
    """
    Return ship_type -> amount committed by this house across
    all preparing battles.
    """
    cursor.execute("""
    SELECT bf.ship_type, SUM(bf.amount)
    FROM battle_fleets bf
    JOIN battles b ON bf.battle_id = b.id
    WHERE bf.house=?
      AND b.status='preparing'
    GROUP BY bf.ship_type
    """, (house_name,))

    rows = cursor.fetchall()

    return {
        ship_type: amount
        for ship_type, amount in rows
    }


def get_available_fleet_for_house(house_name):
    """
    Return ship_type -> currently available amount.
    """
    owned = get_fleet_for_house(house_name)
    committed = get_committed_ships_for_house(house_name)

    available = {}

    for ship_type, owned_amount in owned.items():
        committed_amount = committed.get(
            ship_type,
            0
        )

        avail = owned_amount - committed_amount

        if avail > 0:
            available[ship_type] = avail

    return available


def submit_battle_fleet(
    battle_id,
    house,
    commander,
    commander_martial,
    fleet_dict
):
    """
    Authoritatively submit a fleet.

    Fleet rules:
        - At least 20 non-supply ships.
        - Maximum normal ships = 20 + admiral Martial.
        - Supply ships count toward that maximum at 5:1.
          Every 5 supply ships consume 1 maximum fleet slot.
        - Commander Martial is stored with the fleet.

    Returns:
        {
            "success": bool,
            "fleet_id": str | None,
            "message": str
        }
    """

    if not fleet_dict:
        return {
            "success": False,
            "fleet_id": None,
            "message": "No ships selected."
        }

    try:
        commander_martial = int(commander_martial)
    except (TypeError, ValueError):
        return {
            "success": False,
            "fleet_id": None,
            "message": "Admiral Martial must be a whole number."
        }

    if commander_martial < 0:
        return {
            "success": False,
            "fleet_id": None,
            "message": "Admiral Martial cannot be negative."
        }

    commander = str(commander).strip()

    if not commander:
        return {
            "success": False,
            "fleet_id": None,
            "message": "An admiral name is required."
        }

    try:
        conn.execute("BEGIN")

        # -----------------------------------------------------
        # 1. Verify battle exists and fleets are not locked.
        # -----------------------------------------------------
        cursor.execute("""
            SELECT fleets_locked
            FROM battles
            WHERE id=?
        """, (battle_id,))

        battle_row = cursor.fetchone()

        if not battle_row:
            conn.execute("ROLLBACK")

            return {
                "success": False,
                "fleet_id": None,
                "message": "Battle not found."
            }

        if bool(battle_row[0]):
            conn.execute("ROLLBACK")

            return {
                "success": False,
                "fleet_id": None,
                "message": (
                    "Fleets are locked for this battle. "
                    "No further fleet creation is allowed."
                )
            }

        # -----------------------------------------------------
        # 2. Verify house belongs to the battle.
        # -----------------------------------------------------
        cursor.execute("""
            SELECT 1
            FROM battle_side_houses
            WHERE battle_id=?
              AND house=?
            LIMIT 1
        """, (
            battle_id,
            house
        ))

        if cursor.fetchone() is None:
            conn.execute("ROLLBACK")

            return {
                "success": False,
                "fleet_id": None,
                "message": (
                    f"**{house}** is not assigned to either side "
                    f"of this battle."
                )
            }

        # -----------------------------------------------------
        # 3. Normalize requested quantities.
        # -----------------------------------------------------
        normalized_fleet = {}

        for ship_type, requested_amount in fleet_dict.items():
            try:
                requested_amount = int(requested_amount)
            except (TypeError, ValueError):
                conn.execute("ROLLBACK")

                return {
                    "success": False,
                    "fleet_id": None,
                    "message": (
                        f"Invalid quantity for `{ship_type}`."
                    )
                }

            if requested_amount <= 0:
                conn.execute("ROLLBACK")

                return {
                    "success": False,
                    "fleet_id": None,
                    "message": (
                        f"Ship quantity for `{ship_type}` "
                        f"must be greater than zero."
                    )
                }

            normalized_fleet[ship_type] = requested_amount

        # -----------------------------------------------------
        # 4. Calculate fleet size.
        #
        # Supply ships count at 5:1:
        #
        # 1-4 supply ships = 0 fleet slots
        # 5-9 supply ships = 1 fleet slot
        # 10-14 supply ships = 2 fleet slots
        # etc.
        # -----------------------------------------------------
        normal_ship_count = 0
        supply_ship_count = 0

        for ship_type, amount in normalized_fleet.items():
            ship_data = config.SHIPS.get(ship_type, {})

            if ship_data.get("supply_cost", 0) < 0:
                supply_ship_count += amount
            else:
                normal_ship_count += amount

        # Minimum of 20 ships excluding supply ships.
        if normal_ship_count < 20:
            conn.execute("ROLLBACK")

            return {
                "success": False,
                "fleet_id": None,
                "message": (
                    f"A fleet requires at least **20 non-supply ships**. "
                    f"This fleet only has **{normal_ship_count}**."
                )
            }

        supply_slots = supply_ship_count // 5

        fleet_size = normal_ship_count + supply_slots

        maximum_fleet_size = 20 + commander_martial

        if fleet_size > maximum_fleet_size:
            conn.execute("ROLLBACK")

            return {
                "success": False,
                "fleet_id": None,
                "message": (
                    f"This fleet is too large for **{commander}**.\n"
                    f"Admiral Martial: **{commander_martial}**\n"
                    f"Maximum fleet size: **{maximum_fleet_size}**\n"
                    f"Fleet size: **{fleet_size}** "
                    f"({normal_ship_count} ships + "
                    f"{supply_slots} supply slots)"
                )
            }

        # -----------------------------------------------------
        # 5. Recalculate current ownership.
        # -----------------------------------------------------
        cursor.execute("""
            SELECT ship_type, SUM(amount)
            FROM fleet_ledger
            WHERE house=?
            GROUP BY ship_type
        """, (house,))

        owned_rows = cursor.fetchall()

        owned = {
            ship_type: amount
            for ship_type, amount in owned_rows
        }

        # -----------------------------------------------------
        # 6. Recalculate current commitments.
        # -----------------------------------------------------
        cursor.execute("""
            SELECT bf.ship_type, SUM(bf.amount)
            FROM battle_fleets bf
            JOIN battles b ON bf.battle_id = b.id
            WHERE bf.house=?
              AND b.status='preparing'
            GROUP BY bf.ship_type
        """, (house,))

        committed_rows = cursor.fetchall()

        committed = {
            ship_type: amount
            for ship_type, amount in committed_rows
        }

        # -----------------------------------------------------
        # 7. Verify live availability.
        # -----------------------------------------------------
        for ship_type, requested_amount in normalized_fleet.items():
            owned_amount = owned.get(
                ship_type,
                0
            )

            committed_amount = committed.get(
                ship_type,
                0
            )

            available = owned_amount - committed_amount

            if requested_amount > available:
                conn.execute("ROLLBACK")

                return {
                    "success": False,
                    "fleet_id": None,
                    "message": (
                        f"Insufficient **{ship_type}** available. "
                        f"Only {max(available, 0)} available."
                    )
                }

        # -----------------------------------------------------
        # 8. Generate fleet ID.
        # -----------------------------------------------------
        fleet_id = str(uuid.uuid4())

        # -----------------------------------------------------
        # 9. Insert the complete fleet atomically.
        # -----------------------------------------------------
        for ship_type, amount in normalized_fleet.items():
            cursor.execute("""
                INSERT INTO battle_fleets(
                    battle_id,
                    house,
                    ship_type,
                    amount,
                    commander,
                    commander_martial,
                    fleet_id
                )
                VALUES(?, ?, ?, ?, ?, ?, ?)
            """, (
                battle_id,
                house,
                ship_type,
                amount,
                commander,
                commander_martial,
                fleet_id
            ))

        conn.commit()

        return {
            "success": True,
            "fleet_id": fleet_id,
            "message": "Fleet submitted successfully."
        }

    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass

        raise


# =========================================================
# SHIP REQUESTS
# =========================================================

def create_ship_request(user_id, house, ship_type, amount, comment=None):
    cursor.execute("""
    INSERT INTO ship_requests(user_id, house, ship_type, amount, comment)
    VALUES(?, ?, ?, ?, ?)
    """, (user_id, house, ship_type, amount, comment))
    conn.commit()
    return cursor.lastrowid


def get_ship_request(request_id):
    cursor.execute("""
    SELECT id, user_id, house, ship_type, amount, status, staff_name, deny_reason, comment, added_to_ledger
    FROM ship_requests
    WHERE id=?
    """, (request_id,))
    row = cursor.fetchone()
    if not row:
        return None

    return {
        "id": row[0],
        "user_id": row[1],
        "house": row[2],
        "ship_type": row[3],
        "amount": row[4],
        "status": row[5],
        "staff_name": row[6],
        "deny_reason": row[7],
        "comment": row[8],
        "added_to_ledger": row[9],
    }


def update_ship_request_status(request_id, status, staff_name, deny_reason=None):
    cursor.execute("""
    UPDATE ship_requests
    SET status=?, staff_name=?, deny_reason=?
    WHERE id=?
    """, (status, staff_name, deny_reason, request_id))
    conn.commit()


def mark_ship_request_added_to_ledger(request_id):
    cursor.execute("""
    UPDATE ship_requests
    SET added_to_ledger=1
    WHERE id=?
    """, (request_id,))
    conn.commit()


# =========================================================
# HOUSE PROFILES
# =========================================================

def upsert_house(house_name, duchy=None, culture=None, port_level=0, region=None):
    cursor.execute("""
    INSERT INTO houses(house_name, duchy, culture, port_level, region)
    VALUES(?, ?, ?, ?, ?)
    ON CONFLICT(house_name)
    DO UPDATE SET
        duchy=excluded.duchy,
        culture=excluded.culture,
        port_level=excluded.port_level,
        region=excluded.region
    """, (house_name, duchy, culture, port_level, region))
    conn.commit()


def sync_houses_from_list(role_list):
    """
    Accepts a list of (role_id, role_name) tuples and upserts them into the houses table.
    Existing houses not present in the list are left untouched.
    """
    try:
        cursor.execute("BEGIN")
        for role_id, role_name in role_list:
            cursor.execute("INSERT OR IGNORE INTO houses(house_name, duchy, culture, port_level, region, role_id) VALUES(?, NULL, NULL, 0, NULL, ?)", (role_name, role_id))
            cursor.execute("UPDATE houses SET role_id=? WHERE house_name=?", (role_id, role_name))
        conn.commit()
    except Exception:
        conn.rollback()


def ensure_house_exists(house_name):
    cursor.execute("""
    INSERT OR IGNORE INTO houses(house_name, duchy, culture, port_level, region)
    VALUES(?, NULL, NULL, 0, NULL)
    """, (house_name,))
    conn.commit()


def get_house(house_name):
    cursor.execute("""
    SELECT house_name, duchy, culture, port_level, region
    FROM houses
    WHERE house_name=?
    """, (house_name,))
    row = cursor.fetchone()
    if not row:
        return None

    return {
        "house_name": row[0],
        "duchy": row[1],
        "culture": row[2],
        "port_level": row[3],
        "region": row[4],
    }


def set_house_culture(house_name, culture):
    house = get_house(house_name)
    if house:
        cursor.execute("UPDATE houses SET culture=? WHERE house_name=?", (culture, house_name))
    else:
        cursor.execute("INSERT INTO houses(house_name, culture, port_level) VALUES(?, ?, 0)", (house_name, culture))
    conn.commit()

def set_house_region(house_name, region):
    house = get_house(house_name)
    if house:
        cursor.execute("UPDATE houses SET region=? WHERE house_name=?", (region, house_name))
    else:
        cursor.execute("INSERT INTO houses(house_name, region, port_level) VALUES(?, ?, 0)", (house_name, region))
    conn.commit()

def set_house_port_level(house_name, port_level):
    house = get_house(house_name)
    if house:
        cursor.execute("UPDATE houses SET port_level=? WHERE house_name=?", (port_level, house_name))
    else:
        cursor.execute("INSERT INTO houses(house_name, port_level) VALUES(?, ?)", (house_name, port_level))
    conn.commit()


# =========================================================
# FLEET LEDGER
# =========================================================

def add_fleet_entry(house, ship_type, amount):
    cursor.execute("""
    INSERT INTO fleet_ledger(house, ship_type, amount)
    VALUES(?, ?, ?)
    """, (house, ship_type, amount))
    conn.commit()
    return cursor.lastrowid


def get_fleet_for_house(house):
    cursor.execute("""
    SELECT ship_type, SUM(amount)
    FROM fleet_ledger
    WHERE house=?
    GROUP BY ship_type
    """, (house,))
    rows = cursor.fetchall()
    return {ship_type: amount for ship_type, amount in rows}


def remove_fleet_entry(house, ship_type, amount):
    cursor.execute("""
    INSERT INTO fleet_ledger(house, ship_type, amount)
    VALUES(?, ?, ?)
    """, (house, ship_type, -amount))
    conn.commit()

def get_ships_by_region(region):
    cursor.execute("""
        SELECT
            h.name,
            fl.ship_type,
            SUM(fl.amount)
        FROM houses h
        LEFT JOIN fleet_ledger fl
            ON fl.house = h.name
        WHERE LOWER(h.region) = LOWER(?)
        GROUP BY h.name, fl.ship_type
        ORDER BY h.name, fl.ship_type
    """, (region,))

    rows = cursor.fetchall()

    result = {}

    for house, ship_type, amount in rows:
        if not ship_type:
            continue

        result.setdefault(house, {})
        result[house][ship_type] = amount

    return result

# =========================================================
# PORT REQUESTS
# =========================================================

def create_port_request(user_id, house, requested_level, comment=None):
    cursor.execute("""
    INSERT INTO port_upgrade_requests(user_id, house, requested_level, comment)
    VALUES(?, ?, ?, ?)
    """, (user_id, house, requested_level, comment))
    conn.commit()
    return cursor.lastrowid


def get_port_request(request_id):
    cursor.execute("""
    SELECT id, user_id, house, requested_level, status, staff_name, deny_reason, comment
    FROM port_upgrade_requests
    WHERE id=?
    """, (request_id,))
    row = cursor.fetchone()
    if not row:
        return None

    return {
        "id": row[0],
        "user_id": row[1],
        "house": row[2],
        "requested_level": row[3],
        "status": row[4],
        "staff_name": row[5],
        "deny_reason": row[6],
        "comment": row[7],
    }


def update_port_request_status(request_id, status, staff_name, deny_reason=None):
    cursor.execute("""
    UPDATE port_upgrade_requests
    SET status=?, staff_name=?, deny_reason=?
    WHERE id=?
    """, (status, staff_name, deny_reason, request_id))
    conn.commit()


# =========================================================
# STAFF HELPERS
# =========================================================

def get_all_houses():
    cursor.execute("SELECT house_name FROM houses ORDER BY house_name")
    return [row[0] for row in cursor.fetchall()]


def search_houses(prefix: str, limit: int = 25):
    """Return up to `limit` houses whose names contain `prefix` (case-insensitive)."""
    like = f"%{prefix}%" if prefix else "%"
    cursor.execute("SELECT house_name FROM houses WHERE house_name LIKE ? COLLATE NOCASE ORDER BY house_name LIMIT ?", (like, limit))
    return [row[0] for row in cursor.fetchall()]


# =========================================================
# BATTLES
# =========================================================

def create_battle(
    name,
    attacker,
    defender,
    created_by,
    culture_modifiers=None
):
    culture_modifiers = culture_modifiers or []

    cursor.execute("""
        INSERT INTO battles(
            name,
            attacker_house,
            defender_house,
            created_by,
            culture_modifiers
        )
        VALUES(?, ?, ?, ?, ?)
    """, (
        name,
        attacker,
        defender,
        created_by,
        json.dumps(culture_modifiers)
    ))

    conn.commit()

    battle_id = cursor.lastrowid

    try:
        cursor.execute("""
            INSERT OR IGNORE INTO battle_side_houses(
                battle_id,
                side,
                house
            )
            VALUES(?, ?, ?)
        """, (
            battle_id,
            "attacker",
            attacker
        ))

        cursor.execute("""
            INSERT OR IGNORE INTO battle_side_houses(
                battle_id,
                side,
                house
            )
            VALUES(?, ?, ?)
        """, (
            battle_id,
            "defender",
            defender
        ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    return battle_id


def get_battle(battle_id):
    cursor.execute("""
        SELECT
            id,
            name,
            attacker_house,
            defender_house,
            status,
            attacker_thread_id,
            defender_thread_id,
            thread_id,
            created_by,
            fleets_locked,
            current_round,
            attacker_retreat,
            defender_retreat,
            culture_modifiers
        FROM battles
        WHERE id=?
    """, (battle_id,))

    row = cursor.fetchone()

    if not row:
        return None

    return {
        "id": row[0],
        "name": row[1],
        "attacker_house": row[2],
        "defender_house": row[3],
        "status": row[4],
        "attacker_thread_id": row[5],
        "defender_thread_id": row[6],
        "thread_id": row[7],
        "created_by": row[8],
        "fleets_locked": bool(row[9]),
        "current_round": row[10] or 0,
        "attacker_retreat": bool(row[11]),
        "defender_retreat": bool(row[12]),
        "culture_modifiers": (
            json.loads(row[13])
            if row[13]
            else []
        ),
    }


def update_battle_thread(battle_id, thread_id):
    cursor.execute("""
    UPDATE battles
    SET thread_id=?
    WHERE id=?
    """, (thread_id, battle_id))
    conn.commit()


def update_battle_threads(battle_id, attacker_thread_id, defender_thread_id):
    cursor.execute("""
    UPDATE battles
    SET attacker_thread_id=?, defender_thread_id=?
    WHERE id=?
    """, (attacker_thread_id, defender_thread_id, battle_id))
    conn.commit()


def get_battle_by_thread(thread_id):
    cursor.execute("""
    SELECT id, name, attacker_house, defender_house, status, attacker_thread_id, defender_thread_id, created_by, fleets_locked
    FROM battles
    WHERE attacker_thread_id=? OR defender_thread_id=?
    """, (thread_id, thread_id))
    row = cursor.fetchone()
    if not row:
        return None

    side = "attacker" if row[5] == thread_id else "defender"
    return {
        "id": row[0],
        "name": row[1],
        "attacker_house": row[2],
        "defender_house": row[3],
        "status": row[4],
        "attacker_thread_id": row[5],
        "defender_thread_id": row[6],
        "created_by": row[7],
        "fleets_locked": bool(row[8]),
        "side": side,
    }


def get_active_battles():
    cursor.execute("""
    SELECT id, name, attacker_house, defender_house, status, thread_id
    FROM battles
    WHERE status='preparing'
    """)
    rows = cursor.fetchall()
    return [{
        "id": row[0],
        "name": row[1],
        "attacker_house": row[2],
        "defender_house": row[3],
        "status": row[4],
        "thread_id": row[5],
    } for row in rows]

# =========================================================
# LIVE BATTLE COMBAT STATE
# =========================================================

def clear_battle_fleet_state(battle_id):
    cursor.execute("""
        DELETE FROM battle_fleet_state
        WHERE battle_id=?
    """, (battle_id,))

    conn.commit()


def create_battle_fleet_state(
    battle_id,
    fleet_id,
    ship_type,
    amount,
    health,
    damage
):
    cursor.execute("""
        INSERT INTO battle_fleet_state(
            battle_id,
            fleet_id,
            ship_type,
            amount,
            health,
            damage
        )
        VALUES(?, ?, ?, ?, ?, ?)
    """, (
        battle_id,
        fleet_id,
        ship_type,
        amount,
        health,
        damage
    ))


def get_battle_fleet_state(battle_id):
    cursor.execute("""
        SELECT
            fleet_id,
            ship_type,
            amount,
            health,
            damage
        FROM battle_fleet_state
        WHERE battle_id=?
        ORDER BY id
    """, (battle_id,))

    rows = cursor.fetchall()

    state = {}

    for fleet_id, ship_type, amount, health, damage in rows:
        state.setdefault(
            fleet_id,
            {
                "fleet_id": fleet_id,
                "ships": {}
            }
        )

        state[fleet_id]["ships"][ship_type] = {
            "amount": amount,
            "health": health,
            "damage": damage
        }

    return state


def set_battle_fleet_ship_amount(
    battle_id,
    fleet_id,
    ship_type,
    amount
):
    cursor.execute("""
        UPDATE battle_fleet_state
        SET amount=?
        WHERE battle_id=?
          AND fleet_id=?
          AND ship_type=?
    """, (
        amount,
        battle_id,
        fleet_id,
        ship_type
    ))


def save_battle_fleet_state(battle_id, state):
    try:
        conn.execute("BEGIN")

        cursor.execute("""
            DELETE FROM battle_fleet_state
            WHERE battle_id=?
        """, (battle_id,))

        for fleet_id, fleet in state.items():
            for ship_type, ship in fleet["ships"].items():
                cursor.execute("""
                    INSERT INTO battle_fleet_state(
                        battle_id,
                        fleet_id,
                        ship_type,
                        amount,
                        health,
                        damage
                    )
                    VALUES(?, ?, ?, ?, ?, ?)
                """, (
                    battle_id,
                    fleet_id,
                    ship_type,
                    ship["amount"],
                    ship["health"],
                    ship["damage"]
                ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise


def set_battle_status(
    battle_id,
    status,
    current_round=None
):
    if current_round is None:
        cursor.execute("""
            UPDATE battles
            SET status=?
            WHERE id=?
        """, (
            status,
            battle_id
        ))
    else:
        cursor.execute("""
            UPDATE battles
            SET status=?,
                current_round=?
            WHERE id=?
        """, (
            status,
            current_round,
            battle_id
        ))

    conn.commit()


def set_battle_retreat(
    battle_id,
    side,
    value=True
):
    column = (
        "attacker_retreat"
        if side == "attacker"
        else "defender_retreat"
    )

    if column not in {
        "attacker_retreat",
        "defender_retreat"
    }:
        raise ValueError("Invalid battle side.")

    cursor.execute(
        f"""
        UPDATE battles
        SET {column}=?
        WHERE id=?
        """,
        (
            1 if value else 0,
            battle_id
        )
    )

    conn.commit()


def reset_battle_retreats(battle_id):
    cursor.execute("""
        UPDATE battles
        SET attacker_retreat=0,
            defender_retreat=0
        WHERE id=?
    """, (battle_id,))

    conn.commit()


def save_battle_round(
    battle_id,
    round_number,
    attacker_damage,
    defender_damage,
    attacker_dice,
    defender_dice,
    attacker_ship_dice,
    defender_ship_dice,
    attacker_destroyed,
    defender_destroyed,
    attacker_retreat=False,
    defender_retreat=False,
    notes=None
):
    cursor.execute("""
        INSERT OR REPLACE INTO battle_rounds(
            battle_id,
            round_number,
            attacker_damage,
            defender_damage,
            attacker_dice,
            defender_dice,
            attacker_ship_dice,
            defender_ship_dice,
            attacker_destroyed,
            defender_destroyed,
            attacker_retreat,
            defender_retreat,
            notes
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        battle_id,
        round_number,
        attacker_damage,
        defender_damage,
        attacker_dice,
        defender_dice,
        attacker_ship_dice,
        defender_ship_dice,
        attacker_destroyed,
        defender_destroyed,
        1 if attacker_retreat else 0,
        1 if defender_retreat else 0,
        notes
    ))

    conn.commit()


def get_battle_rounds(battle_id):
    cursor.execute("""
        SELECT
            round_number,
            attacker_damage,
            defender_damage,
            attacker_dice,
            defender_dice,
            attacker_ship_dice,
            defender_ship_dice,
            attacker_destroyed,
            defender_destroyed,
            attacker_retreat,
            defender_retreat,
            notes
        FROM battle_rounds
        WHERE battle_id=?
        ORDER BY round_number
    """, (battle_id,))

    rows = cursor.fetchall()

    return [
        {
            "round": row[0],
            "attacker_damage": row[1],
            "defender_damage": row[2],
            "attacker_dice": row[3],
            "defender_dice": row[4],
            "attacker_ship_dice": row[5],
            "defender_ship_dice": row[6],
            "attacker_destroyed": row[7],
            "defender_destroyed": row[8],
            "attacker_retreat": bool(row[9]),
            "defender_retreat": bool(row[10]),
            "notes": row[11]
        }
        for row in rows
    ]
# =========================================================
# Battle side house helpers
# =========================================================
def assign_house_to_side(battle_id, side, house_name):
    cursor.execute("INSERT OR IGNORE INTO battle_side_houses(battle_id, side, house) VALUES(?, ?, ?)", (battle_id, side, house_name))
    conn.commit()


def remove_house_from_side(battle_id, side, house_name):
    cursor.execute("DELETE FROM battle_side_houses WHERE battle_id=? AND side=? AND house=?", (battle_id, side, house_name))
    conn.commit()


def get_houses_for_side(battle_id, side):
    cursor.execute("SELECT house FROM battle_side_houses WHERE battle_id=? AND side=? ORDER BY house", (battle_id, side))
    return [row[0] for row in cursor.fetchall()]


# =========================================================
# BATTLE FLEETS
# =========================================================

def add_battle_fleet_entry(battle_id, house, ship_type, amount, commander=None, fleet_id=None):
    cursor.execute("""
    INSERT INTO battle_fleets(battle_id, house, ship_type, amount, commander, fleet_id)
    VALUES(?, ?, ?, ?, ?, ?)
    """, (battle_id, house, ship_type, amount, commander, fleet_id))
    conn.commit()
    return cursor.lastrowid


def get_battle_fleet(battle_id, house):
    cursor.execute("""
    SELECT ship_type, SUM(amount)
    FROM battle_fleets
    WHERE battle_id=? AND house=?
    GROUP BY ship_type
    """, (battle_id, house))
    rows = cursor.fetchall()
    return {ship_type: amount for ship_type, amount in rows}


def get_all_battle_fleets(battle_id):
    cursor.execute("""
    SELECT house, ship_type, amount
    FROM battle_fleets
    WHERE battle_id=?
    """, (battle_id,))
    rows = cursor.fetchall()
    fleets = {}
    for house, ship_type, amount in rows:
        if house not in fleets:
            fleets[house] = {}
        fleets[house][ship_type] = fleets[house].get(ship_type, 0) + amount
    return fleets


def get_battle_fleet_groups(battle_id):
    cursor.execute("""
        SELECT
            house,
            commander,
            commander_martial,
            fleet_id,
            ship_type,
            amount
        FROM battle_fleets
        WHERE battle_id=?
        ORDER BY rowid
    """, (battle_id,))

    rows = cursor.fetchall()

    groups = {}

    for (
        house,
        commander,
        commander_martial,
        fleet_id,
        ship_type,
        amount
    ) in rows:

        if not fleet_id:
            fleet_id = "unknown"

        if fleet_id not in groups:
            groups[fleet_id] = {
                "fleet_id": fleet_id,
                "house": house,
                "commander": commander,
                "commander_martial": (
                    commander_martial or 0
                ),
                "ships": {}
            }

        groups[fleet_id]["ships"][
            ship_type
        ] = (
            groups[fleet_id]["ships"].get(
                ship_type,
                0
            ) + amount
        )

    return list(groups.values())


def is_battle_fleets_locked(battle_id):
    cursor.execute("SELECT fleets_locked FROM battles WHERE id=?", (battle_id,))
    row = cursor.fetchone()
    return bool(row[0]) if row else False


def lock_battle_fleets(battle_id):
    cursor.execute("UPDATE battles SET fleets_locked=1 WHERE id=?", (battle_id,))
    conn.commit()


def unlock_battle_fleets(battle_id):
    cursor.execute("UPDATE battles SET fleets_locked=0 WHERE id=?", (battle_id,))
    conn.commit()


def delete_battle_fleet(battle_id, fleet_id):
    if fleet_id == "unknown":
        cursor.execute("DELETE FROM battle_fleets WHERE battle_id=? AND fleet_id IS NULL", (battle_id,))
    else:
        cursor.execute("DELETE FROM battle_fleets WHERE battle_id=? AND fleet_id=?", (battle_id, fleet_id))
    deleted = cursor.rowcount > 0
    conn.commit()
    return deleted


def delete_all_battle_fleets(battle_id):
    cursor.execute("DELETE FROM battle_fleets WHERE battle_id=?", (battle_id,))
    conn.commit()
    deleted_count = cursor.rowcount
    return deleted_count

# =========================================================
# AVAILABILITY / RESERVATION HELPERS
# =========================================================

def get_committed_ships_for_house(house_name):
    """Return a dict of ship_type -> amount that are committed for this house
    across all active/preparing battles. These ships should be treated as reserved
    and not available for new fleet submissions."""
    cursor.execute("""
    SELECT bf.ship_type, SUM(bf.amount)
    FROM battle_fleets bf
    JOIN battles b ON bf.battle_id = b.id
    WHERE bf.house=? AND b.status='preparing'
    GROUP BY bf.ship_type
    """, (house_name,))
    rows = cursor.fetchall()
    return {ship_type: amount for ship_type, amount in rows}


def get_available_fleet_for_house(house_name):
    """Return a dict of ship_type -> available amount for the house after
    subtracting committed ships from the ledger totals."""
    owned = get_fleet_for_house(house_name)
    committed = get_committed_ships_for_house(house_name)

    available = {}
    for ship_type, owned_amount in owned.items():
        committed_amount = committed.get(ship_type, 0)
        avail = owned_amount - committed_amount
        if avail > 0:
            available[ship_type] = avail
    return available


def reserve_battle_fleet_entries(
    battle_id,
    house,
    fleet_dict,
    commander=None,
    commander_martial=None
):
    """
    Reserve a fleet for a preparing battle.

    This does NOT alter fleet_ledger.
    It only creates battle_fleets commitment rows.
    """

    try:
        conn.execute("BEGIN")

        cursor.execute("""
            SELECT ship_type, SUM(amount)
            FROM fleet_ledger
            WHERE house=?
            GROUP BY ship_type
        """, (house,))

        owned_rows = cursor.fetchall()

        owned = {
            ship_type: amount
            for ship_type, amount in owned_rows
        }

        cursor.execute("""
            SELECT bf.ship_type, SUM(bf.amount)
            FROM battle_fleets bf
            JOIN battles b
                ON bf.battle_id = b.id
            WHERE bf.house=?
              AND b.status='preparing'
            GROUP BY bf.ship_type
        """, (house,))

        committed_rows = cursor.fetchall()

        committed = {
            ship_type: amount
            for ship_type, amount in committed_rows
        }

        for ship_type, requested_amount in fleet_dict.items():
            owned_amount = owned.get(ship_type, 0)
            committed_amount = committed.get(ship_type, 0)

            available = owned_amount - committed_amount

            if requested_amount > available:
                conn.execute("ROLLBACK")
                return False

        fleet_id = str(uuid.uuid4())

        for ship_type, amount in fleet_dict.items():
            cursor.execute("""
                INSERT INTO battle_fleets(
                    battle_id,
                    house,
                    ship_type,
                    amount,
                    commander,
                    commander_martial,
                    fleet_id
                )
                VALUES(?, ?, ?, ?, ?, ?, ?)
            """, (
                battle_id,
                house,
                ship_type,
                amount,
                commander,
                commander_martial,
                fleet_id
            ))

        conn.commit()

        return True

    except Exception:
        conn.rollback()
        raise