import sqlite3
import uuid

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

    # Add missing fleets_locked column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE battles ADD COLUMN fleets_locked INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # ----------------------------
    # Battle Fleets
    # ----------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS battle_fleets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        battle_id INTEGER NOT NULL,
        house TEXT NOT NULL,
        ship_type TEXT NOT NULL,
        amount INTEGER NOT NULL,
        commander TEXT,
        fleet_id TEXT,
        FOREIGN KEY (battle_id) REFERENCES battles(id)
    )
    """)

    # Add missing commander column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE battle_fleets ADD COLUMN commander TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # Add missing fleet_id column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE battle_fleets ADD COLUMN fleet_id TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    conn.commit()


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

def create_battle(name, attacker, defender, created_by):
    cursor.execute("""
    INSERT INTO battles(name, attacker_house, defender_house, created_by)
    VALUES(?, ?, ?, ?)
    """, (name, attacker, defender, created_by))
    conn.commit()
    battle_id = cursor.lastrowid
    # seed side house mappings with the initial attacker/defender
    try:
        cursor.execute("INSERT OR IGNORE INTO battle_side_houses(battle_id, side, house) VALUES(?, ?, ?)", (battle_id, 'attacker', attacker))
        cursor.execute("INSERT OR IGNORE INTO battle_side_houses(battle_id, side, house) VALUES(?, ?, ?)", (battle_id, 'defender', defender))
        conn.commit()
    except Exception:
        conn.rollback()

    return battle_id


def get_battle(battle_id):
    cursor.execute("""
    SELECT id, name, attacker_house, defender_house, status, attacker_thread_id, defender_thread_id, thread_id, created_by, fleets_locked
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
    SELECT house, commander, fleet_id, ship_type, amount
    FROM battle_fleets
    WHERE battle_id=?
    ORDER BY rowid
    """, (battle_id,))
    rows = cursor.fetchall()
    groups = {}
    for house, commander, fleet_id, ship_type, amount in rows:
        if not fleet_id:
            fleet_id = "unknown"

        if fleet_id not in groups:
            groups[fleet_id] = {
                "fleet_id": fleet_id,
                "house": house,
                "commander": commander,
                "ships": {},
            }
        groups[fleet_id]["ships"][ship_type] = groups[fleet_id]["ships"].get(ship_type, 0) + amount
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
    conn.commit()


def delete_all_battle_fleets(battle_id):
    cursor.execute("DELETE FROM battle_fleets WHERE battle_id=?", (battle_id,))
    conn.commit()


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


def reserve_battle_fleet_entries(battle_id, house, fleet_dict, commander=None):
    """Attempt to reserve the ships in `fleet_dict` (ship_type->amount) for
    `house` in `battle_id`. This checks current availability (owned minus
    committed) and if sufficient, inserts entries into battle_fleets atomically.
    Returns True on success, False on insufficient ships."""
    # Recompute availability inside a transaction to reduce race windows
    try:
        conn.execute('BEGIN')

        # Get latest owned and committed counts
        cursor.execute("""
        SELECT ship_type, SUM(amount)
        FROM fleet_ledger
        WHERE house=?
        GROUP BY ship_type
        """, (house,))
        owned_rows = cursor.fetchall()
        owned = {ship_type: amount for ship_type, amount in owned_rows}

        cursor.execute("""
        SELECT bf.ship_type, SUM(bf.amount)
        FROM battle_fleets bf
        JOIN battles b ON bf.battle_id = b.id
        WHERE bf.house=? AND b.status='preparing'
        GROUP BY bf.ship_type
        """, (house,))
        committed_rows = cursor.fetchall()
        committed = {ship_type: amount for ship_type, amount in committed_rows}

        # Verify availability for each requested ship_type
        for ship_type, req_amount in fleet_dict.items():
            owned_amount = owned.get(ship_type, 0)
            committed_amount = committed.get(ship_type, 0)
            available = owned_amount - committed_amount
            if req_amount > available:
                conn.execute('ROLLBACK')
                return False

        fleet_id = str(uuid.uuid4())
        # Insert entries
        for ship_type, amount in fleet_dict.items():
            cursor.execute("""
            INSERT INTO battle_fleets(battle_id, house, ship_type, amount, commander, fleet_id)
            VALUES(?, ?, ?, ?, ?, ?)
            """, (battle_id, house, ship_type, amount, commander, fleet_id))

        conn.commit()
        return True
    except Exception:
        conn.execute('ROLLBACK')
        raise