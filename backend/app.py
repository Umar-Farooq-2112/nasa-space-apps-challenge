"""Mover Spotter API. Run from repo root: .venv/Scripts/python -m uvicorn backend.app:app --reload"""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import cutouts, irsa, movers, resolve, sky_index
from .targets import TARGETS

app = FastAPI(title="Mover Spotter")


@app.middleware("http")
async def revalidate_pages(request, call_next):
    """Make browsers re-check the page on every visit (cheap via ETag), so updates show up immediately."""
    resp = await call_next(request)
    if not request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-cache"
    return resp

# One detector per movie: each sees a different wavelength, so stars change brightness between detectors.
Detector = Literal["D1", "D2", "D3", "D4", "D5", "D6"]
RA = Query(ge=0, lt=360)
DEC = Query(ge=-90, le=90)
FOV = Query(0.1, ge=0.02, le=0.3, description="cutout size in degrees")


@app.get("/api/targets")
def targets():
    return TARGETS


@app.get("/api/frames")
def frames(ra: float = RA, dec: float = DEC, fov: float = FOV, detector: Detector = "D3"):
    """Cached frames for a sky spot, oldest first, plus the status of the live IRSA fetch.
    The first call for a new spot starts the fetch; poll until status.state is done or error."""
    folder = cutouts.folder_for(ra, dec, fov)
    status = irsa.start(ra, dec, fov, detector, folder)
    items = cutouts.list_frames(folder, detector)
    for it in items:
        it["png_url"] = f"/api/frame.png?folder={it['folder']}&file={it['file']}&v={cutouts.RENDER_VERSION}"
    return {"ra": ra, "dec": dec, "fov": fov, "detector": detector,
            "status": {k: status.get(k) for k in ("state", "total", "error", "available", "first_mjd", "last_mjd")},
            "archive_newest_mjd": sky_index.newest_mjd(detector),
            "frames": items}


@app.get("/api/movers")
def find_movers(ra: float = RA, dec: float = DEC, fov: float = FOV, detector: Detector = "D3"):
    folder = cutouts.folder_for(ra, dec, fov)
    files = tuple(f["file"] for f in cutouts.list_frames(folder, detector))
    return _movers(folder.name, detector, files)


@lru_cache(maxsize=64)   # keyed by the exact frame files, so new downloads give a fresh result
def _movers(folder_name: str, detector: str, files: tuple):
    if len(files) < 5:
        return {"movers": [], "note": f"Need at least 5 frames to spot movers, have {len(files)}."}
    ra, dec, fov = (float(x) for x in folder_name.split("_"))
    frames = cutouts.load_frames(cutouts.CACHE / folder_name, detector)
    need = max(5, round(0.4 * len(frames)))  # a real source shows up in most frames; blocks chance matches
    # search only the inner 80% of the area the user sees: cutouts are 1.5x larger just to fill the rotated
    # display, and their edges produced fake tracks on real data (RW Aur, WISE 0855 D6)
    found = movers.spot_movers(frames, (ra, dec), min_frames=need, half_size=0.4 * fov * 3600)
    grid = cutouts.display_wcs(folder_name)   # frames are shown resampled onto this north-up grid
    for m in found:
        for p in m["points"]:
            p["px"], p["py"] = (float(v) for v in grid.world_to_pixel_values(p["ra"], p["dec"]))
    return {"movers": found, "scale": cutouts.SCALE}


def _cached_file(folder: str, file: str) -> Path:
    # block path tricks like ../
    if Path(folder).name != folder or Path(file).name != file or not file.endswith(".fits"):
        raise HTTPException(400, "bad name")
    path = cutouts.CACHE / folder / file
    if not path.exists():
        raise HTTPException(404, "not found")
    return path


@app.get("/api/frame.png")
def frame_png(folder: str, file: str, mode: Literal["sky", "diff", "deep"] = "sky", n: int = 0):
    """mode=diff: frame minus the median of all frames of its detector (n = frame count, part of the URL
    so the browser cache refreshes when more frames arrive)."""
    _cached_file(folder, file)
    ref = ()
    if mode != "sky":
        det = file.split("_")[1]
        ref = tuple(f["file"] for f in cutouts.list_frames(cutouts.CACHE / folder, det))
    return Response(cutouts.render_png(folder, file, ref, mode), media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})  # cutouts never change


@app.get("/api/frame.fits")
def frame_fits(folder: str, file: str):
    """The original SPHEREx cutout (all layers: IMAGE, FLAGS, VARIANCE, ...) for scientists."""
    return FileResponse(_cached_file(folder, file), media_type="application/fits", filename=file)


@app.get("/api/resolve")
def resolve_name(name: str = Query(min_length=1, max_length=100)):
    try:
        return resolve.resolve(name.strip())
    except LookupError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(503, str(e))


# Local runs serve the page from here; on Vercel the CDN serves public/ and leaves it out of the function bundle,
# so the folder may be missing: check_dir=False keeps the API from crashing at import.
app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent.parent / "public", html=True, check_dir=False))
