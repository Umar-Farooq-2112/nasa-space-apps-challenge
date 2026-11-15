"""Probe unWISE (unwise.me) time-resolved cutouts. Usage: probe_unwise.py RA DEC [SIZE_PIX=100]
Saves the raw response to data/raw/probe/unwise_response.bin and prints what it looks like.
"""
import sys
import tarfile
from pathlib import Path

import requests

ra, dec = sys.argv[1], sys.argv[2]
size = sys.argv[3] if len(sys.argv) > 3 else "100"
out = Path("data/raw/probe")
out.mkdir(parents=True, exist_ok=True)

for base in ("https://unwise.me", "http://unwise.me"):
    url = f"{base}/cutout_fits"
    params = {"version": "neo7", "ra": ra, "dec": dec, "size": size, "bands": "1"}
    try:
        r = requests.get(url, params=params, timeout=120)
    except requests.RequestException as e:
        print(base, "FAILED", type(e).__name__, str(e)[:100])
        continue
    print(base, "HTTP", r.status_code, r.headers.get("content-type"), len(r.content), "bytes")
    print("first bytes:", r.content[:120])
    if r.status_code == 200:
        dest = out / "unwise_response.bin"
        dest.write_bytes(r.content)
        try:
            with tarfile.open(dest) as t:
                names = t.getnames()
                print(len(names), "files in tar; first 12:", names[:12])
        except tarfile.TarError:
            print("not a tar file")
        break
