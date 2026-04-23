import requests
import json
from pathlib import Path
import time

data_dir = Path("../data")
existing = {float(f.stem) for f in data_dir.glob("*.json")}
max_id = int(max(existing))

print(f"Current max circular ID: {max_id}")

for i in range(max_id + 1, max_id + 5000):
    out = data_dir / f"{i}.json"
    if out.exists():
        continue
    try:
        r = requests.get(f"https://gcn.nasa.gov/circulars/{i}.json", timeout=10)
        if r.status_code == 404:
            print(f"404 at {i} — may have reached the end")
            break
        r.raise_for_status()
        out.write_text(r.text, encoding="utf-8")
        print(f"Downloaded {i}")
        time.sleep(0.2)  # be polite
    except Exception as e:
        print(f"Error {i}: {e}")