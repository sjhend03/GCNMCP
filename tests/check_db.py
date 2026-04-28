import sqlite3

conn = sqlite3.connect("gcn.sqlite")
print("rows=", conn.execute("select count(*) from circulars").fetchone()[0])
print(
    "special=",
    conn.execute(
        "select circular_id_raw, circular_id_int from circulars where circular_id_raw in ('18448.5', '18453.5')"
    ).fetchall()
)
conn.close()
