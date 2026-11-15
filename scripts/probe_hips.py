"""Probe CDS hips2fits: download one cutout per survey for a position and print what we got.
Usage: probe_hips.py RA DEC [FOV_DEG=0.1]    Output: data/raw/probe/hips_<survey>.fits
"""
import sys
from pathlib import Path

import requests
from astropy.io import fits

ra, dec = sys.argv[1], sys.argv[2]
fov = sys.argv[3] if len(sys.argv) > 3 else "0.1"
URL = "https://alasky.cds.unistra.fr/hips-image-services/hips2fits"
SURVEYS = ["CDS/P/DSS2/blue", "CDS/P/DSS2/red", "CDS/P/2MASS/J", "CDS/P/allWISE/W1"]

out = Path("data/raw/probe")
out.mkdir(parents=True, exist_ok=True)
for hips in SURVEYS:
    params = {"hips": hips, "ra": ra, "dec": dec, "fov": fov, "width": 300, "height": 300,
              "projection": "TAN", "coordsys": "icrs", "format": "fits"}
    try:
        r = requests.get(URL, params=params, timeout=90)
    except requests.RequestException as e:
        print(hips, "FAILED", type(e).__name__)
        continue
    if r.status_code != 200 or r.content[:6] != b"SIMPLE":
        print(hips, "HTTP", r.status_code, r.text[:100].replace("\n", " "))
        continue
    dest = out / ("hips_" + hips.replace("/", "_") + ".fits")
    dest.write_bytes(r.content)
    h = fits.getheader(dest)
    print(hips, "OK", len(r.content), "bytes", "| date-like keys:",
          {k: h[k] for k in h if k.upper() in ("DATE-OBS", "MJD-OBS", "EPOCH", "DATE")})
