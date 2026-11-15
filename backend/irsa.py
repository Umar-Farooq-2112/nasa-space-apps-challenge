"""Live SPHEREx data from NASA IRSA: find images covering a spot (our AWS-built index in sky_index.py,
else IRSA's TAP search), then download small cutouts from IRSA's cutout server.
IRSA is often slow or returns 502, so every call retries, and the app runs fetches as background jobs
(`start`) that the frontend polls. Also used offline by scripts/fetch_all.py to pre-download demo targets."""
import io
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests
from astropy.io.votable import parse_single_table

from . import sky_index

TAP = "https://irsa.ipac.caltech.edu/TAP"
DETECTORS = ("D1", "D2", "D3", "D4", "D5", "D6")
LIST_MAX_AGE = 7 * 86400   # re-search after a week: IRSA adds new images in weekly releases


def _retry(fn, deadline):
    """Call fn() until IRSA answers with a non-5xx response or the deadline passes."""
    while True:
        try:
            r = fn()
            if r.status_code < 500:
                return r
        except requests.RequestException:
            pass
        if time.time() > deadline:
            raise RuntimeError("NASA IRSA is not responding right now, please try again later.")
        time.sleep(5)


def find_images(ra: float, dec: float, detector: str, timeout: float = 900):
    """[[uri, mjd], ...] of SPHEREx images covering (ra, dec) for one detector, oldest first."""
    assert detector in DETECTORS  # goes into SQL
    query = f"""SELECT a.uri, p.time_bounds_lower FROM spherex.artifact a JOIN spherex.plane p ON a.planeid = p.planeid
WHERE CONTAINS(POINT('ICRS', {float(ra)}, {float(dec)}), p.poly) = 1 AND p.energy_bandpassname = 'SPHEREx-{detector}'
ORDER BY p.time_bounds_lower"""
    deadline = time.time() + timeout
    r = _retry(lambda: requests.post(TAP + "/async", data={
        "REQUEST": "doQuery", "LANG": "ADQL", "QUERY": query, "PHASE": "RUN"},
        allow_redirects=False, timeout=60), deadline)
    job = r.headers.get("Location") or r.url
    while True:
        phase = _retry(lambda: requests.get(job + "/phase", timeout=30), deadline).text.strip()
        if phase == "COMPLETED":
            break
        if phase in ("ERROR", "ABORTED"):
            err = _retry(lambda: requests.get(job + "/error", timeout=30), deadline).text
            raise RuntimeError("IRSA search failed: " + err[:200])
        if time.time() > deadline:
            raise RuntimeError("NASA IRSA search is queued for too long, please try again later.")
        time.sleep(5)
    res = _retry(lambda: requests.get(job + "/results/result", timeout=120), deadline)
    t = parse_single_table(io.BytesIO(res.content)).to_table()
    seen, out = set(), []
    for uri, mjd in zip(t["uri"], t["time_bounds_lower"]):
        uri = str(uri)
        if uri.endswith(".fits") and uri not in seen:
            seen.add(uri)
            out.append([uri, float(mjd)])
    return out


def spread(images, n: int):
    """n images evenly spread over the whole time range (so the movie covers every survey pass)."""
    if len(images) <= n:
        return images
    return [images[i] for i in sorted(set(np.linspace(0, len(images) - 1, n).round().astype(int)))]


def download(uri: str, mjd: float, ra: float, dec: float, fov: float, folder: Path, detector: str, timeout=300):
    """Save one cutout as <mjd>_<detector>_<name>.fits. Returns False if IRSA has no such file."""
    dest = folder / f"{mjd:.4f}_{detector}_{Path(uri).name}"
    if dest.exists():
        return True
    # 1.5x: frames are rotated onto a north-up grid, a fov-sized cutout would leave empty corners (needs >= sqrt 2)
    url = f"https://irsa.ipac.caltech.edu/{uri}?center={ra},{dec}&size={round(fov * 1.5, 4)}"
    r = _retry(lambda: requests.get(url, timeout=180), time.time() + timeout)
    if r.status_code != 200 or r.content[:6] != b"SIMPLE":
        return False
    # unique temp name (app + fetch_all may download the same file at once); rename = never half a file
    tmp = dest.with_suffix(f".{threading.get_ident()}.part")
    tmp.write_bytes(r.content)
    tmp.replace(dest)
    return True


def _search_irsa(ra, dec, detector, folder: Path, job: dict):
    """Fallback when no local index exists: IRSA TAP search, cached for a week in the cutout folder."""
    saved = folder / f"images_{detector}.json"
    if saved.exists() and time.time() - saved.stat().st_mtime < LIST_MAX_AGE:
        return json.loads(saved.read_text())
    job["state"] = "searching"
    try:
        images = find_images(ra, dec, detector)
        saved.write_text(json.dumps(images))
        return images
    except RuntimeError:
        if not saved.exists():
            raise
        return json.loads(saved.read_text())   # IRSA down: keep using last week's list


def fetch(ra, dec, fov, detector, folder: Path, n: int = 20, job: dict | None = None):
    """Search (or reuse the saved image list) and download up to n cutouts into folder."""
    job = job if job is not None else {}
    folder.mkdir(parents=True, exist_ok=True)
    images = sky_index.find_images(ra, dec, detector, fov)   # our own AWS-built index: instant, no IRSA search
    if images is None:
        images = _search_irsa(ra, dec, detector, folder, job)
    picks = spread(images, n)
    job.update(state="downloading", total=len(picks), available=len(images),
               first_mjd=images[0][1] if images else None, last_mjd=images[-1][1] if images else None)
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(lambda im: download(im[0], im[1], ra, dec, fov, folder, detector), picks))


_jobs: dict[str, dict] = {}
_lock = threading.Lock()


MAX_JOBS = 4  # ponytail: global cap; add per-client rate limits if this is ever hosted publicly


def start(ra, dec, fov, detector, folder: Path) -> dict:
    """Start a background fetch unless one is running or finished recently. Returns the job status
    {state: searching|downloading|done|error, total, error}."""
    key = f"{folder.name}/{detector}"
    with _lock:
        j = _jobs.get(key)
        if j:
            running = j["state"] in ("searching", "downloading")
            recent = time.time() - j["t"] < (3600 if j["state"] == "done" else 30)
            if running or recent:
                return j
        # cap concurrent downloads so a flood of new positions cannot exhaust bandwidth, threads or disk
        # (not stored in _jobs, so the client simply retries on its next poll)
        if sum(x["state"] in ("searching", "downloading") for x in _jobs.values()) >= MAX_JOBS:
            return {"state": "error", "total": None, "error": "Many people are fetching new spots right now. Try again in a minute.", "t": time.time()}
        j = _jobs[key] = {"state": "searching", "total": None, "error": None, "t": time.time()}

    def run():
        try:
            fetch(ra, dec, fov, detector, folder, job=j)
            j["state"] = "done"
        except Exception as e:  # report any failure to the user instead of a silent dead thread
            j.update(state="error", error=str(e))
        j["t"] = time.time()

    threading.Thread(target=run, daemon=True).start()
    return j
