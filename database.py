import sqlite3

conn = sqlite3.connect("ships.db")
cursor = conn.cursor()


def setup():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ship_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        player_name TEXT NOT NULL,
        region TEXT NOT NULL,
        ship_type TEXT NOT NULL,
        amount INTEGER NOT NULL,
        rp_link TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        staff_name TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()


def create_ship_request(user_id, player_name, region, ship_type, amount, rp_link):
    cursor.execute("""
    INSERT INTO ship_requests(user_id, player_name, region, ship_type, amount, rp_link)
    VALUES(?, ?, ?, ?, ?, ?)
    """, (user_id, player_name, region, ship_type, amount, rp_link))

    conn.commit()
    return cursor.lastrowid


def get_ship_request(request_id):
    cursor.execute("""
    SELECT id, user_id, player_name, region, ship_type, amount, rp_link, status, staff_name
    FROM ship_requests
    WHERE id=?
    """, (request_id,))

    row = cursor.fetchone()

    if not row:
        return None

    return {
        "id": row[0],
        "user_id": row[1],
        "player_name": row[2],
        "region": row[3],
        "ship_type": row[4],
        "amount": row[5],
        "rp_link": row[6],
        "status": row[7],
        "staff_name": row[8],
    }


def update_ship_request_status(request_id, status, staff_name):
    cursor.execute("""
    UPDATE ship_requests
    SET status=?, staff_name=?
    WHERE id=?
    """, (status, staff_name, request_id))

    conn.commit()