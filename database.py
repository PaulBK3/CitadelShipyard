import sqlite3

conn = sqlite3.connect("ships.db")
cursor = conn.cursor()


def setup():
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
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("PRAGMA table_info(ship_requests)")
    columns = [row[1] for row in cursor.fetchall()]

    if "deny_reason" not in columns:
        cursor.execute("ALTER TABLE ship_requests ADD COLUMN deny_reason TEXT")

    if "comment" not in columns:
        cursor.execute("ALTER TABLE ship_requests ADD COLUMN comment TEXT")

    conn.commit()


def create_ship_request(user_id, house, ship_type, amount, comment=None):
    cursor.execute("""
    INSERT INTO ship_requests(user_id, house, ship_type, amount, comment)
    VALUES(?, ?, ?, ?, ?)
    """, (user_id, house, ship_type, amount, comment))

    conn.commit()
    return cursor.lastrowid


def get_ship_request(request_id):
    cursor.execute("""
    SELECT id, user_id, house, ship_type, amount, status, staff_name, deny_reason, comment
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
    }


def update_ship_request_status(request_id, status, staff_name, deny_reason=None):
    cursor.execute("""
    UPDATE ship_requests
    SET status=?, staff_name=?, deny_reason=?
    WHERE id=?
    """, (status, staff_name, deny_reason, request_id))

    conn.commit()