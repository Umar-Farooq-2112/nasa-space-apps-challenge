"""Mover Spotter API. Run from repo root: .venv/Scripts/python -m uvicorn backend.app:app --reload

Users upload FITS images into datasets (see backend/store.py). Nothing about targets is built in.
The React front end (frontend/, built to frontend/dist) is served from the same server.
"""
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import movers, store

app = FastAPI(title="Mover Spotter")
DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


class NewDataset(BaseModel):
    name: str
    ra: Optional[float] = None
    dec: Optional[float] = None


class DatasetChanges(BaseModel):
    name: Optional[str] = None
    ra: Optional[float] = None
    dec: Optional[float] = None
    clear_centre: bool = False       # true = forget the RA/Dec
    crop: Optional[int] = None       # window size in pixels for big images


def _guard(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except store.UploadError as e:
        raise HTTPException(400, str(e))


@app.get("/api/datasets")
def datasets():
    return store.list_datasets()


@app.post("/api/datasets")
def new_dataset(d: NewDataset):
    meta = _guard(store.create_dataset, d.name, d.ra, d.dec)
    return store.summary(meta["id"])


@app.get("/api/datasets/{ds_id}")
def dataset(ds_id: str):
    return _guard(store.summary, ds_id)


@app.patch("/api/datasets/{ds_id}")
def change_dataset(ds_id: str, c: DatasetChanges):
    """Set, change or clear the RA/Dec (and window size) at any time. Original files are never modified."""
    _guard(store.update_dataset, ds_id, c.name, c.ra, c.dec, c.clear_centre, c.crop)
    return store.summary(ds_id)


@app.delete("/api/datasets/{ds_id}")
def remove_dataset(ds_id: str):
    _guard(store.delete_dataset, ds_id)
    return {"ok": True}


@app.post("/api/datasets/{ds_id}/files")
async def upload(ds_id: str, files: List[UploadFile] = File(...)):
    """Add FITS files. Every file gets its own result so one bad file does not stop the others."""
    _guard(store.get_meta, ds_id)
    results = []
    for f in files:
        try:
            results.append({"name": f.filename, "ok": True, **store.add_file(ds_id, await f.read(), f.filename)})
        except store.UploadError as e:
            results.append({"name": f.filename, "ok": False, "error": str(e)})
    return {"results": results, "dataset": store.summary(ds_id)}


@app.get("/api/datasets/{ds_id}/files")
def files(ds_id: str):
    return _guard(store.list_files, ds_id)


@app.delete("/api/datasets/{ds_id}/files/{file}")
def remove_file(ds_id: str, file: str):
    _guard(store.remove_file, ds_id, file)
    return store.summary(ds_id)


@app.get("/api/datasets/{ds_id}/frames")
def frames(ds_id: str, band: Optional[str] = None):
    items = _guard(store.list_frames, ds_id, band)
    for it in items:
        it["png_url"] = f"/api/datasets/{ds_id}/frame.png?file={it['file']}&v={int(it['mjd'] * 1000)}"
    return {"dataset": store.summary(ds_id), "frames": items}


@app.get("/api/datasets/{ds_id}/frame.png")
def frame_png(ds_id: str, file: str):
    return Response(_guard(store.render_frame, ds_id, file), media_type="image/png")


@app.get("/api/datasets/{ds_id}/movers")
def find_movers(ds_id: str, band: Optional[str] = None, nsigma: float = 4.0):
    """Mover Spotter. Use ONE band at a time: different bands show different stars."""
    frames_ = _guard(store.load_frames, ds_id, band)
    if len(frames_) < 5:
        return {"movers": [], "n_frames": len(frames_),
                "note": f"Need at least 5 frames in one band to spot movers; this has {len(frames_)}."}
    need = max(5, round(0.4 * len(frames_)))  # a real source shows up in most frames; blocks chance matches
    centre = store.effective_centre(ds_id)
    found = movers.spot_movers(frames_, tuple(centre), min_frames=need, nsigma=nsigma)
    return {"movers": found, "n_frames": len(frames_)}


def _picture(ds_id, band, fn):
    frames_ = _guard(store.load_frames, ds_id, band)
    if len(frames_) < 2:
        raise HTTPException(400, "need at least 2 usable images")
    return Response(fn(frames_), media_type="image/png")


@app.get("/api/datasets/{ds_id}/composite.png")
def composite(ds_id: str, band: Optional[str] = None):
    return _picture(ds_id, band, store.render_composite)


@app.get("/api/datasets/{ds_id}/difference.png")
def difference(ds_id: str, band: Optional[str] = None):
    return _picture(ds_id, band, store.render_difference)


if DIST.exists():  # built React app (npm run build in frontend/)
    app.mount("/", StaticFiles(directory=DIST, html=True))
else:
    @app.get("/")
    def not_built():
        return Response("Front end not built yet. Run: cd frontend && npm install && npm run build",
                        media_type="text/plain")
