import sqlite3

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

    # ----------------------------
    # House Profiles
    # ----------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS houses (
        house_name TEXT PRIMARY KEY,
        duchy TEXT,
        culture TEXT,
        port_level INTEGER NOT NULL DEFAULT 0
    )
    """)

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

def upsert_house(house_name, duchy=None, culture=None, port_level=0):
    cursor.execute("""
    INSERT INTO houses(house_name, duchy, culture, port_level)
    VALUES(?, ?, ?, ?)
    ON CONFLICT(house_name)
    DO UPDATE SET
        duchy=excluded.duchy,
        culture=excluded.culture,
        port_level=excluded.port_level
    """, (house_name, duchy, culture, port_level))
    conn.commit()


def get_house(house_name):
    cursor.execute("""
    SELECT house_name, duchy, culture, port_level
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
    }


def set_house_culture(house_name, culture):
    house = get_house(house_name)
    if house:
        cursor.execute("UPDATE houses SET culture=? WHERE house_name=?", (culture, house_name))
    else:
        cursor.execute("INSERT INTO houses(house_name, culture, port_level) VALUES(?, ?, 0)", (house_name, culture))
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

def add_fleet_entry(house, ship_type, amount, source_request_id=None, added_by=None):
    cursor.execute("""
    INSERT INTO fleet_ledger(house, ship_type, amount, source_request_id, added_by)
    VALUES(?, ?, ?, ?, ?)
    """, (house, ship_type, amount, source_request_id, added_by))
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