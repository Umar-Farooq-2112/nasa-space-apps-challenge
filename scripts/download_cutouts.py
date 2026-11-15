"""Download FITS cutouts for the images listed by find_images.py.
Usage: download_cutouts.py RA DEC [SIZE_DEG=0.1] [MAX=10]
Saves to data/raw/cutouts/<ra>_<dec>/ (gitignored). Retries when IRSA says busy.
"""
import csv
import sys
import time
from pathlib import Path

import requests

ra, dec = sys.argv[1], sys.argv[2]
size = sys.argv[3] if len(sys.argv) > 3 else "0.1"
limit = int(sys.argv[4]) if len(sys.argv) > 4 else 10

rows = list(csv.reader(open(f"data/raw/images_{float(ra)}_{float(dec)}.csv")))[1:]
out = Path(f"data/raw/cutouts/{ra}_{dec}")
out.mkdir(parents=True, exist_ok=True)

# spread picks across the whole time range
step = max(1, len(rows) // limit)
for uri, mjd, band, *_ in rows[::step][:limit]:
    name = f"{float(mjd):.4f}_{band.split('-')[-1]}_{Path(uri).name}"
    dest = out / name
    if dest.exists():
        continue
    url = f"https://irsa.ipac.caltech.edu/{uri}?center={ra},{dec}&size={size}"
    for attempt in range(20):
        try:
            r = requests.get(url, timeout=180)
            if r.status_code == 200 and r.content[:6] == b"SIMPLE":
                dest.write_bytes(r.content)
                print("ok", name, len(r.content), flush=True)
                break
            print("retry", r.status_code, r.text[:60].replace("\n", " "), flush=True)
        except requests.RequestException as e:
            print("retry", type(e).__name__, flush=True)
        time.sleep(5)
