"""Offline test for the local SPHEREx index search (no network). Run: .venv/Scripts/python -m pytest -q"""
import numpy as np

from backend import sky_index as S


def test_find_images_inside_outside_and_dedupe(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "DB", tmp_path / "i.sqlite")
    con = S._db()
    s = S.PIX_DEG
    rot = [s * np.cos(0.5), -s * np.sin(0.5), -s * np.sin(0.5), -s * np.cos(0.5)]   # rotated, flipped like SPHEREx
    rows = [
        ("dr1/level2/W1/v1/3/level2_W1_0001_1D3_spx_v1.fits", 60800.0, 100.0, 20.0),   # centered on target
        ("dr1/level2/W1/retry/3/level2_W1_0001_1D3_spx_retry.fits", 60800.0, 100.0, 20.0),  # same exposure again
        ("dr1/level2/W2/v1/3/level2_W2_0001_1D3_spx_v1.fits", 60700.0, 101.5, 20.0),   # target 1.4 deg off: inside
        ("dr1/level2/W3/v1/3/level2_W3_0001_1D3_spx_v1.fits", 60900.0, 103.0, 20.0),   # 2.8 deg off: outside
        ("dr1/level2/W4/v1/3/level2_W4_0001_1D3_spx_v1.fits", 60950.0, 280.0, -20.0),  # other side of the sky
    ]
    for key, mjd, ra, dec in rows:
        con.execute("INSERT INTO images VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (key, "D3", mjd, ra, dec, 1020.5, 1020.5, *rot))
    con.commit()
    hits = S.find_images(100.0, 20.0, "D3", fov=0.1)
    assert [h[1] for h in hits] == [60700.0, 60800.0]          # oldest first, duplicate exposure dropped
    assert hits[0][0].startswith("ibe/data/spherex/dr1/level2/W2/")
    assert S.find_images(100.0, 20.0, "D5") is None             # nothing indexed for that detector
