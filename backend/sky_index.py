"""Our own "which SPHEREx images cover this spot" index, built from NASA IRSA's public AWS copy of SPHEREx.
Needed because IRSA's search services (TAP/SIA) are often down, while its cutout server keeps working.
For every level-2 image we read only the FITS header (first ~30 KB of a 65 MB file) and store pointing + time.
Build/update (resumable, safe to re-run for new weekly data):
    .venv/Scripts/python -m backend.sky_index D3
"""
import sqlite3
import sys
from functools import lru_cache
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests

BUCKET = "https://nasa-irsa-spherex.s3.amazonaws.com"
RELEASES = ("dr1", "qr3")   # dr1 = 2025 data, qr3 = 2026 quick release (qr2 is an older version of dr1)
DB = Path(__file__).resolve().parent.parent / "data" / "index" / "spherex.sqlite"
SEED = Path(__file__).resolve().parent.parent / "seed" / "index"   # compact copy shipped with the code (see export)
COLS = "mjd, ra, dec, crpix1, crpix2, cd11, cd12, cd21, cd22"
NPIX = 2040
PIX_DEG = 6.15 / 3600
NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"
_local = threading.local()


def _session():
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
    return _local.s


def _get(url, **kw):
    for attempt in range(6):
        try:
            r = _session().get(url, timeout=60, **kw)
            if r.status_code < 500:
                return r
        except requests.RequestException:
            pass
        time.sleep(2 ** attempt)
    raise RuntimeError("AWS not responding: " + url)


def _list(prefix, folders=False):
    """S3 keys (or sub-folders) under prefix, following pagination."""
    out, token = [], None
    while True:
        params = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
        if folders:
            params["delimiter"] = "/"
        if token:
            params["continuation-token"] = token
        root = ET.fromstring(_get(BUCKET + "/", params=params).content)   # AWS's own XML, no entities
        path = f"{NS}CommonPrefixes/{NS}Prefix" if folders else f"{NS}Contents/{NS}Key"
        out += [e.text for e in root.iterfind(path)]
        token = root.findtext(NS + "NextContinuationToken")
        if not token:
            return out


def list_images(detector: str):
    """All level-2 image keys for one detector (e.g. D3) in every release."""
    det = detector[1]
    versions = []
    for rel in RELEASES:
        for week in _list(f"{rel}/level2/", folders=True):
            versions += _list(week, folders=True)
    with ThreadPoolExecutor(16) as ex:
        keys = [k for ks in ex.map(lambda v: _list(f"{v}{det}/"), versions) for k in ks]
    return [k for k in keys if k.endswith(".fits")]


def read_pointing(key: str):
    """(mjd, crval1, crval2, crpix1, crpix2, cd11, cd12, cd21, cd22) from the IMAGE header, or None."""
    try:
        return _read_pointing(key)
    except Exception as e:  # one odd file must not stop indexing 100k others
        print("skip", key, type(e).__name__, e, flush=True)
        return None


_KEYS = {b"MJD-OBS", b"CRVAL1", b"CRVAL2", b"CRPIX1", b"CRPIX2", b"CDELT1", b"CDELT2",
         b"PC1_1", b"PC1_2", b"PC2_1", b"PC2_2", b"CD1_1", b"CD1_2", b"CD2_1", b"CD2_2"}


_NEED = {b"MJD-OBS", b"CRVAL1", b"CRVAL2", b"CRPIX1", b"CRPIX2"}


def _scan(b: bytes, start: int):
    """Header values from 80-byte cards starting at byte offset `start` (a multiple of 80). Returns (values, saw END)."""
    v = {}
    for i in range(start, len(b) - 79, 80):
        k = b[i:i + 8].rstrip()
        if k == b"END":
            return v, True
        if k in _KEYS and k not in v and b[i + 8:i + 10] == b"= ":   # first = main WCS, not alternates
            v[k] = float(b[i + 10:i + 80].split(b"/")[0])
    return v, False


