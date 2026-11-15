"""Object name -> sky position now, via the CDS Sesame name resolver (SIMBAD/NED/VizieR).
SIMBAD positions are for the year 2000; fast-moving stars have moved a lot since, so the proper motion
is applied to bring them to the SPHEREx era (2026.0), otherwise they fall outside a small cutout."""
import re
from functools import lru_cache

import numpy as np
import requests

SESAME = "https://cds.unistra.fr/cgi-bin/nph-sesame/-oxp/SNV"
EPOCH = 2026.0


def _num(tag: str, text: str):
    m = re.search(rf"<{tag}>\s*([-+0-9.eE]+)\s*</{tag}>", text)
    return float(m.group(1)) if m else None


@lru_cache(maxsize=1024)
def resolve(name: str) -> dict:
    """{'name', 'ra', 'dec', 'pm_mas_yr'} or raises LookupError (unknown) / RuntimeError (service down)."""
    try:
        r = requests.get(SESAME, params=name, timeout=20)   # follows CDS's redirect to its mirror
        r.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError("The name lookup service (CDS Sesame) is not responding. Enter RA and Dec instead.") from e
    text = r.text
    ra, dec = _num("jradeg", text), _num("jdedeg", text)
    if ra is None or dec is None:
        raise LookupError(f'No object called "{name}" was found. Check the spelling or enter RA and Dec.')
    pmra, pmde = _num("pmRA", text) or 0.0, _num("pmDE", text) or 0.0
    dt = EPOCH - 2000.0
    ra = (ra + pmra * dt / 3.6e6 / np.cos(np.radians(dec))) % 360
    dec = dec + pmde * dt / 3.6e6
    oname = re.search(r"<oname>([^<]+)</oname>", text)
    return {"name": oname.group(1).strip() if oname else name, "ra": round(float(ra), 5),
            "dec": round(float(dec), 5), "pm_mas_yr": round(float(np.hypot(pmra, pmde)), 1),
            "pmra": pmra, "pmdec": pmde}
