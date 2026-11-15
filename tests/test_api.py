"""API tests with synthetic FITS files uploaded through the real endpoints (stored in a temp folder)."""
import io

import numpy as np
import pytest
from astropy.io import fits
from fastapi.testclient import TestClient

from backend import store
from backend.app import app
from tests.test_movers import RA0, DEC0, build

client = TestClient(app)


@pytest.fixture(autouse=True)
def tmp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path)


def fits_bytes(frame, band="2", with_date=True, with_wcs=True, data=None):
    h = frame.wcs.to_header() if with_wcs else fits.Header()
    if with_date:
        h["MJD-OBS"] = frame.mjd
    h["BAND"] = band
    buf = io.BytesIO()
    fits.PrimaryHDU(frame.image if data is None else data, h).writeto(buf)
    return buf.getvalue()


def upload(ds, items):
    r = client.post(f"/api/datasets/{ds}/files", files=[("files", (n, b, "application/fits")) for n, b in items])
    assert r.status_code == 200
    return r.json()["results"]


def new_ds(**kw):
    return client.post("/api/datasets", json={"name": "Test field", **kw}).json()["id"]


def patch(ds, **kw):
    r = client.patch(f"/api/datasets/{ds}", json=kw)
    assert r.status_code == 200, r.text
    return r.json()


def test_upload_then_find_mover():
    frames = build([(48.0, 48.0, 0.004, -0.002, 60.0)])
    ds = new_ds()
    res = upload(ds, [(f"epoch{i}.fits", fits_bytes(f)) for i, f in enumerate(frames)])
    assert all(r["ok"] for r in res), res
    listed = client.get(f"/api/datasets/{ds}/frames?band=W2").json()["frames"]
    assert len(listed) == 15 and listed[0]["mjd"] <= listed[-1]["mjd"]       # oldest first, band "2" -> "W2"
    out = client.get(f"/api/datasets/{ds}/movers?band=W2").json()
    assert len(out["movers"]) == 1
    assert client.get(f"/api/datasets/{ds}/frame.png?file={listed[0]['file']}").headers["content-type"] == "image/png"
    for view in ("composite", "difference"):
        r = client.get(f"/api/datasets/{ds}/{view}.png?band=W2")
        assert r.status_code == 200 and r.content[:4] == b"\x89PNG"


def test_helpful_errors():
    f = build([])[0]
    ds = new_ds()
    res = upload(ds, [("nowcs.fits", fits_bytes(f, with_wcs=False)),
                      ("nodate.fits", fits_bytes(f, with_date=False)),
                      ("junk.fits", b"not a fits file"),
                      ("ok.fits", fits_bytes(f)),
                      ("ok.fits", fits_bytes(f))])
    msgs = [r.get("error", "OK") for r in res]
    assert "sky coordinates" in msgs[0] and "date" in msgs[1] and "FITS" in msgs[2]
    assert msgs[3] == "OK" and "already" in msgs[4]


def test_centre_can_be_set_changed_and_cleared_any_time():
    f = build([])[0]
    big = np.random.default_rng(0).normal(0, 1, (400, 400)).astype("f4")
    ds = new_ds()                                            # no centre at creation
    assert upload(ds, [("big.fits", fits_bytes(f, data=big))])[0]["ok"]          # upload is accepted ...
    s = client.get(f"/api/datasets/{ds}").json()
    assert s["n_needs_centre"] == 1 and s["n_ok"] == 0       # ... but it needs a centre to be shown
    assert client.get(f"/api/datasets/{ds}/frames").json()["frames"] == []

    s = patch(ds, ra=RA0, dec=DEC0)                          # set
    assert s["n_ok"] == 1 and s["centre"] == pytest.approx([RA0, DEC0])
    fr = client.get(f"/api/datasets/{ds}/frames").json()["frames"]
    assert (fr[0]["width"], fr[0]["height"]) == (600, 600)   # 200 px window x scale 3

    s = patch(ds, ra=RA0 + 5, dec=DEC0)                      # change to somewhere the image does not cover
    assert s["n_outside"] == 1 and s["n_ok"] == 0
    s = patch(ds, ra=RA0, dec=DEC0)                          # change back
    assert s["n_ok"] == 1
    s = patch(ds, crop=100)                                  # window size
    assert client.get(f"/api/datasets/{ds}/frames").json()["frames"][0]["width"] == 600   # 100 px x scale 6
    s = patch(ds, clear_centre=True)                         # cancel
    assert s["centre"] is None and s["n_needs_centre"] == 1 and s["n_ok"] == 0


def test_small_images_work_without_centre_and_originals_are_kept():
    f = build([])[0]
    ds = new_ds()
    assert upload(ds, [("a.fits", fits_bytes(f))])[0]["ok"]
    s = client.get(f"/api/datasets/{ds}").json()
    assert s["n_ok"] == 1 and s["centre"] is None and s["centre_is_auto"] and s["effective_centre"] is not None
    names = [x["orig"] for x in client.get(f"/api/datasets/{ds}/files").json()]
    assert names == ["a.fits"]
    assert client.delete(f"/api/datasets/{ds}/files/{client.get(f'/api/datasets/{ds}/files').json()[0]['file']}").json()["n_files"] == 0


def test_bad_values_and_ids():
    ds = new_ds()
    assert client.patch(f"/api/datasets/{ds}", json={"ra": 10, "dec": 120}).status_code == 400
    assert client.patch(f"/api/datasets/{ds}", json={"ra": 10}).status_code == 400
    assert client.get("/api/datasets/../frames").status_code in (400, 404)
    assert client.get("/api/datasets/nope/frames").status_code == 400
