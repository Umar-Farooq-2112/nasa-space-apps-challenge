"""List SPHEREx images covering a sky position (via IRSA TAP).
Usage: find_images.py RA DEC [DETECTOR e.g. D3]
IRSA's server often returns 502, so we submit an async job and poll with retries.
Result is saved to data/raw/images_<ra>_<dec>.csv
"""
import sys
import time

import requests
from astropy.io.votable import parse_single_table
import io

TAP = "https://irsa.ipac.caltech.edu/TAP"
ra, dec = float(sys.argv[1]), float(sys.argv[2])
det = sys.argv[3] if len(sys.argv) > 3 else None   # e.g. D3
det_sql = f"AND p.energy_bandpassname = 'SPHEREx-{det}'" if det else ""

QUERY = f"""
SELECT TOP 200 a.uri AS uri, p.time_bounds_lower AS mjd, p.energy_bandpassname AS band, p.calibrationlevel AS level, a.producttype AS ptype
FROM spherex.artifact a JOIN spherex.plane p ON a.planeid = p.planeid
WHERE CONTAINS(POINT('ICRS', {ra}, {dec}), p.poly) = 1 {det_sql}
ORDER BY p.time_bounds_lower
"""


def retry(fn, tries=2000):
    """Call fn() until it works; IRSA returns 502 a lot."""
    for i in range(tries):
        try:
            r = fn()
            if r.status_code < 500:
                return r
        except requests.RequestException:
            pass
        time.sleep(5)
    raise RuntimeError("IRSA kept failing")


r = retry(lambda: requests.post(TAP + "/async", data={
    "REQUEST": "doQuery", "LANG": "ADQL", "QUERY": QUERY, "PHASE": "RUN"},
    allow_redirects=False, timeout=60))
job = r.headers.get("Location") or r.url
print("job:", job, flush=True)

while True:
    phase = retry(lambda: requests.get(job + "/phase", timeout=30)).text.strip()
    print("phase:", phase, flush=True)
    if phase in ("COMPLETED", "ERROR", "ABORTED"):
        break
    time.sleep(10)

if phase != "COMPLETED":
    print(retry(lambda: requests.get(job + "/error", timeout=30)).text)
    sys.exit(1)

res = retry(lambda: requests.get(job + "/results/result", timeout=120))
t = parse_single_table(io.BytesIO(res.content)).to_table()
print(len(t), "rows")
print(t[:15])
t.write(f"data/raw/images_{ra}_{dec}.csv", format="csv", overwrite=True)
