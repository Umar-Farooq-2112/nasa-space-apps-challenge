"""Upload every FITS file in a folder to a running Mover Spotter server (same as dragging them into the page).
Usage: upload_folder.py FOLDER DATASET_NAME [RA DEC] [--server http://localhost:8000]
"""
import sys
from pathlib import Path

import requests

args = [a for a in sys.argv[1:] if not a.startswith("--")]
server = "http://localhost:8000"
if "--server" in sys.argv:
    server = sys.argv[sys.argv.index("--server") + 1]
    args = [a for a in args if a != server]
folder, name = Path(args[0]), args[1]
body = {"name": name}
if len(args) >= 4:
    body.update(ra=float(args[2]), dec=float(args[3]))
ds = requests.post(f"{server}/api/datasets", json=body).json()["id"]
files = sorted(folder.glob("*.fits"))
for i in range(0, len(files), 4):
    batch = [("files", (f.name, f.read_bytes())) for f in files[i:i + 4]]
    for r in requests.post(f"{server}/api/datasets/{ds}/files", files=batch).json()["results"]:
        print("OK  " if r["ok"] else "SKIP", r["name"], r.get("band", ""), r.get("date", r.get("error", "")))
print("dataset id:", ds, f"-> {server}/?ds={ds}")
