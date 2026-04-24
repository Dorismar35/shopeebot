import sqlite3
from pathlib import Path

db_path = Path("banco/shopeebot.db")
if not db_path.exists():
    print("Database file not found.")
else:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM ofertas;").fetchall()
    print(f"Total rows: {len(rows)}")
    for r in rows:
        print(dict(r))
    conn.close()
