import json
import sqlite3
import pathlib

conn = sqlite3.connect("gcn.sqlite")
db_ids = {row[0] for row in conn.execute("select circular_id_raw from circulars")}
raw_ids = set()

for p in pathlib.Path("data").glob("*.json"):
    obj = json.loads(p.read_text(encoding="utf-8"))
    raw_ids.add(str(obj.get("circularId")).strip())

print("missing_from_db=", sorted(raw_ids - db_ids)[:20])
print("missing_count=", len(raw_ids - db_ids))
print("extra_in_db=", sorted(db_ids - raw_ids)[:20])
print("extra_count=", len(db_ids - raw_ids))

conn.close()
