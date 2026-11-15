"""Resolve target names to real coordinates with public name resolvers (no hardcoded values).
Tries MAST (STScI) then NED (Caltech). Usage: resolve_targets.py "Barnard's star" "RW Aur" ...
Prints RA/Dec (ICRS, J2000, degrees) and which service answered.
"""
import json
import sys

import requests

MAST = "https://mast.stsci.edu/api/v0/invoke"
NED = "https://ned.ipac.caltech.edu/srs/ObjectLookup"


def mast(name):
    req = {"service": "Mast.Name.Lookup", "params": {"input": name, "format": "json"}}
    r = requests.post(MAST, data={"request": json.dumps(req)}, timeout=60)
    r.raise_for_status()
    res = r.json()["resolvedCoordinate"][0]
    return res["ra"], res["decl"], f"MAST ({res.get('resolver')}, {res.get('canonicalName')})"


def ned(name):
    r = requests.get(NED, params={"name": name, "of": "ascii_bar"}, timeout=60)
    r.raise_for_status()
    j = requests.get(NED, params={"name": name, "of": "json"}, timeout=60).json()
    return j["Preferred"]["Position"]["RA"], j["Preferred"]["Position"]["Dec"], "NED"


for name in sys.argv[1:]:
    for fn in (mast, ned):
        try:
            ra, dec, src = fn(name)
            print(f"{name:20s} RA {ra:.5f} Dec {dec:.5f}  via {src}")
            break
        except Exception as e:
            print(f"{name:20s} {fn.__name__} failed: {type(e).__name__} {str(e)[:80]}")