def _read_pointing(key: str):
    # Plain card scan instead of astropy (astropy parsing is GIL-bound at 100k files). Download is the other
    # bottleneck, so first fetch only bytes 9600-21119, where SPHEREx puts the WCS and MJD (dr1 and qr3);
    # if anything is missing there, read the whole header.
    url = f"{BUCKET}/{key}"
    v, _ = _scan(_get(url, headers={"Range": "bytes=9600-21119"}).content, 0)
    if not (_NEED <= v.keys() and (b"PC1_1" in v or b"CD1_1" in v)):
        v, end = _scan(_get(url, headers={"Range": "bytes=0-63359"}).content, 2880)
        if not end or not _NEED <= v.keys():
            return None
    if b"CD1_1" in v:
        cd = [v.get(b"CD1_1", 0.0), v.get(b"CD1_2", 0.0), v.get(b"CD2_1", 0.0), v.get(b"CD2_2", 0.0)]
    else:   # FITS defaults: PC = identity, CDELT = 1
        c1, c2 = v.get(b"CDELT1", 1.0), v.get(b"CDELT2", 1.0)
        cd = [c1 * v.get(b"PC1_1", 1.0), c1 * v.get(b"PC1_2", 0.0), c2 * v.get(b"PC2_1", 0.0), c2 * v.get(b"PC2_2", 1.0)]
    return (v[b"MJD-OBS"], v[b"CRVAL1"], v[b"CRVAL2"], v[b"CRPIX1"], v[b"CRPIX2"], *cd)


def _db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, check_same_thread=False, timeout=60)   # builds for several detectors may run at once
    con.execute("PRAGMA journal_mode=WAL")   # the app keeps reading while a build writes
    con.execute("""CREATE TABLE IF NOT EXISTS images (key TEXT PRIMARY KEY, det TEXT, mjd REAL,
                   ra REAL, dec REAL, crpix1 REAL, crpix2 REAL, cd11 REAL, cd12 REAL, cd21 REAL, cd22 REAL)""")
    return con


def _keys(detector: str):
    """Image keys, cached for a day (listing all of AWS takes minutes)."""
    cache = DB.parent / f"keys_{detector}.txt"
    if cache.exists() and time.time() - cache.stat().st_mtime < 86400:
        return cache.read_text().split()
    keys = list_images(detector)
    DB.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text("\n".join(keys))
    return keys


