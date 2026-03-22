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
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()


def create_ship_request(user_id, house, ship_type, amount):
    cursor.execute("""
    INSERT INTO ship_requests(user_id, house, ship_type, amount)
    VALUES(?, ?, ?, ?)
    """, (user_id, house, ship_type, amount))

    conn.commit()
    return cursor.lastrowid


def get_ship_request(request_id):
    cursor.execute("""
    SELECT id, user_id, house, ship_type, amount, status, staff_name
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
    }


def update_ship_request_status(request_id, status, staff_name):
    cursor.execute("""
    UPDATE ship_requests
    SET status=?, staff_name=?
    WHERE id=?
    """, (status, staff_name, request_id))

    conn.commit()