def _index(con, detector, todo, workers, label):
    print(f"{label}: {len(todo)} images", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(workers) as ex:
        for n, (key, p) in enumerate(zip(todo, ex.map(read_pointing, todo)), 1):
            if p:
                con.execute("INSERT OR REPLACE INTO images VALUES (?,?,?,?,?,?,?,?,?,?,?)", (key, detector, *p))
            if n % 2000 == 0:
                con.commit()
                print(f"  {n}/{len(todo)}  {n / (time.time() - t0):.0f}/s", flush=True)
    con.commit()


def build(detector: str = "D3", workers: int = 96, near_deg: float = 3.5):
    """Index in 3 passes so the demo targets are usable early:
    1) first exposure of every observation (each observation = 2-4 exposures ~0.2 deg apart; the next jumps away),
    2) all exposures of observations near a demo target, 3) everything else."""
    from .targets import TARGETS
    con = _db()
    done = {k for (k,) in con.execute("SELECT key FROM images")}
    groups = {}
    for k in _keys(detector):
        p = k.rsplit("/", 1)[0], Path(k).name.split("_")[1:4]   # folder + week + observation number
        groups.setdefault(str(p), []).append(k)
    groups = [sorted(g) for g in groups.values()]
    print(f"{sum(map(len, groups))} {detector} images in {len(groups)} observations, {len(done)} already indexed")

    _index(con, detector, [g[0] for g in groups if g[0] not in done], workers, "pass 1 (one per observation)")
    pos = {k: (r, d) for k, r, d in con.execute("SELECT key, ra, dec FROM images")}
    t = np.radians([[x["ra"], x["dec"]] for x in TARGETS])

    def near(k):
        if k not in pos:
            return False
        r, d = np.radians(pos[k])
        cos = np.sin(d) * np.sin(t[:, 1]) + np.cos(d) * np.cos(t[:, 1]) * np.cos(r - t[:, 0])
        return bool(np.any(cos > np.cos(np.radians(near_deg))))
    second = [k for g in groups if near(g[0]) for k in g[1:] if k not in done]
    _index(con, detector, second, workers, "pass 2 (near demo targets)")
    done = set(pos) | set(second)
    _index(con, detector, [k for g in groups for k in g if k not in done], workers, "pass 3 (rest of the sky)")
    print("done", flush=True)


def export(detector: str):
    """Write a compact index for one detector to seed/index/<det>.npz (~10x smaller than the SQLite file),
    so a deployment without the SQLite build can still search the whole sky."""
    rows = _db().execute(f"SELECT key, {COLS} FROM images WHERE det=?", (detector,)).fetchall()
    SEED.mkdir(parents=True, exist_ok=True)
    m = np.array([r[1:] for r in rows], dtype=float)
    np.savez_compressed(SEED / f"{detector}.npz", keys=np.array([r[0] for r in rows], dtype="S"),
                        mjd=m[:, 0], geo=m[:, 1:].astype(np.float32))   # float32 = 0.1" on ra/dec, plenty
    print(detector, len(rows))


@lru_cache(maxsize=6)
def _seed_rows(detector: str):
    path = SEED / f"{detector}.npz"
    if not path.exists():
        return None
    z = np.load(path)
    return [k.decode() for k in z["keys"]], np.column_stack([z["mjd"], z["geo"].astype(float)])


def _rows(detector: str):
    """(keys, [[mjd, ra, dec, crpix1, crpix2, cd11, cd12, cd21, cd22], ...]) from the SQLite build if present,
    else from the shipped compact copy; None if this detector is not indexed."""
    if DB.exists():
        rows = _db().execute(f"SELECT key, {COLS} FROM images WHERE det=?", (detector,)).fetchall()
        return ([r[0] for r in rows], np.array([r[1:] for r in rows], dtype=float)) if rows else None
    return _seed_rows(detector)


def newest_mjd(detector: str):
    """Time of the newest indexed SPHEREx image for this detector (the latest NASA release we have), or None."""
    r = _rows(detector)
    return float(r[1][:, 0].max()) if r else None


def find_images(ra: float, dec: float, detector: str, fov: float = 0.1):
    """[[irsa_uri, mjd], ...] of indexed images whose area fully contains the cutout, oldest first.
    None if the index has nothing for this detector (not built)."""
    r = _rows(detector)
    if r is None:
        return None
    keys, m = r
    mjd, ra0, dec0 = m[:, 0], np.radians(m[:, 1]), np.radians(m[:, 2])
    a, d = np.radians(ra), np.radians(dec)
    # gnomonic (TAN) projection of the target onto each image plane, in degrees
    cosc = np.sin(dec0) * np.sin(d) + np.cos(dec0) * np.cos(d) * np.cos(a - ra0)
    xi = np.degrees(np.cos(d) * np.sin(a - ra0) / cosc)
    eta = np.degrees((np.cos(dec0) * np.sin(d) - np.sin(dec0) * np.cos(d) * np.cos(a - ra0)) / cosc)
    cd = m[:, 5:9].reshape(-1, 2, 2)
    pix = np.linalg.solve(cd, np.stack([xi, eta], axis=1)[:, :, None])[:, :, 0] + m[:, 3:5]
    margin = fov / 2 / PIX_DEG + 10   # whole cutout inside the image; +10 px covers ignored SIP distortion (<=6 px)
    ok = (cosc > 0) & np.all((pix > margin) & (pix < NPIX + 1 - margin), axis=1)
    hits, seen = [], set()
    for i in sorted(np.flatnonzero(ok), key=lambda i: mjd[i]):
        obs = Path(keys[i]).name.split("_spx_")[0]   # same exposure can exist in a normal + a "retry" folder
        if obs not in seen:
            seen.add(obs)
            hits.append([f"ibe/data/spherex/{keys[i]}", float(mjd[i])])
    return hits


if __name__ == "__main__":
    if sys.argv[1:2] == ["export"]:
        for det in sys.argv[2:]:
            export(det)
    else:
        build(sys.argv[1] if len(sys.argv) > 1 else "D3")
